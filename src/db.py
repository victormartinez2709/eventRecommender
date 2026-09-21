"""
Database schema for the Ticketmaster dataset.

Run once to create it:
    python src/db.py
"""

from __future__ import annotations

import sqlite3

from config import DB_PATH

SCHEMA = """
-- ---------------------------------------------------------------------------
-- Venues. Ticketmaster supplies a real venue id, so no name-hashing is needed.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS venues (
    venue_id      TEXT PRIMARY KEY,
    name          TEXT,
    city          TEXT,
    state_code    TEXT,
    country_code  TEXT,
    address       TEXT,
    postal_code   TEXT,
    latitude      REAL,
    longitude     REAL,
    timezone      TEXT,
    market        TEXT,
    dma_id        TEXT,
    url           TEXT,
    fetched_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city, state_code);

-- ---------------------------------------------------------------------------
-- Artists. Ticketmaster calls them "attractions".
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attractions (
    attraction_id   TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    url             TEXT,
    segment_id      TEXT,
    segment_name    TEXT,
    genre_id        TEXT,
    genre_name      TEXT,
    subgenre_id     TEXT,
    subgenre_name   TEXT,
    upcoming_events INTEGER,
    image_url       TEXT,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attractions_name ON attractions(name);
CREATE INDEX IF NOT EXISTS idx_attractions_genre ON attractions(genre_name, subgenre_name);

-- Spotify, MusicBrainz, Last.fm, YouTube, homepage... the join keys to
-- everything outside Ticketmaster.
CREATE TABLE IF NOT EXISTS attraction_links (
    attraction_id TEXT NOT NULL,
    platform      TEXT NOT NULL,
    url           TEXT NOT NULL,
    PRIMARY KEY (attraction_id, platform, url)
);

-- ---------------------------------------------------------------------------
-- Events. The primary unit of this dataset.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    name            TEXT,
    url             TEXT,
    venue_id        TEXT,

    local_date      TEXT,     -- venue-local calendar date, as supplied
    local_time      TEXT,     -- venue-local clock time, as supplied
    datetime_utc    TEXT,     -- the same instant in UTC, supplied by the API
    timezone        TEXT,
    status          TEXT,     -- onsale / offsale / cancelled / postponed / rescheduled

    onsale_start    TEXT,     -- when tickets went on sale: gives announcement lead time
    onsale_end      TEXT,

    price_min       REAL,
    price_max       REAL,
    price_currency  TEXT,

    promoter_name   TEXT,

    -- The primary classification, denormalised for convenient querying.
    -- Every classification an event carries is also in event_classifications.
    segment_id      TEXT,
    segment_name    TEXT,
    genre_id        TEXT,
    genre_name      TEXT,
    subgenre_id     TEXT,
    subgenre_name   TEXT,

    fetched_at      TEXT NOT NULL,
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id)
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(local_date);
CREATE INDEX IF NOT EXISTS idx_events_genre ON events(genre_name, subgenre_name);
CREATE INDEX IF NOT EXISTS idx_events_venue ON events(venue_id);

-- An event may carry more than one classification; keep them all.
CREATE TABLE IF NOT EXISTS event_classifications (
    event_id      TEXT NOT NULL,
    is_primary    INTEGER NOT NULL DEFAULT 0,
    segment_id    TEXT,
    segment_name  TEXT,
    genre_id      TEXT,
    genre_name    TEXT,
    subgenre_id   TEXT,
    subgenre_name TEXT,
    PRIMARY KEY (event_id, segment_id, genre_id, subgenre_id)
);

-- THE LINEUP. One row per artist per event. Two artists sharing an event_id
-- is a co-performance edge.
CREATE TABLE IF NOT EXISTS event_attractions (
    event_id      TEXT NOT NULL,
    attraction_id TEXT NOT NULL,
    position      INTEGER,     -- 0 = first listed, usually the headliner
    PRIMARY KEY (event_id, attraction_id)
);
CREATE INDEX IF NOT EXISTS idx_ea_attraction ON event_attractions(attraction_id);

-- ---------------------------------------------------------------------------
-- The classification taxonomy itself, pulled from /classifications.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS classifications (
    segment_id    TEXT NOT NULL,
    segment_name  TEXT,
    genre_id      TEXT,
    genre_name    TEXT,
    subgenre_id   TEXT,
    subgenre_name TEXT,
    fetched_at    TEXT NOT NULL,
    PRIMARY KEY (segment_id, genre_id, subgenre_id)
);

-- ---------------------------------------------------------------------------
-- What was collected, when, and whether it was complete. The deep-paging cap
-- means a slice returning 1000+ results was truncated, so record it.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS collection_log (
    slice_start    TEXT NOT NULL,
    slice_end      TEXT NOT NULL,
    params         TEXT,
    total_elements INTEGER,
    pages_fetched  INTEGER,
    truncated      INTEGER NOT NULL DEFAULT 0,
    fetched_at     TEXT NOT NULL,
    PRIMARY KEY (slice_start, slice_end, params)
);

-- ---------------------------------------------------------------------------
-- HTTP response cache. Keyed by a hash of the request path and parameters with
-- the API key removed, so re-runs cost no quota and return instantly.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key   TEXT PRIMARY KEY,
    path        TEXT NOT NULL,
    params      TEXT NOT NULL,
    payload     TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    hits        INTEGER NOT NULL DEFAULT 0,
    last_hit_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cache_expiry ON api_cache(expires_at);

-- ---------------------------------------------------------------------------
-- Append-only observation log.
--
-- Ticketmaster is a live ticketing feed, not an archive: events disappear once
-- they are off-sale, and prices and status change while they are listed. The
-- events table holds current state; this table holds every time we saw an
-- event and what it looked like then. It is the only way to recover price
-- movement, sell-outs and cancellations, and it cannot be backfilled.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_observations (
    event_id       TEXT NOT NULL,
    observed_at    TEXT NOT NULL,
    status         TEXT,
    price_min      REAL,
    price_max      REAL,
    lineup_size    INTEGER,
    days_until     INTEGER,      -- days from observation to the event date
    PRIMARY KEY (event_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_obs_event ON event_observations(event_id);

-- ---------------------------------------------------------------------------
-- Cleaning output. One row per event, produced by clean.py. Kept separate from
-- `events` so the raw parse is never overwritten by a cleaning decision.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events_clean (
    event_id         TEXT PRIMARY KEY,
    dedup_group      TEXT NOT NULL,   -- venue + date + normalised headliner
    venue_canonical_id TEXT,          -- same building listed under several ids
    headliner        TEXT,            -- first real artist, junk listings removed
    is_duplicate     INTEGER NOT NULL DEFAULT 0,
    is_cancelled     INTEGER NOT NULL DEFAULT 0,
    genre_clean      TEXT,            -- "None"/"Undefined" collapsed to NULL
    subgenre_clean   TEXT,
    is_electronic    INTEGER NOT NULL DEFAULT 0,
    name_clean       TEXT,
    lineup_size      INTEGER NOT NULL DEFAULT 0,
    lead_time_days   INTEGER,         -- on-sale date to event date
    weekday          INTEGER,
    cleaned_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clean_group ON events_clean(dedup_group);
CREATE INDEX IF NOT EXISTS idx_clean_genre ON events_clean(genre_clean, subgenre_clean);

-- ---------------------------------------------------------------------------
-- Weekly run bookkeeping, and what each run pushed to Supabase.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    api_calls      INTEGER,
    cache_hits     INTEGER,
    events_seen    INTEGER,
    events_new     INTEGER,
    synced_rows    INTEGER,
    notes          TEXT
);
"""



def connect() -> sqlite3.Connection:
    """Open the Ticketmaster database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# CREATE TABLE IF NOT EXISTS does nothing when the table already exists, so a
# new column in SCHEMA never reaches an existing database. These are ALTERed in.
_EXPECTED_COLUMNS = {
    "events_clean": {
        "venue_canonical_id": "TEXT",
        "headliner": "TEXT",
    },
}


def ensure_columns(conn) -> list:
    """Add columns missing from an existing table. Returns what it added."""
    added = []
    for table, columns in _EXPECTED_COLUMNS.items():
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        if not exists:
            continue
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in columns.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                added.append(f"{table}.{col}")
    return added


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        added = ensure_columns(conn)
    if added:
        print(f"Added missing columns: {', '.join(added)}")
    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    init_db()
