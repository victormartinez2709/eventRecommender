"""
Build the seed list of Colorado electronic artists.

Why this file exists: the Bandsintown *API* has no search and no genre filter, so
you cannot ask it "give me electronic artists in Colorado". But the Bandsintown
*website* does have city + genre pages, and it server-renders a schema.org JSON-LD
block listing every event on the page — including a link to each artist's page,
which contains their numeric Bandsintown ID.

So: scrape the website to discover WHO, then use the API to get the structured data.

Verified page structure (checked live):
    <script type="application/ld+json">  -> block 0 is the City
    <script type="application/ld+json">  -> block 1 is a JSON ARRAY of MusicEvent
Each MusicEvent has:
    name       "CYTRUS @ Cervantes' Masterpiece Ballroom"
    startDate  "2026-09-13T20:00:00"
    url        ".../e/1039165156-cytrus-at-..."
    location   {"name": "Cervantes' Masterpiece Ballroom", ...}
    performer  {"name": "CYTRUS"}
    organizer  {"name": "CYTRUS", "url": ".../a/15390659-cytrus?came_from=209"}
                                            ^^^^^^^^ the artist ID we want

Run:
    python src/seeds.py                # this-week pages for every CO city
    python src/seeds.py --range all-dates
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import random
import re
import time

import requests
from bs4 import BeautifulSoup

from config import CO_CITIES, GENRES, USER_AGENT
from db import connect

CITY_URL = "https://www.bandsintown.com/c/{city}/{date_range}/genre/{genre}"

# Matches the artist ID in a URL like .../a/15390659-cytrus?came_from=209
ARTIST_ID_RE = re.compile(r"/a/(\d+)")


def fetch_page(city: str, genre: str, date_range: str) -> str | None:
    """Download one city+genre listing page as HTML."""
    url = CITY_URL.format(city=city, genre=genre, date_range=date_range)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as exc:
        print(f"  ! network error for {city}: {exc}")
        return None
    if resp.status_code != 200:
        print(f"  ! HTTP {resp.status_code} for {city}/{genre}/{date_range}")
        return None
    return resp.text


def extract_events(html: str) -> list[dict]:
    """
    Pull the MusicEvent list out of the page's JSON-LD.

    We look at every ld+json block rather than assuming it is always the second
    one — that assumption would break silently the day they add another block.
    """
    soup = BeautifulSoup(html, "lxml")
    events: list[dict] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue  # some blocks are malformed or empty; skip quietly

        # Normalise: a block is either one object or a list of objects.
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "MusicEvent":
                events.append(item)

    return events


def parse_artist(event: dict) -> tuple[str, str] | None:
    """Return (artist_id, artist_name) from one MusicEvent, or None if absent."""
    organizer = event.get("organizer") or {}
    performer = event.get("performer") or {}

    # .get chained with "or {}" guards against the key existing but being null.
    url = organizer.get("url") or ""
    match = ARTIST_ID_RE.search(url)
    if not match:
        return None

    artist_id = match.group(1)          # group(1) is the (\d+) capture
    name = organizer.get("name") or performer.get("name") or ""
    return artist_id, name.strip()


def save_seeds(rows: list[tuple[str, str, str, str]]) -> tuple[int, int]:
    """
    Write discoveries to seed_discovery, and queue each new artist in the frontier.
    Returns (rows_recorded, artists_newly_queued).
    """
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    queued = 0

    with connect() as conn:
        for artist_id, name, city, genre in rows:
            # INSERT OR IGNORE: if this (artist, city, genre) is already recorded,
            # do nothing instead of raising a duplicate-key error. This is what
            # makes the whole script safe to re-run every week.
            conn.execute(
                """INSERT OR IGNORE INTO seed_discovery
                   (artist_id, artist_name, city_slug, genre_slug, discovered_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (artist_id, name, city, genre, now),
            )
            for kind in ("artist", "events"):
                cur = conn.execute(
                    """INSERT OR IGNORE INTO frontier (key, kind, depth, status, updated_at)
                       VALUES (?, ?, 0, 'pending', ?)""",
                    (f"id_{artist_id}", kind, now),
                )
                queued += cur.rowcount  # 1 if inserted, 0 if it already existed

    return len(rows), queued


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--range",
        default="this-week",
        choices=["this-week", "this-month", "all-dates"],
        help="Which Bandsintown date window to scrape.",
    )
    parser.add_argument("--genre", default=None, help="Override the genre slug.")
    args = parser.parse_args()

    genres = [args.genre] if args.genre else GENRES
    all_rows: list[tuple[str, str, str, str]] = []

    for city in CO_CITIES:
        for genre in genres:
            html = fetch_page(city, genre, args.range)
            if not html:
                continue

            events = extract_events(html)
            found = 0
            for event in events:
                parsed = parse_artist(event)
                if parsed:
                    artist_id, name = parsed
                    all_rows.append((artist_id, name, city, genre))
                    found += 1

            print(f"  {city:<24} {genre:<12} {len(events):>3} events, {found:>3} with artist IDs")
            # Be a good citizen: these are normal web pages, not an API.
            time.sleep(1.5 + random.uniform(0, 1.0))

    recorded, queued = save_seeds(all_rows)
    unique = len({r[0] for r in all_rows})
    print(
        f"\nDone. {recorded} discoveries ({unique} unique artists). "
        f"{queued} new frontier rows queued."
    )


if __name__ == "__main__":
    main()
