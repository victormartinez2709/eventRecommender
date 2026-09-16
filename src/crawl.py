"""
The crawler. Works through the frontier table, calling the API for each artist,
and snowballs outward: every new name found in an event's lineup gets queued.

Resumable by design — kill it with Ctrl-C and run it again; it picks up where it
stopped, because all state lives in the frontier table, not in memory.

Run:
    python src/crawl.py               # process everything pending
    python src/crawl.py --limit 50    # just 50 items, for a first test
"""

from __future__ import annotations
import argparse
import datetime as dt

from tqdm import tqdm

from bit_client import BandsintownClient
from config import MAX_DEPTH
from db import connect


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def claim_batch(limit: int) -> list[tuple[str, str, int]]:
    """
    Take up to `limit` pending items off the frontier.

    Artists are fetched before events (ORDER BY kind) so that by the time we
    process an artist's events we already know their name and ID.

    Rows previously marked 'error' are re-claimed until attempts reaches 3, so a
    transient network failure or a 429 does not permanently drop an artist.
    """
    with connect() as conn:
        rows = conn.execute(
            """SELECT key, kind, depth FROM frontier
               WHERE status IN ('pending', 'error') AND attempts < 3
               ORDER BY depth ASC, kind ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [(r["key"], r["kind"], r["depth"]) for r in rows]


def mark(key: str, kind: str, status: str, error: str | None = None) -> None:
    """Record the outcome of one fetch."""
    with connect() as conn:
        conn.execute(
            """UPDATE frontier
               SET status = ?, attempts = attempts + 1, last_error = ?, updated_at = ?
               WHERE key = ? AND kind = ?""",
            (status, error, now(), key, kind),
        )


def queue_lineup_names(names: list[str], depth: int) -> int:
    """
    Add newly-seen artist names to the frontier at depth+1.

    Note these are NAMES, not IDs — the events endpoint gives lineup as plain
    strings. The crawler will resolve each to an ID when it fetches the profile.
    """
    if depth + 1 > MAX_DEPTH:
        return 0  # stop expanding; otherwise the crawl never terminates

    added = 0
    with connect() as conn:
        for name in names:
            clean = (name or "").strip()
            if not clean:
                continue
            for kind in ("artist", "events"):
                cur = conn.execute(
                    """INSERT OR IGNORE INTO frontier (key, kind, depth, status, updated_at)
                       VALUES (?, ?, ?, 'pending', ?)""",
                    (clean, kind, depth + 1, now()),
                )
                added += cur.rowcount
    return added


def handle_artist(payload) -> None:
    """Upsert one artist profile, and append a snapshot row for the time series."""
    if not isinstance(payload, dict) or not payload.get("id"):
        return

    ts = now()
    with connect() as conn:
        # ON CONFLICT ... DO UPDATE is an "upsert": insert if new, otherwise update
        # the fields that can change, while preserving first_seen_at.
        conn.execute(
            """INSERT INTO artists
                 (artist_id, name, mbid, url, image_url, facebook_page_url,
                  first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(artist_id) DO UPDATE SET
                 name = excluded.name,
                 mbid = COALESCE(excluded.mbid, artists.mbid),
                 url = excluded.url,
                 image_url = excluded.image_url,
                 facebook_page_url = excluded.facebook_page_url,
                 last_seen_at = excluded.last_seen_at""",
            (
                str(payload["id"]),
                payload.get("name", ""),
                payload.get("mbid") or None,
                payload.get("url"),
                payload.get("image_url"),
                payload.get("facebook_page_url"),
                ts,
                ts,
            ),
        )
        conn.execute(
            """INSERT OR IGNORE INTO artist_snapshots
                 (artist_id, observed_at, tracker_count, upcoming_event_count)
               VALUES (?, ?, ?, ?)""",
            (
                str(payload["id"]),
                ts,
                payload.get("tracker_count"),
                payload.get("upcoming_event_count"),
            ),
        )


def run(limit: int | None, batch_size: int = 100) -> None:
    client = BandsintownClient()
    processed = 0

    while True:
        take = batch_size if limit is None else min(batch_size, limit - processed)
        if take <= 0:
            break

        batch = claim_batch(take)
        if not batch:
            print("Frontier empty — nothing left to crawl.")
            break

        for key, kind, depth in tqdm(batch, desc=f"depth<={MAX_DEPTH}", unit="req"):
            if kind == "artist":
                status, payload = client.get_artist(key)
                if status == 200 and isinstance(payload, dict) and payload.get("id"):
                    handle_artist(payload)
                    mark(key, kind, "done")
                elif status in (200, 404):
                    # Empty body on 200 is how Bandsintown says "no such artist".
                    mark(key, kind, "not_found")
                else:
                    mark(key, kind, "error", f"HTTP {status}")

            else:  # kind == "events"
                status, payload = client.get_events(key, date="all")
                if status == 200 and isinstance(payload, list):
                    names: list[str] = []
                    for event in payload:
                        names.extend(event.get("lineup") or [])
                    queue_lineup_names(sorted(set(names)), depth)
                    mark(key, kind, "done")
                elif status in (200, 404):
                    mark(key, kind, "not_found")
                else:
                    mark(key, kind, "error", f"HTTP {status}")

            processed += 1

    with connect() as conn:
        stats = conn.execute(
            "SELECT status, COUNT(*) AS n FROM frontier GROUP BY status"
        ).fetchall()
    print("\nFrontier status:")
    for row in stats:
        print(f"  {row['status']:<12} {row['n']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max requests to make.")
    args = parser.parse_args()
    run(args.limit)
