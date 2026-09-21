"""
Push the cleaned tables to Supabase.

    python src/supabase_sync.py            # sync everything
    python src/supabase_sync.py --check    # connection test only
    python src/supabase_sync.py --dry-run  # show what would be sent

Plain HTTP against PostgREST rather than the supabase-py client, which keeps
the dependency list short. Current state is upserted so re-running is
harmless; observations are appended, because their whole purpose is to record
what a thing looked like at one moment.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

import requests

from config import SUPABASE_KEY, SUPABASE_URL
from db import connect

CHUNK = 500          # rows per request; Supabase handles this comfortably
TIMEOUT = 60


def headers(upsert: bool = True) -> dict:
    """PostgREST auth, plus the header that turns an insert into an upsert."""
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if upsert:
        h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return h


def require_supabase() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit(
            "SUPABASE_URL or SUPABASE_KEY is not set.\n"
            "Add both to .env. Find them in your Supabase project under\n"
            "Settings -> API. Use the service_role key for this ingest script,\n"
            "and never commit it."
        )
    if "paste" in (SUPABASE_KEY or "").lower():
        raise SystemExit("SUPABASE_KEY still contains the placeholder from .env.example.")


def push(table: str, rows: list[dict], upsert: bool = True,
         on_conflict: str | None = None, dry_run: bool = False) -> int:
    """Send rows to one table in chunks. Returns how many were sent."""
    if not rows:
        print(f"  {table:<22} nothing to send")
        return 0

    if dry_run:
        print(f"  {table:<22} would send {len(rows)} rows; first row:")
        print("    " + json.dumps(rows[0], default=str)[:220])
        return 0

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"on_conflict": on_conflict} if on_conflict else {}
    sent = 0

    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        resp = requests.post(url, params=params, headers=headers(upsert),
                             data=json.dumps(chunk, default=str), timeout=TIMEOUT)
        if resp.status_code >= 300:
            print(f"  {table:<22} HTTP {resp.status_code}")
            print(f"    {resp.text[:400]}")
            raise SystemExit(
                f"\nSync aborted on {table}. Nothing after this point was sent.\n"
                f"If the message mentions a missing relation, run supabase_schema.sql\n"
                f"in the Supabase SQL editor first."
            )
        sent += len(chunk)
        print(f"  {table:<22} {sent}/{len(rows)}", end="\r")

    print(f"  {table:<22} {sent} rows sent      ")
    return sent


def rows_from(conn, sql: str, mapper) -> list[dict]:
    return [mapper(r) for r in conn.execute(sql)]


def none_if_blank(v):
    return None if v in ("", None) else v


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="connection test only")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    require_supabase()

    if args.check:
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/events",
                            params={"select": "event_id", "limit": 1},
                            headers=headers(upsert=False), timeout=TIMEOUT)
        if resp.status_code < 300:
            print(f"Connected. events table reachable (HTTP {resp.status_code}).")
        else:
            print(f"HTTP {resp.status_code}: {resp.text[:300]}")
            print("\nIf this says the relation does not exist, run supabase_schema.sql")
            print("in the Supabase SQL editor first.")
        return

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    total = 0

    with connect() as conn:
        has_clean = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events_clean'"
        ).fetchone()
        if not has_clean or not conn.execute(
                "SELECT COUNT(*) FROM events_clean").fetchone()[0]:
            raise SystemExit("No cleaned events. Run src/clean.py first.")

        print("\nSyncing to Supabase:")

        # --- venues ---------------------------------------------------------
        total += push("venues", rows_from(conn, "SELECT * FROM venues", lambda r: {
            "venue_id": r["venue_id"], "name": r["name"], "city": r["city"],
            "state_code": r["state_code"], "country_code": r["country_code"],
            "address": r["address"], "postal_code": r["postal_code"],
            "latitude": r["latitude"], "longitude": r["longitude"],
            "timezone": r["timezone"], "market": r["market"],
            "dma_id": str(r["dma_id"]) if r["dma_id"] is not None else None,
            "url": r["url"], "updated_at": now,
        }), on_conflict="venue_id", dry_run=args.dry_run)

        # --- attractions ----------------------------------------------------
        total += push("attractions", rows_from(conn, "SELECT * FROM attractions",
            lambda r: {
                "attraction_id": r["attraction_id"], "name": r["name"], "url": r["url"],
                "segment_id": r["segment_id"], "segment_name": r["segment_name"],
                "genre_id": r["genre_id"], "genre_name": r["genre_name"],
                "subgenre_id": r["subgenre_id"], "subgenre_name": r["subgenre_name"],
                "upcoming_events": r["upcoming_events"], "image_url": r["image_url"],
                "first_seen_at": r["first_seen_at"], "updated_at": now,
            }), on_conflict="attraction_id", dry_run=args.dry_run)

        total += push("attraction_links", rows_from(conn,
            "SELECT * FROM attraction_links", lambda r: dict(r)),
            on_conflict="attraction_id,platform,url", dry_run=args.dry_run)

        # --- events, joined to their cleaning output ------------------------
        total += push("events", rows_from(conn, """
            SELECT e.*, c.genre_clean, c.subgenre_clean, c.is_electronic,
                   c.is_duplicate, c.is_cancelled, c.dedup_group, c.lineup_size,
                   c.lead_time_days, c.weekday, c.venue_canonical_id, c.headliner
            FROM events e JOIN events_clean c USING(event_id)""", lambda r: {
                "event_id": r["event_id"], "name": r["name"], "url": r["url"],
                "venue_id": r["venue_id"],
                "local_date": none_if_blank(r["local_date"]),
                "local_time": none_if_blank(r["local_time"]),
                "datetime_utc": none_if_blank(r["datetime_utc"]),
                "timezone": r["timezone"], "status": r["status"],
                "onsale_start": none_if_blank(r["onsale_start"]),
                "onsale_end": none_if_blank(r["onsale_end"]),
                "price_min": r["price_min"], "price_max": r["price_max"],
                "price_currency": r["price_currency"],
                "promoter_name": r["promoter_name"],
                "segment_id": r["segment_id"], "segment_name": r["segment_name"],
                "genre_id": r["genre_id"], "genre_name": r["genre_name"],
                "subgenre_id": r["subgenre_id"], "subgenre_name": r["subgenre_name"],
                "genre_clean": r["genre_clean"], "subgenre_clean": r["subgenre_clean"],
                "is_electronic": bool(r["is_electronic"]),
                "is_duplicate": bool(r["is_duplicate"]),
                "is_cancelled": bool(r["is_cancelled"]),
                "dedup_group": r["dedup_group"], "lineup_size": r["lineup_size"],
                "venue_canonical_id": r["venue_canonical_id"],
                "headliner": r["headliner"],
                "lead_time_days": r["lead_time_days"], "weekday": r["weekday"],
                "first_seen_at": r["fetched_at"], "last_seen_at": r["fetched_at"],
                "updated_at": now,
            }), on_conflict="event_id", dry_run=args.dry_run)

        total += push("event_attractions", rows_from(conn,
            "SELECT * FROM event_attractions", lambda r: dict(r)),
            on_conflict="event_id,attraction_id", dry_run=args.dry_run)

        total += push("classifications", rows_from(conn,
            "SELECT segment_id, segment_name, genre_id, genre_name, subgenre_id, "
            "subgenre_name FROM classifications", lambda r: dict(r)),
            on_conflict="segment_id,genre_id,subgenre_id", dry_run=args.dry_run)

        # --- observations: append-only, never merged ------------------------
        total += push("event_observations", rows_from(conn,
            "SELECT * FROM event_observations", lambda r: dict(r)),
            on_conflict="event_id,observed_at", dry_run=args.dry_run)

    print(f"\n{total} rows synced." if not args.dry_run else "\ndry run, nothing sent.")


if __name__ == "__main__":
    main()
