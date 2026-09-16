"""
Discovery, stage 1: turn a plain list of artist names into frontier entries.

Why this exists: Bandsintown's website returns HTTP 403 to scripts, so the city
and genre listing pages cannot be used to find artists. The API has no search
either. But every event the API returns includes its full lineup, so a modest
starting list expands on its own once crawl.py begins following those lineups.

Edit seeds.txt, then run:
    python src/seed_names.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from bit_client import BandsintownClient
from config import PROJECT_ROOT
from db import connect

SEED_FILE = PROJECT_ROOT / "seeds.txt"


def read_seeds() -> list[tuple[str, str]]:
    """
    Parse the seed file into (lookup_key, label) pairs.

    Two accepted line formats:
        15559410 | MGNA Crrrta     -> looked up by ID (exact, no name matching)
        MGNA Crrrta                -> looked up by name

    Blank lines and lines starting with # are ignored.
    """
    if not SEED_FILE.exists():
        raise SystemExit(f"No seed file at {SEED_FILE}. Create it, one artist per line.")

    seeds = []
    for line in SEED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            left, right = line.split("|", 1)
            left, right = left.strip(), right.strip()
            if left.isdigit():
                seeds.append((f"id_{left}", right or left))
                continue
        seeds.append((line, line))
    return seeds


def main() -> None:
    seeds = read_seeds()
    by_id = sum(1 for k, _ in seeds if k.startswith("id_"))
    print(f"{len(seeds)} seeds in {SEED_FILE.name} ({by_id} by ID, {len(seeds) - by_id} by name)")

    client = BandsintownClient()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    found, missing, queued = 0, [], 0

    for key, label in seeds:
        status, payload = client.get_artist(key)

        # An unknown artist comes back as HTTP 200 with an empty body, not a 404.
        if status != 200 or not isinstance(payload, dict) or not payload.get("id"):
            missing.append(label)
            print(f"  not found : {label}")
            continue

        artist_id = str(payload["id"])
        real_name = payload.get("name", label)
        trackers = payload.get("tracker_count", 0)
        print(f"  found     : {real_name:<32} id={artist_id:<12} followers={trackers}")
        found += 1

        with connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO seed_discovery
                   (artist_id, artist_name, city_slug, genre_slug, discovered_at)
                   VALUES (?, ?, 'manual-seed', 'electronic', ?)""",
                (artist_id, real_name, now),
            )
            # Queue both the profile and the event history at depth 0. crawl.py
            # will expand outward from here using each event's lineup.
            for kind in ("artist", "events"):
                cur = conn.execute(
                    """INSERT OR IGNORE INTO frontier (key, kind, depth, status, updated_at)
                       VALUES (?, ?, 0, 'pending', ?)""",
                    (f"id_{artist_id}", kind, now),
                )
                queued += cur.rowcount

    print(f"\n{found} found, {len(missing)} not found, {queued} new frontier rows queued.")
    if missing:
        print("\nNot found — check the spelling against the artist's Bandsintown page:")
        for label in missing:
            print(f"  {label}")


if __name__ == "__main__":
    main()
