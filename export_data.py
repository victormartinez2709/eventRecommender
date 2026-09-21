"""
Export the raw and cleaned data, and render the before/after sample images.

    python export_data.py

Produces three things the project website links to:

  exports/*.csv                 the parsed raw tables and the cleaned tables
  raw/sample/*.json             one untouched API response, pretty-printed
  assets/figures/raw_sample.png and clean_sample.png

The sample images deliberately show the same events before and after cleaning,
chosen so that the defects are visible: a placeholder genre, a ticket tier
listed as an artist, and one concert listed twice.
"""

from __future__ import annotations

import csv
import gzip
import json
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from config import DB_PATH, PROJECT_ROOT

EXPORTS = PROJECT_ROOT / "exports"
SAMPLES = PROJECT_ROOT / "raw" / "sample"
FIGS = PROJECT_ROOT / "assets" / "figures"
for d in (EXPORTS, SAMPLES, FIGS):
    d.mkdir(parents=True, exist_ok=True)

INK, HEAD_BG, ALT_BG = "#0b0b0b", "#2a78d6", "#f4f6f9"
FLAG_BG = "#fde3d5"


def dump(conn, name, sql):
    """Write one query to a CSV and report its size."""
    rows = conn.execute(sql).fetchall()
    path = EXPORTS / f"{name}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(rows[0].keys() if rows else [])
        for r in rows:
            w.writerow(list(r))
    print(f"  {path.relative_to(PROJECT_ROOT)}  ({len(rows):,} rows, "
          f"{path.stat().st_size / 1024:.0f} KB)")
    return len(rows)


def table_image(path, title, columns, rows, note, flag_col=None):
    """Render a small table as a figure, with flagged cells tinted."""
    fig, ax = plt.subplots(figsize=(min(2.0 + 1.55 * len(columns), 13), 1.0 + 0.42 * len(rows)))
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=columns, loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    tbl.scale(1, 1.45)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#dcdbd6")
        cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor(HEAD_BG)
            cell.set_text_props(color="white", weight="bold")
        else:
            flagged = flag_col is not None and str(rows[r - 1][flag_col]).strip() in ("1", "yes")
            cell.set_facecolor(FLAG_BG if flagged else (ALT_BG if r % 2 else "white"))
    ax.set_title(title, fontsize=11, weight="semibold", color=INK, pad=14)
    fig.text(0.5, 0.015, note, ha="center", fontsize=7.5, color="#52514e", wrap=True)
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {path.relative_to(PROJECT_ROOT)}")


def clip(v, n=26):
    s = "" if v is None else str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("\nCSV exports")
    dump(conn, "events_raw", "SELECT * FROM events ORDER BY local_date")
    dump(conn, "events_clean", """
        SELECT e.event_id, e.name, c.name_clean, c.headliner, v.name AS venue,
               v.city, c.venue_canonical_id, e.local_date, c.weekday, e.status,
               c.genre_clean, c.subgenre_clean, c.is_electronic, c.is_duplicate,
               c.is_cancelled, c.dedup_group, c.lineup_size, c.lead_time_days,
               e.price_min, e.price_max
        FROM events e
        JOIN events_clean c USING(event_id)
        LEFT JOIN venues v ON v.venue_id = c.venue_canonical_id
        ORDER BY e.local_date""")
    dump(conn, "venues", "SELECT * FROM venues ORDER BY city, name")
    dump(conn, "attractions", "SELECT * FROM attractions ORDER BY name")
    dump(conn, "event_attractions", "SELECT * FROM event_attractions")
    dump(conn, "classifications", "SELECT * FROM classifications")
    dump(conn, "event_observations", "SELECT * FROM event_observations")

    # --- one untouched API response ---------------------------------------
    print("\nRaw API sample")
    archives = sorted((PROJECT_ROOT / "raw" / "events").rglob("*.jsonl.gz"))
    if archives:
        with gzip.open(archives[-1], "rt", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                payload = rec.get("payload", rec)
                evs = payload.get("_embedded", {}).get("events", [])
                if evs:
                    out = SAMPLES / "ticketmaster_event_sample.json"
                    out.write_text(json.dumps(evs[0], indent=2)[:60000], encoding="utf-8")
                    print(f"  {out.relative_to(PROJECT_ROOT)}  (one event, as returned)")
                    page = SAMPLES / "ticketmaster_response_sample.json"
                    trimmed = dict(payload)
                    trimmed["_embedded"] = {"events": evs[:2]}
                    page.write_text(json.dumps(trimmed, indent=2)[:120000], encoding="utf-8")
                    print(f"  {page.relative_to(PROJECT_ROOT)}  (response envelope, 2 events)")
                    break

    # --- before / after images --------------------------------------------
    print("\nSample images")
    group = conn.execute("""
        SELECT dedup_group FROM events_clean
        GROUP BY dedup_group HAVING COUNT(*) > 1 AND SUM(is_duplicate) > 0
        LIMIT 1""").fetchone()[0]
    ids = [r[0] for r in conn.execute(
        "SELECT event_id FROM events_clean WHERE dedup_group = ?", (group,))]
    ids += [r[0] for r in conn.execute("""
        SELECT event_id FROM events_clean WHERE genre_clean IS NULL LIMIT 2""")]
    ids += [r[0] for r in conn.execute("""
        SELECT ea.event_id FROM event_attractions ea
        JOIN attractions a USING(attraction_id)
        WHERE lower(a.name) LIKE 'club seating%' LIMIT 2""")]
    marks = ",".join("?" * len(ids))

    raw_rows = []
    for r in conn.execute(f"""
        SELECT e.event_id, e.name, v.name venue, e.local_date, e.genre_name,
               e.subgenre_name, e.price_min,
               (SELECT a.name FROM event_attractions ea
                JOIN attractions a USING(attraction_id)
                WHERE ea.event_id = e.event_id ORDER BY ea.position LIMIT 1) first_act
        FROM events e LEFT JOIN venues v USING(venue_id)
        WHERE e.event_id IN ({marks}) ORDER BY e.local_date""", ids):
        raw_rows.append([clip(r["event_id"], 18), clip(r["name"], 30), clip(r["venue"], 20),
                         clip(r["local_date"], 10), clip(r["genre_name"], 16),
                         clip(r["subgenre_name"], 14),
                         "" if r["price_min"] is None else f"{r['price_min']:.2f}",
                         clip(r["first_act"], 22)])

    table_image(
        FIGS / "raw_sample.png",
        "Raw data, exactly as the API returns it",
        ["event_id", "name", "venue", "date", "genre", "subgenre", "price", "first act"],
        raw_rows,
        'Four defects are visible: "Undefined" stored where a genre is missing, an empty price, '
        '"Club Seating" listed ahead of the real performer, and one concert appearing twice '
        'under two ids and two slightly different titles.')

    clean_rows = []
    for r in conn.execute(f"""
        SELECT c.event_id, c.name_clean, c.headliner, v.name venue, e.local_date,
               c.genre_clean, c.is_electronic, c.is_duplicate, c.lineup_size
        FROM events_clean c JOIN events e USING(event_id)
        LEFT JOIN venues v ON v.venue_id = c.venue_canonical_id
        WHERE c.event_id IN ({marks}) ORDER BY e.local_date""", ids):
        clean_rows.append([clip(r["event_id"], 18), clip(r["name_clean"], 28),
                           clip(r["headliner"], 22), clip(r["venue"], 20),
                           clip(r["local_date"], 10),
                           r["genre_clean"] if r["genre_clean"] else "NULL",
                           str(r["is_electronic"]), str(r["is_duplicate"]),
                           str(r["lineup_size"])])

    table_image(
        FIGS / "clean_sample.png",
        "The same events after cleaning",
        ["event_id", "name_clean", "headliner", "venue", "date", "genre", "elec", "dup", "acts"],
        clean_rows,
        'Placeholder genres are now NULL, the ticket tier no longer appears as the headliner, '
        'and the repeated concert is flagged in the dup column (tinted) rather than deleted, '
        'so the decision stays reversible.',
        flag_col=7)

    conn.close()
    print("\nDone. exports/ is what the website links to as cleaned data.\n")


if __name__ == "__main__":
    main()
