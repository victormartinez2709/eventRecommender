"""
The weekly job, end to end.

    python src/weekly_run.py                 # collect, clean, audit, publish
    python src/weekly_run.py --no-sync       # everything except Supabase
    python src/weekly_run.py --fresh         # ignore the cache and re-fetch

Collect, parse, record an observation of every event as it looks now, clean,
audit, publish. Step three is what makes weekly collection worth doing:
Ticketmaster drops events once they are off sale, so anything not observed
this week is gone from the feed for good. Safe to run more than once a day.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import uuid
from pathlib import Path

from config import PROJECT_ROOT
from db import connect, init_db

SRC = Path(__file__).resolve().parent
PY = sys.executable


def run_step(label: str, args: list[str]) -> bool:
    """Run one stage as a subprocess so a failure cannot poison the rest."""
    print(f"\n{'=' * 62}\n{label}\n{'=' * 62}")
    result = subprocess.run([PY, *args], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\n!! {label} exited with code {result.returncode}")
        return False
    return True


def record_observations() -> int:
    """
    Snapshot every known event.

    Append-only and keyed by (event_id, observed_at), so running twice in a day
    adds two rows. days_until is stored because it is the natural x-axis for
    any question about how prices or availability move as an event approaches.
    """
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    stamp = now.isoformat()

    with connect() as conn:
        rows = conn.execute("""
            SELECT e.event_id, e.status, e.price_min, e.price_max, e.local_date,
                   (SELECT COUNT(*) FROM event_attractions ea
                    WHERE ea.event_id = e.event_id) AS lineup_size
            FROM events e""").fetchall()

        payload = []
        for r in rows:
            days_until = None
            raw = (r["local_date"] or "")[:10]
            if len(raw) == 10:
                try:
                    y, m, d = (int(x) for x in raw.split("-"))
                    days_until = (dt.date(y, m, d) - today).days
                except ValueError:
                    pass
            payload.append((r["event_id"], stamp, r["status"], r["price_min"],
                            r["price_max"], r["lineup_size"], days_until))

        conn.executemany(
            """INSERT OR IGNORE INTO event_observations
               (event_id, observed_at, status, price_min, price_max,
                lineup_size, days_until)
               VALUES (?, ?, ?, ?, ?, ?, ?)""", payload)
    return len(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sync", action="store_true",
                        help="skip the Supabase push")
    parser.add_argument("--fresh", action="store_true",
                        help="ignore the cache and re-fetch everything")
    parser.add_argument("--months-forward", type=int, default=12)
    args = parser.parse_args()

    init_db()
    run_id = uuid.uuid4().hex[:12]
    started = dt.datetime.now(dt.timezone.utc)

    with connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.execute("INSERT INTO runs (run_id, started_at) VALUES (?, ?)",
                     (run_id, started.isoformat()))

    print(f"\nweekly run {run_id}  started {started:%Y-%m-%d %H:%M} UTC")
    print(f"events already known: {before}")

    if args.fresh:
        import cache
        print(f"--fresh: purged {cache.purge(expired_only=False)} cache entries")

    ok = run_step("1/6  collecting from Ticketmaster",
                  [str(SRC / "collect_events.py"),
                   "--months-back", "0",
                   "--months-forward", str(args.months_forward)])
    if ok:
        ok = run_step("2/6  normalizing", [str(SRC / "normalize_tm.py")])

    observed = 0
    if ok:
        print(f"\n{'=' * 62}\n3/6  recording observations\n{'=' * 62}")
        observed = record_observations()
        print(f"  observed {observed} events at this point in time")

        ok = run_step("4/6  cleaning and deduplicating", [str(SRC / "clean.py")])

    # The audit re-derives the cleaning decisions independently. A failure here
    # means the local tables are wrong, and syncing would only publish the
    # problem, so the push is skipped rather than attempted.
    if ok:
        if not run_step("5/6  auditing", [str(SRC / "audit.py")]):
            print("\n!! audit found failures -- skipping the Supabase sync.")
            print("   Fix them, re-run src/clean.py, then re-run this.")
            ok = False

    synced = 0
    if ok and not args.no_sync:
        if run_step("6/6  syncing to Supabase", [str(SRC / "supabase_sync.py")]):
            synced = -1  # the sync script reports its own totals

    finished = dt.datetime.now(dt.timezone.utc)
    with connect() as conn:
        after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.execute(
            """UPDATE runs SET finished_at = ?, events_seen = ?, events_new = ?,
                 synced_rows = ?, notes = ? WHERE run_id = ?""",
            (finished.isoformat(), after, after - before, synced,
             "ok" if ok else "failed", run_id))

        import cache
        stats = cache.stats()

    mins = (finished - started).total_seconds() / 60
    print(f"\n{'=' * 62}")
    print(f"run {run_id} finished in {mins:.1f} min")
    print(f"  events known    {after}  (+{after - before} new this week)")
    print(f"  observations    {observed}")
    print(f"  cache entries   {stats.get('entries', 0)} "
          f"({stats.get('fresh', 0)} fresh, {stats.get('hits', 0)} lifetime hits)")
    print("=" * 62)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
