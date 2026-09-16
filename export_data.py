#!/usr/bin/env python3
"""
Export the cleaned tables as CSV, plus a small raw sample, so the website can
link to real data. GitHub renders CSV files in the browser, which makes them
far more useful to a reader than a binary database file.

    python export_data.py

Writes:
    data/sample/*.csv        cleaned tables
    raw/sample/*.jsonl       first few raw API responses, exactly as received
"""
import csv
import gzip
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "bandsintown.sqlite"
CLEAN_DIR = ROOT / "data" / "sample"
RAW_DIR = ROOT / "raw" / "sample"

TABLES = ["artists", "artist_snapshots", "artists_mb", "artist_tags",
          "mb_colorado_artists", "seed_discovery"]

RAW_SAMPLE_LINES = 5


def export_clean() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    for table in TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            print(f"  skip {table} (no such table)")
            continue

        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        path = CLEAN_DIR / f"{table}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            if rows:
                writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
                writer.writeheader()
                for r in rows:
                    writer.writerow(dict(r))
            else:
                cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})")]
                csv.writer(fh).writerow(cols)
        print(f"  wrote data/sample/{table}.csv  ({len(rows)} rows)")

    conn.close()


def export_raw() -> None:
    """A few untouched API responses, so the reader can see the original shape."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for kind in ("artists", "events"):
        files = sorted((ROOT / "raw" / kind).rglob("*.jsonl.gz"))
        if not files:
            continue
        out = RAW_DIR / f"{kind}_sample.jsonl"
        written = 0
        with open(out, "w", encoding="utf-8") as dst:
            with gzip.open(files[0], "rt", encoding="utf-8") as src:
                for line in src:
                    if written >= RAW_SAMPLE_LINES:
                        break
                    if not line.strip():
                        continue
                    # re-dump indented so it is readable on GitHub
                    dst.write(json.dumps(json.loads(line), indent=2) + "\n")
                    written += 1
        print(f"  wrote raw/sample/{kind}_sample.jsonl  ({written} responses)")


if __name__ == "__main__":
    if not DB.exists():
        raise SystemExit(f"No database at {DB}. Run the collection first.")
    print("Exporting cleaned tables:")
    export_clean()
    print("\nExporting raw samples:")
    export_raw()
    print("\nDone. Commit data/sample/ and raw/sample/ so the website links resolve.")
