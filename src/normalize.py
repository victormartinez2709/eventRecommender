"""
Turn the raw JSONL files into clean relational tables.

This is deliberately a SEPARATE step from crawling. The crawler's job is to get
bytes onto disk safely; this file's job is to interpret them. When you later
realise you parsed something wrong, you fix this file and re-run it — no
re-crawling, no extra load on Bandsintown, and your results stay reproducible.

Run:
    python src/normalize.py
"""

from __future__ import annotations
import datetime as dt
import gzip
import hashlib
import json
import re

from tqdm import tqdm

from config import RAW_DIR
from db import connect

# timezonefinder is a big dependency; make it optional so the pipeline still runs
# without it (you just won't get datetime_utc filled in).
try:
    from timezonefinder import TimezoneFinder
    from zoneinfo import ZoneInfo

    _TF = TimezoneFinder()
except ImportError:  # pragma: no cover
    _TF = None


def iter_raw(kind: str):
    """Yield every record ever written for a given kind ('artists' or 'events')."""
    root = RAW_DIR / kind
    if not root.exists():
        return
    # sorted() so files are processed in date order and later fetches win.
    for path in sorted(root.rglob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)


def venue_key(venue: dict) -> str:
    """
    Build a stable ID for a venue.

    Bandsintown gives no venue ID, so "Bluebird Theater" and "The Bluebird Theatre"
    would be two different rooms unless we normalise. We lowercase, strip anything
    that isn't a letter or digit, drop a leading "the", and round the coordinates
    to ~100m. Hashing the result gives a short, deterministic key.
    """
    name = (venue.get("name") or "").lower()
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    name = re.sub(r"^the\s+", "", name)

    city = (venue.get("city") or "").lower().strip()
    country = (venue.get("country") or "").lower().strip()

    def coord(value):
        try:
            return f"{round(float(value), 3)}"
        except (TypeError, ValueError):
            return ""

    blob = f"{name}|{city}|{country}|{coord(venue.get('latitude'))}|{coord(venue.get('longitude'))}"
    # sha1 is fine here — we need determinism, not cryptographic security.
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def to_utc(local_iso: str, lat, lon) -> str | None:
    """
    Bandsintown's `datetime` is LOCAL VENUE TIME with no offset. Parsing it as UTC
    silently shifts every show by several hours and quietly ruins any feature that
    depends on time. We attach the real timezone using the venue's coordinates.
    """
    if not local_iso or _TF is None:
        return None
    try:
        naive = dt.datetime.fromisoformat(local_iso.replace("Z", ""))
        tzname = _TF.timezone_at(lat=float(lat), lng=float(lon))
        if not tzname:
            return None
        return naive.replace(tzinfo=ZoneInfo(tzname)).astimezone(dt.timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def normalize_artists(conn) -> int:
    count = 0
    for record in tqdm(iter_raw("artists"), desc="artists", unit="rec"):
        payload = record.get("payload")
        if not isinstance(payload, dict) or not payload.get("id"):
            continue
        ts = record.get("fetched_at")
        conn.execute(
            """INSERT INTO artists
                 (artist_id, name, mbid, url, image_url, facebook_page_url,
                  first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(artist_id) DO UPDATE SET
                 name = excluded.name,
                 mbid = COALESCE(excluded.mbid, artists.mbid),
                 last_seen_at = MAX(artists.last_seen_at, excluded.last_seen_at)""",
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
            (str(payload["id"]), ts, payload.get("tracker_count"),
             payload.get("upcoming_event_count")),
        )
        count += 1
    return count


def normalize_events(conn) -> int:
    count = 0
    for record in tqdm(iter_raw("events"), desc="events", unit="rec"):
        payload = record.get("payload")
        if not isinstance(payload, list):
            continue
        fetched_at = record.get("fetched_at")

        for event in payload:
            if not isinstance(event, dict) or not event.get("id"):
                continue

            venue = event.get("venue") or {}
            vid = venue_key(venue)
            conn.execute(
                """INSERT OR IGNORE INTO venues
                     (venue_id, name, city, region, country, latitude, longitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (vid, venue.get("name"), venue.get("city"), venue.get("region"),
                 venue.get("country"), venue.get("latitude"), venue.get("longitude")),
            )

            local = event.get("datetime")
            conn.execute(
                """INSERT INTO events
                     (event_id, headliner_id, venue_id, datetime_local, datetime_utc,
                      on_sale_datetime, title, description, url, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(event_id) DO UPDATE SET
                     datetime_local = excluded.datetime_local,
                     datetime_utc = excluded.datetime_utc,
                     fetched_at = excluded.fetched_at""",
                (
                    str(event["id"]),
                    str(event.get("artist_id")) if event.get("artist_id") else None,
                    vid,
                    local,
                    to_utc(local, venue.get("latitude"), venue.get("longitude")),
                    event.get("on_sale_datetime"),
                    event.get("title"),
                    event.get("description"),
                    event.get("url"),
                    fetched_at,
                ),
            )

            # enumerate gives us (index, value) pairs — index 0 is the headliner.
            for position, artist_name in enumerate(event.get("lineup") or []):
                conn.execute(
                    """INSERT OR IGNORE INTO event_lineup
                         (event_id, artist_name, position) VALUES (?, ?, ?)""",
                    (str(event["id"]), (artist_name or "").strip(), position),
                )

            for offer in event.get("offers") or []:
                conn.execute(
                    """INSERT OR IGNORE INTO offers
                         (event_id, type, url, status, observed_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(event["id"]), offer.get("type"), offer.get("url"),
                     offer.get("status"), fetched_at),
                )
            count += 1
    return count


def resolve_lineup_ids(conn) -> int:
    """
    Fill event_lineup.artist_id by matching names against the artists table.

    This is exact matching only — deliberately conservative. Fuzzy matching belongs
    in its own module where you can evaluate it, not buried in the normaliser.
    """
    cur = conn.execute(
        """UPDATE event_lineup
           SET artist_id = (
               SELECT a.artist_id FROM artists a
               WHERE LOWER(TRIM(a.name)) = LOWER(TRIM(event_lineup.artist_name))
               LIMIT 1
           )
           WHERE artist_id IS NULL"""
    )
    return cur.rowcount


def main() -> None:
    with connect() as conn:
        n_artists = normalize_artists(conn)
        n_events = normalize_events(conn)
        n_resolved = resolve_lineup_ids(conn)

        print(f"\nProcessed {n_artists} artist records, {n_events} event records.")
        print(f"Resolved {n_resolved} lineup names to artist IDs.")

        for table in ("artists", "events", "venues", "event_lineup", "artist_snapshots"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<20} {n:>8}")

        unresolved = conn.execute(
            "SELECT COUNT(*) FROM event_lineup WHERE artist_id IS NULL"
        ).fetchone()[0]
        with_mbid = conn.execute(
            "SELECT COUNT(*) FROM artists WHERE mbid IS NOT NULL AND mbid != ''"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]

        print(f"\n  lineup names still unresolved: {unresolved}")
        if total:
            print(f"  mbid coverage: {with_mbid}/{total} = {100 * with_mbid / total:.1f}%")


if __name__ == "__main__":
    main()
