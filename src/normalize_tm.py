"""
Turn the raw Ticketmaster responses into clean relational tables.

Kept separate from collection on purpose: this file makes no API calls. It only
re-reads the files already in raw/, so a parsing correction costs one re-run
rather than another day of quota.

    python src/normalize_tm.py
"""

from __future__ import annotations

import datetime as dt
import gzip
import json

from tqdm import tqdm

from config import RAW_DIR
from db import connect, init_db


def iter_raw(kind: str):
    root = RAW_DIR / kind
    if not root.exists():
        return
    for path in sorted(root.rglob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


def cls_parts(classification: dict) -> tuple:
    """Pull (segment, genre, subGenre) ids and names out of one classification."""
    def part(key):
        node = classification.get(key) or {}
        return node.get("id"), node.get("name")
    return part("segment") + part("genre") + part("subGenre")


def save_venue(conn, venue: dict, now: str) -> str | None:
    vid = venue.get("id")
    if not vid:
        return None
    loc = venue.get("location") or {}

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    conn.execute(
        """INSERT INTO venues (venue_id, name, city, state_code, country_code,
             address, postal_code, latitude, longitude, timezone, market, dma_id,
             url, fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(venue_id) DO UPDATE SET
             name = excluded.name,
             latitude = COALESCE(excluded.latitude, venues.latitude),
             longitude = COALESCE(excluded.longitude, venues.longitude),
             fetched_at = excluded.fetched_at""",
        (vid, venue.get("name"),
         (venue.get("city") or {}).get("name"),
         (venue.get("state") or {}).get("stateCode"),
         (venue.get("country") or {}).get("countryCode"),
         (venue.get("address") or {}).get("line1"),
         venue.get("postalCode"),
         num(loc.get("latitude")), num(loc.get("longitude")),
         venue.get("timezone"),
         ((venue.get("markets") or [{}])[0]).get("name"),
         ((venue.get("dmas") or [{}])[0]).get("id"),
         venue.get("url"), now))
    return vid


def save_attraction(conn, attraction: dict, now: str) -> str | None:
    aid = attraction.get("id")
    if not aid:
        return None
    cls = (attraction.get("classifications") or [{}])[0]
    seg_id, seg_name, gen_id, gen_name, sub_id, sub_name = cls_parts(cls)
    images = attraction.get("images") or []

    conn.execute(
        """INSERT INTO attractions (attraction_id, name, url, segment_id, segment_name,
             genre_id, genre_name, subgenre_id, subgenre_name, upcoming_events,
             image_url, first_seen_at, last_seen_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(attraction_id) DO UPDATE SET
             name = excluded.name,
             genre_name = COALESCE(excluded.genre_name, attractions.genre_name),
             subgenre_name = COALESCE(excluded.subgenre_name, attractions.subgenre_name),
             upcoming_events = COALESCE(excluded.upcoming_events, attractions.upcoming_events),
             last_seen_at = excluded.last_seen_at""",
        (aid, attraction.get("name", ""), attraction.get("url"),
         seg_id, seg_name, gen_id, gen_name, sub_id, sub_name,
         (attraction.get("upcomingEvents") or {}).get("_total"),
         images[0].get("url") if images else None,
         now, now))

    # externalLinks is a dict of platform -> [ {url: ...}, ... ]
    for platform, entries in (attraction.get("externalLinks") or {}).items():
        for entry in entries or []:
            url = entry.get("url") if isinstance(entry, dict) else None
            if url:
                conn.execute(
                    """INSERT OR IGNORE INTO attraction_links (attraction_id, platform, url)
                       VALUES (?,?,?)""", (aid, platform, url))
    return aid


def save_event(conn, event: dict, now: str) -> bool:
    eid = event.get("id")
    if not eid:
        return False

    embedded = event.get("_embedded") or {}
    venues = embedded.get("venues") or []
    venue_id = save_venue(conn, venues[0], now) if venues else None

    start = (event.get("dates") or {}).get("start") or {}
    status = ((event.get("dates") or {}).get("status") or {}).get("code")
    tz = (event.get("dates") or {}).get("timezone")

    public = ((event.get("sales") or {}).get("public") or {})
    prices = event.get("priceRanges") or []
    price = prices[0] if prices else {}

    classifications = event.get("classifications") or []
    primary = classifications[0] if classifications else {}
    seg_id, seg_name, gen_id, gen_name, sub_id, sub_name = cls_parts(primary)

    conn.execute(
        """INSERT INTO events (event_id, name, url, venue_id, local_date, local_time,
             datetime_utc, timezone, status, onsale_start, onsale_end,
             price_min, price_max, price_currency, promoter_name,
             segment_id, segment_name, genre_id, genre_name, subgenre_id,
             subgenre_name, fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(event_id) DO UPDATE SET
             status = excluded.status,
             price_min = COALESCE(excluded.price_min, events.price_min),
             price_max = COALESCE(excluded.price_max, events.price_max),
             fetched_at = excluded.fetched_at""",
        (eid, event.get("name"), event.get("url"), venue_id,
         start.get("localDate"), start.get("localTime"), start.get("dateTime"),
         tz, status, public.get("startDateTime"), public.get("endDateTime"),
         price.get("min"), price.get("max"), price.get("currency"),
         (event.get("promoter") or {}).get("name"),
         seg_id, seg_name, gen_id, gen_name, sub_id, sub_name, now))

    for i, cls in enumerate(classifications):
        s_id, s_nm, g_id, g_nm, sb_id, sb_nm = cls_parts(cls)
        conn.execute(
            """INSERT OR IGNORE INTO event_classifications
               (event_id, is_primary, segment_id, segment_name, genre_id,
                genre_name, subgenre_id, subgenre_name)
               VALUES (?,?,?,?,?,?,?,?)""",
            (eid, 1 if i == 0 else 0, s_id, s_nm, g_id, g_nm, sb_id, sb_nm))

    for position, attraction in enumerate(embedded.get("attractions") or []):
        aid = save_attraction(conn, attraction, now)
        if aid:
            conn.execute(
                """INSERT OR IGNORE INTO event_attractions (event_id, attraction_id, position)
                   VALUES (?,?,?)""", (eid, aid, position))
    return True


def save_taxonomy(conn, payload: dict, now: str) -> int:
    n = 0
    for entry in ((payload.get("_embedded") or {}).get("classifications") or []):
        segment = entry.get("segment") or {}
        seg_id, seg_name = segment.get("id"), segment.get("name")
        if not seg_id:
            continue
        genres = ((segment.get("_embedded") or {}).get("genres")) or [{}]
        for genre in genres:
            subs = ((genre.get("_embedded") or {}).get("subgenres")) or [{}]
            for sub in subs:
                conn.execute(
                    """INSERT OR IGNORE INTO classifications
                       (segment_id, segment_name, genre_id, genre_name,
                        subgenre_id, subgenre_name, fetched_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (seg_id, seg_name, genre.get("id") or "", genre.get("name"),
                     sub.get("id") or "", sub.get("name"), now))
                n += 1
    return n


def main() -> None:
    init_db()
    events_seen = taxonomy_rows = 0

    with connect() as conn:
        for record in tqdm(iter_raw("events"), desc="events", unit="page"):
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            now = record.get("fetched_at")
            for event in ((payload.get("_embedded") or {}).get("events") or []):
                if save_event(conn, event, now):
                    events_seen += 1

        for record in tqdm(iter_raw("classifications"), desc="taxonomy", unit="page"):
            payload = record.get("payload")
            if isinstance(payload, dict):
                taxonomy_rows += save_taxonomy(conn, payload, record.get("fetched_at"))

        print(f"\nProcessed {events_seen} event records, {taxonomy_rows} taxonomy rows.\n")

        for table in ("events", "venues", "attractions", "event_attractions",
                      "attraction_links", "event_classifications", "classifications"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<24} {n:>8}")

        print()
        rows = conn.execute(
            """SELECT genre_name, COUNT(*) n FROM events
               WHERE genre_name IS NOT NULL
               GROUP BY genre_name ORDER BY n DESC LIMIT 10""").fetchall()
        if rows:
            print("  top genres by event count:")
            for r in rows:
                print(f"    {r['genre_name']:<28} {r['n']}")

        truncated = conn.execute(
            "SELECT COUNT(*) FROM collection_log WHERE truncated = 1").fetchone()[0]
        if truncated:
            print(f"\n  WARNING: {truncated} date slice(s) hit the 1000-item paging cap "
                  f"and are incomplete.")


if __name__ == "__main__":
    main()
