"""
Second data source: MusicBrainz.

Bandsintown gives us artists but not their events, and no genre at all.
MusicBrainz fills both gaps and is completely open -- no key, no registration,
CC0 data, and it carries an `area` field so artists can be located geographically.

Two modes:

    python src/enrich_musicbrainz.py enrich
        For every Bandsintown artist, pull MusicBrainz metadata: genres, tags,
        area, country, artist type, and active years. Uses the mbid when
        Bandsintown supplied one, and falls back to a name search when it did not.

    python src/enrich_musicbrainz.py colorado
        Search MusicBrainz for artists whose area is in Colorado. This is an
        independent sample, not derived from Bandsintown at all, which makes it
        a genuine second source rather than an annotation of the first.

MusicBrainz asks for at most one request per second and a descriptive
User-Agent. Both are respected below.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.parse

import requests

from config import CONTACT_EMAIL
from db import connect

BASE = "https://musicbrainz.org/ws/2"
UA = f"CU-Boulder-CSCI5612-project/0.1 ( {CONTACT_EMAIL} )"
MIN_INTERVAL = 1.3  # MusicBrainz allows ~1 req/sec; leave real headroom

SCHEMA = """
CREATE TABLE IF NOT EXISTS artists_mb (
    artist_id       TEXT PRIMARY KEY,   -- the Bandsintown id, so it joins to artists
    mbid            TEXT,
    mb_name         TEXT,
    mb_type         TEXT,               -- Person / Group / Orchestra ...
    country         TEXT,
    area            TEXT,
    begin_area      TEXT,
    life_begin      TEXT,
    life_end        TEXT,
    match_method    TEXT,               -- 'mbid' (exact) or 'name-search' (fuzzy)
    match_score     INTEGER,            -- search score, NULL when matched by mbid
    fetched_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mb_colorado_artists (
    mbid            TEXT PRIMARY KEY,
    name            TEXT,
    mb_type         TEXT,
    area            TEXT,
    begin_area      TEXT,
    life_begin      TEXT,
    score           INTEGER,
    query_area      TEXT,
    is_colorado     INTEGER NOT NULL DEFAULT 0,  -- 1 = area really is in Colorado
    fetched_at      TEXT NOT NULL
);
"""

def ensure_columns(conn) -> None:
    """
    Add columns that were introduced after a table was first created.

    CREATE TABLE IF NOT EXISTS does nothing when the table already exists, so a
    new column in SCHEMA never reaches a database built by an earlier version.
    """
    wanted = {"mb_colorado_artists": [("is_colorado", "INTEGER NOT NULL DEFAULT 0")]}
    for table, cols in wanted.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue  # table does not exist yet; SCHEMA will create it correctly
        for name, decl in cols:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                print(f"  added missing column {table}.{name}")


_session = requests.Session()
_session.headers["User-Agent"] = UA
_last = [0.0]


def get(path: str, params: dict) -> dict | None:
    """One rate-limited GET against the MusicBrainz web service."""
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()

    params = dict(params)
    params["fmt"] = "json"
    try:
        r = _session.get(f"{BASE}{path}", params=params, timeout=30)
    except requests.RequestException as exc:
        print(f"    network error: {exc}")
        return None

    # 503 is MusicBrainz throttling, not a real failure. Back off and retry.
    for attempt in range(1, 4):
        if r.status_code != 503:
            break
        time.sleep(3 * attempt)
        _last[0] = time.monotonic()
        try:
            r = _session.get(f"{BASE}{path}", params=params, timeout=30)
        except requests.RequestException:
            return None

    if r.status_code != 200:
        print(f"    HTTP {r.status_code} (gave up)")
        return None
    try:
        return r.json()
    except ValueError:
        return None


def _area(obj, key) -> str | None:
    node = obj.get(key) or {}
    return node.get("name")


def save_tags(conn, artist_id: str, payload: dict, now: str) -> int:
    """Store genres and folksonomy tags. Genres are the curated vocabulary."""
    n = 0
    for genre in payload.get("genres") or []:
        conn.execute(
            """INSERT OR IGNORE INTO artist_tags (artist_id, source, tag, weight, fetched_at)
               VALUES (?, 'musicbrainz-genre', ?, ?, ?)""",
            (artist_id, genre.get("name"), genre.get("count"), now))
        n += 1
    for tag in payload.get("tags") or []:
        conn.execute(
            """INSERT OR IGNORE INTO artist_tags (artist_id, source, tag, weight, fetched_at)
               VALUES (?, 'musicbrainz-tag', ?, ?, ?)""",
            (artist_id, tag.get("name"), tag.get("count"), now))
        n += 1
    return n


def enrich() -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with connect() as conn:
        conn.executescript(SCHEMA)
        ensure_columns(conn)
        rows = conn.execute(
            "SELECT artist_id, name, mbid FROM artists ORDER BY name").fetchall()

    print(f"{len(rows)} Bandsintown artists to enrich")
    with_mbid = sum(1 for r in rows if r["mbid"])
    print(f"  {with_mbid} have a MusicBrainz id, {len(rows) - with_mbid} need a name search\n")

    hit = miss = tags_total = 0

    for row in rows:
        artist_id, name, mbid = row["artist_id"], row["name"], row["mbid"]
        payload, method, score = None, None, None

        if mbid:
            payload = get(f"/artist/{mbid}", {"inc": "tags+genres"})
            if payload and payload.get("id"):
                method = "mbid"

        if payload is None or not payload.get("id"):
            # Fall back to a name search. Exact-phrase query, take the top hit,
            # and record the score so weak matches can be filtered later.
            res = get("/artist", {"query": f'artist:"{name}"', "limit": 3})
            cands = (res or {}).get("artists") or []
            if cands and cands[0].get("score", 0) >= 90:
                best = cands[0]
                payload = get(f"/artist/{best['id']}", {"inc": "tags+genres"})
                method, score = "name-search", best.get("score")

        if not payload or not payload.get("id"):
            miss += 1
            print(f"  no match : {name}")
            continue

        hit += 1
        with connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO artists_mb
                   (artist_id, mbid, mb_name, mb_type, country, area, begin_area,
                    life_begin, life_end, match_method, match_score, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (artist_id, payload.get("id"), payload.get("name"),
                 payload.get("type"), payload.get("country"),
                 _area(payload, "area"), _area(payload, "begin-area"),
                 (payload.get("life-span") or {}).get("begin"),
                 (payload.get("life-span") or {}).get("end"),
                 method, score, now))
            tags_total += save_tags(conn, artist_id, payload, now)

        area = _area(payload, "area") or _area(payload, "begin-area") or "?"
        ngen = len(payload.get("genres") or [])
        print(f"  {name:<28} {method:<12} area={area:<22} genres={ngen}")

    print(f"\n{hit} matched, {miss} unmatched, {tags_total} tag/genre rows written.")


# Multi-word values MUST be quoted. Unquoted, `area:Fort Collins` tokenises and
# matches any artist whose area contains "Collins", which returned 2012 results.
COLORADO_QUERIES = [
    'area:"Colorado"',
    'beginarea:"Colorado"',
    'area:"Denver"',
    'beginarea:"Denver"',
    'area:"Boulder"',
    'area:"Colorado Springs"',
    'area:"Fort Collins"',
    'area:"Aspen"',
]

# Used to separate genuine Colorado matches from search noise (Denver PA, etc.)
CO_PLACES = ("colorado", "denver", "boulder", "aurora", "lakewood", "fort collins",
             "colorado springs", "pueblo", "greeley", "longmont", "loveland",
             "arvada", "westminster", "littleton", "englewood", "golden",
             "aspen", "vail", "durango", "telluride", "breckenridge", "steamboat")


# Other US states that contain a town sharing a name with a Colorado one
# (Denver PA, Boulder NV, Aurora IL, Golden MS...). If one of these is named,
# the match is not ours.
OTHER_STATES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana",
    "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
)


def is_colorado(area: str | None, begin_area: str | None) -> bool:
    """True when the area names a Colorado place and no competing US state."""
    blob = f"{area or ''} {begin_area or ''}".lower()
    if not any(place in blob for place in CO_PLACES):
        return False
    if "colorado" in blob:          # explicit wins over any other token
        return True
    return not any(state in blob for state in OTHER_STATES)


def colorado() -> None:
    """Independent sample: artists MusicBrainz places in Colorado."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with connect() as conn:
        conn.executescript(SCHEMA)
        ensure_columns(conn)

    total_new = 0
    for query in COLORADO_QUERIES:
        offset, added, reported = 0, 0, None
        while True:
            res = get("/artist", {"query": query, "limit": 100, "offset": offset})
            if not res:
                break
            if reported is None:
                reported = res.get("count", 0)
                print(f"  {query:<26} {reported} results")
            artists = res.get("artists") or []
            if not artists:
                break
            with connect() as conn:
                for a in artists:
                    cur = conn.execute(
                        """INSERT OR IGNORE INTO mb_colorado_artists
                           (mbid, name, mb_type, area, begin_area, life_begin,
                            score, query_area, fetched_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (a.get("id"), a.get("name"), a.get("type"),
                         _area(a, "area"), _area(a, "begin-area"),
                         (a.get("life-span") or {}).get("begin"),
                         a.get("score"), query, now))
                    added += cur.rowcount
            offset += len(artists)
            if offset >= min(reported or 0, 500):   # cap per query
                break
        total_new += added
        print(f"    -> {added} new")

    with connect() as conn:
        rows = conn.execute(
            "SELECT mbid, area, begin_area FROM mb_colorado_artists").fetchall()
        real = [r["mbid"] for r in rows if is_colorado(r["area"], r["begin_area"])]
        for mbid in real:
            conn.execute(
                "UPDATE mb_colorado_artists SET is_colorado = 1 WHERE mbid = ?", (mbid,))

    print(f"\n{total_new} new rows, {len(rows)} total returned by the searches.")
    print(f"{len(real)} of those are genuinely in a Colorado area "
          f"({100 * len(real) / max(len(rows), 1):.1f}%).")
    print("The remainder are search noise (Denver PA, Boulder City NV, and so on)")
    print("and are kept with is_colorado = 0 so the filtering is documented.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "enrich"
    if mode == "enrich":
        enrich()
    elif mode == "colorado":
        colorado()
    else:
        raise SystemExit("usage: python src/enrich_musicbrainz.py [enrich|colorado]")
