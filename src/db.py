"""
Database schema and connection helper.

Run this file directly once to create the database:
    python src/db.py
"""

from __future__ import annotations
import sqlite3

from config import DB_PATH

# A "schema" is just the set of CREATE TABLE statements describing your tables.
# IF NOT EXISTS means running this script twice is harmless.
SCHEMA = """
-- ---------------------------------------------------------------------------
-- Crawl bookkeeping: which artists we still need to fetch.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS frontier (
    key         TEXT NOT NULL,      -- 'id_15390659' or a raw artist name
    kind        TEXT NOT NULL,      -- 'artist' (profile) or 'events'
    depth       INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|done|not_found|error
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    updated_at  TEXT,
    -- Each artist needs TWO rows: one to fetch the profile, one to fetch events.
    -- The key alone must NOT be the primary key, or the second row is silently
    -- dropped by INSERT OR IGNORE and no events are ever collected.
    PRIMARY KEY (key, kind)
);
CREATE INDEX IF NOT EXISTS idx_frontier_status ON frontier(status, kind);

-- ---------------------------------------------------------------------------
-- Core entities
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artists (
    artist_id          TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    mbid               TEXT,        -- MusicBrainz ID: the join key to everything else
    url                TEXT,
    image_url          TEXT,
    facebook_page_url  TEXT,
    first_seen_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artists_mbid ON artists(mbid);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);

-- Append-only time series. tracker_count is a snapshot when you ask for it, so the
-- ONLY way to have a history is to sample it repeatedly. Start this early.
CREATE TABLE IF NOT EXISTS artist_snapshots (
    artist_id             TEXT NOT NULL,
    observed_at           TEXT NOT NULL,
    tracker_count         INTEGER,
    upcoming_event_count  INTEGER,
    PRIMARY KEY (artist_id, observed_at)
);

-- Bandsintown gives no venue ID, so we build one by hashing a normalised name+place.
CREATE TABLE IF NOT EXISTS venues (
    venue_id   TEXT PRIMARY KEY,
    name       TEXT,
    city       TEXT,
    region     TEXT,
    country    TEXT,
    latitude   REAL,
    longitude  REAL
);
CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city, region);

CREATE TABLE IF NOT EXISTS events (
    event_id          TEXT PRIMARY KEY,
    headliner_id      TEXT,      -- the artist whose feed this event came from
    venue_id          TEXT,
    datetime_local    TEXT,      -- exactly as Bandsintown gave it: LOCAL venue time
    datetime_utc      TEXT,      -- computed by us from the venue coordinates
    on_sale_datetime  TEXT,
    title             TEXT,
    description       TEXT,
    url               TEXT,
    fetched_at        TEXT NOT NULL,
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id)
);
CREATE INDEX IF NOT EXISTS idx_events_datetime ON events(datetime_local);
CREATE INDEX IF NOT EXISTS idx_events_venue ON events(venue_id);

-- THE GRAPH. One row per (event, artist-on-that-bill). Two artists sharing an
-- event_id is a co-billing edge, and that is the core signal of the whole thesis.
CREATE TABLE IF NOT EXISTS event_lineup (
    event_id     TEXT NOT NULL,
    artist_name  TEXT NOT NULL,
    artist_id    TEXT,          -- NULL until we resolve the name to an ID
    position     INTEGER,       -- 0 = first listed (usually the headliner)
    PRIMARY KEY (event_id, artist_name)
);
CREATE INDEX IF NOT EXISTS idx_lineup_artist ON event_lineup(artist_id);

CREATE TABLE IF NOT EXISTS offers (
    event_id     TEXT NOT NULL,
    type         TEXT,
    url          TEXT,
    status       TEXT,          -- 'available' / 'sold out' — a real demand signal
    observed_at  TEXT NOT NULL,
    PRIMARY KEY (event_id, type, observed_at)
);

-- Genre/tags pulled from Last.fm, MusicBrainz, Discogs. Kept raw and separate,
-- because the mapping from messy tags to clean genres is a modelling decision
-- you will change your mind about several times.
CREATE TABLE IF NOT EXISTS artist_tags (
    artist_id   TEXT NOT NULL,
    source      TEXT NOT NULL,   -- 'lastfm' | 'musicbrainz' | 'discogs' | 'bandsintown'
    tag         TEXT NOT NULL,
    weight      REAL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (artist_id, source, tag)
);

-- Which artists we discovered from which Bandsintown city+genre page. This is how
-- you know an artist is "a Colorado electronic artist" in the first place.
CREATE TABLE IF NOT EXISTS seed_discovery (
    artist_id     TEXT NOT NULL,
    artist_name   TEXT,
    city_slug     TEXT NOT NULL,
    genre_slug    TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    PRIMARY KEY (artist_id, city_slug, genre_slug)
);
"""


def connect() -> sqlite3.Connection:
    """Open the database with settings that make life easier."""
    conn = sqlite3.connect(DB_PATH)
    # Rows come back as objects you can index by column name: row["name"]
    # instead of row[1]. Much less error-prone than counting columns.
    conn.row_factory = sqlite3.Row
    # WAL = write-ahead logging. Lets you read the DB (e.g. from a notebook)
    # while the crawler is still writing to it.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_frontier(conn) -> bool:
    """
    Repair the original frontier table, which declared `key TEXT PRIMARY KEY`.

    Each artist needs two rows (one for the profile, one for the events). With
    the key alone as the primary key the second row collided with the first and
    was silently discarded by INSERT OR IGNORE, so no events were ever queued.

    Existing progress is preserved: rows are copied into the corrected table.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='frontier'"
    ).fetchone()
    if not row or "PRIMARY KEY (key, kind)" in row[0]:
        return False  # absent, or already correct

    print("  migrating frontier table to a composite primary key...")
    conn.executescript("""
        ALTER TABLE frontier RENAME TO frontier_legacy;

        CREATE TABLE frontier (
            key         TEXT NOT NULL,
            kind        TEXT NOT NULL,
            depth       INTEGER NOT NULL DEFAULT 0,
            status      TEXT NOT NULL DEFAULT 'pending',
            attempts    INTEGER NOT NULL DEFAULT 0,
            last_error  TEXT,
            updated_at  TEXT,
            PRIMARY KEY (key, kind)
        );

        INSERT OR IGNORE INTO frontier
            (key, kind, depth, status, attempts, last_error, updated_at)
        SELECT key, kind, depth, status, attempts, last_error, updated_at
        FROM frontier_legacy;

        DROP TABLE frontier_legacy;
    """)
    n = conn.execute("SELECT COUNT(*) FROM frontier").fetchone()[0]
    print(f"  migration done, {n} rows preserved")
    return True


def init_db() -> None:
    """Create every table, and repair the old frontier schema. Safe to re-run."""
    with connect() as conn:
        _migrate_frontier(conn)
        conn.executescript(SCHEMA)
    print(f"Database ready at {DB_PATH}")


# This guard means the code below runs only when you execute this file directly
# (`python src/db.py`), not when another module does `from db import connect`.
if __name__ == "__main__":
    init_db()
