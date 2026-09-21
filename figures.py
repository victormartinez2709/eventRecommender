"""
Generate the exploratory figures for the project website.

    python figures.py

Reads the local database only -- no API calls. Writes ten PNGs to
assets/figures/ and prints the numbers behind them, so the write-up and the
charts cannot drift apart. Uses live events throughout: duplicates and
cancellations removed.
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from config import DB_PATH, PROJECT_ROOT

OUT = PROJECT_ROOT / "assets" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2 = "#0b0b0b", "#52514e"
GRID = "#e6e5e1"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
RAMP = LinearSegmentedColormap.from_list("blues", SEQ)

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.size": 9,
    "axes.titlesize": 11, "axes.titleweight": "semibold", "axes.labelsize": 9,
    "axes.labelcolor": INK_2, "axes.edgecolor": GRID, "text.color": INK,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.bbox": "tight",
})

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
stats = {}


def style(ax, xgrid=False, ygrid=True):
    """Recessive axes: no box, grid on the value axis, behind the data."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
    if xgrid:
        ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"  wrote {name}")


def barh_labels(ax, bars, values, fmt="{:,.0f}"):
    span = max(values) if values else 1
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + span * 0.015,
                bar.get_y() + bar.get_height() / 2, fmt.format(v),
                va="center", ha="left", fontsize=8, color=INK_2)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q = lambda sql, *a: conn.execute(sql, a).fetchall()
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]

    LIVE = "NOT c.is_duplicate AND NOT c.is_cancelled"
    total_raw = one("SELECT COUNT(*) FROM events")
    n_dup = one("SELECT COUNT(*) FROM events_clean WHERE is_duplicate")
    n_can = one("SELECT COUNT(*) FROM events_clean WHERE is_cancelled AND NOT is_duplicate")
    n_live = one(f"SELECT COUNT(*) FROM events_clean c WHERE {LIVE}")
    stats.update(raw=total_raw, duplicates=n_dup, cancelled=n_can, live=n_live)

    print("\nWriting figures to assets/figures/\n")

    # --- 1. events per month ------------------------------------------------
    rows = q(f"""SELECT substr(e.local_date,1,7) m, COUNT(*) n
                 FROM events e JOIN events_clean c USING(event_id)
                 WHERE {LIVE} AND e.local_date IS NOT NULL
                 GROUP BY m ORDER BY m""")
    months = [r["m"] for r in rows]
    counts = [r["n"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.bar(range(len(months)), counts, color=BLUE, width=0.72)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([m[2:] for m in months], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("events listed")
    ax.set_title("Listings thin out about four months ahead, as announcements run dry")
    style(ax)
    save(fig, "fig01_events_per_month.png")
    stats["peak_month"] = (months[counts.index(max(counts))], max(counts))
    stats["months_span"] = (months[0], months[-1])

    # --- 2. weekday ---------------------------------------------------------
    wd = {r["w"]: r["n"] for r in q(
        f"""SELECT c.weekday w, COUNT(*) n FROM events_clean c
            WHERE {LIVE} AND c.weekday IS NOT NULL GROUP BY w ORDER BY w""")}
    vals = [wd.get(i, 0) for i in range(7)]
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    ax.bar(WEEKDAYS, vals, color=BLUE, width=0.68)
    ax.set_ylabel("events")
    ax.set_title("Live music concentrates on Friday and Saturday")
    style(ax)
    save(fig, "fig02_events_by_weekday.png")
    stats["weekend_share"] = 100 * (vals[5] + vals[6]) / max(sum(vals), 1)

    # --- 3. top venues ------------------------------------------------------
    rows = q(f"""SELECT v.name || ', ' || v.city AS venue, COUNT(*) n
                 FROM events_clean c
                 JOIN venues v ON v.venue_id = c.venue_canonical_id
                 WHERE {LIVE} GROUP BY c.venue_canonical_id
                 ORDER BY n DESC LIMIT 15""")
    names = [r["venue"] for r in rows][::-1]
    vals = [r["n"] for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    bars = ax.barh(names, vals, color=BLUE, height=0.7)
    barh_labels(ax, bars, vals)
    ax.set_xlabel("events")
    ax.set_title("A small number of rooms carry most of the calendar")
    style(ax, xgrid=True, ygrid=False)
    ax.tick_params(labelsize=8)
    save(fig, "fig03_top_venues.png")
    stats["top_venue"] = (rows[0]["venue"], rows[0]["n"])
    stats["n_venues"] = one("SELECT COUNT(DISTINCT venue_canonical_id) FROM events_clean")

    # --- 4. genre distribution ----------------------------------------------
    rows = q(f"""SELECT COALESCE(c.genre_clean, 'no genre given') g, COUNT(*) n
                 FROM events_clean c WHERE {LIVE}
                 GROUP BY g ORDER BY n DESC LIMIT 12""")
    names = [r["g"] for r in rows][::-1]
    vals = [r["n"] for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    bars = ax.barh(names, vals, height=0.7,
                   color=[ORANGE if n == "Dance/Electronic" else BLUE for n in names])
    barh_labels(ax, bars, vals)
    ax.set_xlabel("events")
    ax.set_title("Genre as Ticketmaster reports it, Dance/Electronic highlighted")
    style(ax, xgrid=True, ygrid=False)
    save(fig, "fig04_genre_distribution.png")
    stats["genre_top"] = [(r["g"], r["n"]) for r in rows[:6]]

    # --- 5. how each electronic event was identified ------------------------
    by_genre = one(f"""SELECT COUNT(*) FROM events_clean c
                       WHERE {LIVE} AND c.is_electronic
                         AND c.genre_clean = 'Dance/Electronic'""")
    by_lineup = one(f"""SELECT COUNT(*) FROM events_clean c
                        WHERE {LIVE} AND c.is_electronic
                          AND (c.genre_clean IS NULL
                               OR c.genre_clean <> 'Dance/Electronic')""")
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    bars = ax.bar(["event's own genre", "lineup only"], [by_genre, by_lineup],
                  color=[BLUE, ORANGE], width=0.55)
    for bar, v in zip(bars, [by_genre, by_lineup]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                v + max(by_genre, by_lineup) * 0.02, str(v),
                ha="center", fontsize=9, color=INK)
    ax.set_ylabel("electronic events")
    ax.set_title("A quarter of electronic events are invisible to the genre field")
    style(ax)
    save(fig, "fig05_electronic_detection.png")
    stats["elec_genre"], stats["elec_lineup"] = by_genre, by_lineup
    stats["electronic"] = by_genre + by_lineup

    # --- 6. field completeness ----------------------------------------------
    J = "FROM events e JOIN events_clean c USING(event_id)"
    fields = [
        ("event date",    f"SELECT COUNT(*) {J} WHERE {LIVE} AND e.local_date IS NOT NULL"),
        ("venue",         f"SELECT COUNT(*) {J} WHERE {LIVE} AND e.venue_id IS NOT NULL"),
        ("start time",    f"SELECT COUNT(*) {J} WHERE {LIVE} AND e.local_time IS NOT NULL"),
        ("genre field set", f"SELECT COUNT(*) FROM events_clean c WHERE {LIVE} AND c.genre_clean IS NOT NULL"),
        ("genre that is usable", f"SELECT COUNT(*) FROM events_clean c WHERE {LIVE} AND c.genre_clean IS NOT NULL AND c.genre_clean <> 'Other'"),
        ("on-sale date",  f"SELECT COUNT(*) {J} WHERE {LIVE} AND e.onsale_start IS NOT NULL"),
        ("artist lineup", f"SELECT COUNT(*) FROM events_clean c WHERE {LIVE} AND c.lineup_size > 0"),
        ("promoter",      f"SELECT COUNT(*) {J} WHERE {LIVE} AND e.promoter_name IS NOT NULL"),
        ("subgenre that is usable", f"SELECT COUNT(*) FROM events_clean c WHERE {LIVE} AND c.subgenre_clean IS NOT NULL AND c.subgenre_clean <> 'Other'"),
        ("price",         f"SELECT COUNT(*) {J} WHERE {LIVE} AND e.price_min IS NOT NULL"),
    ]
    pairs = sorted(((lbl, 100 * one(sql) / max(n_live, 1)) for lbl, sql in fields),
                   key=lambda t: t[1])
    names, vals = [p[0] for p in pairs], [p[1] for p in pairs]
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    bars = ax.barh(names, vals, height=0.68,
                   color=[ORANGE if v < 50 else BLUE for v in vals])
    barh_labels(ax, bars, vals, fmt="{:.0f}%")
    ax.set_xlim(0, 110)
    ax.set_xlabel("percent of live events with the field populated")
    ax.set_title("Price is missing, and a quarter of genres say only \"Other\"")
    style(ax, xgrid=True, ygrid=False)
    save(fig, "fig06_field_completeness.png")
    stats["completeness"] = pairs

    # --- 7. lineup size -----------------------------------------------------
    rows = q(f"""SELECT MIN(c.lineup_size, 5) s, COUNT(*) n FROM events_clean c
                 WHERE {LIVE} GROUP BY s ORDER BY s""")
    labels = {0: "none", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5+"}
    fig, ax = plt.subplots(figsize=(5.8, 3.2))
    ax.bar([labels[r["s"]] for r in rows], [r["n"] for r in rows],
           color=BLUE, width=0.64)
    ax.set_xlabel("artists credited on the event")
    ax.set_ylabel("events")
    ax.set_title("Most events name one act, and a sixth name none")
    style(ax)
    save(fig, "fig07_lineup_size.png")
    stats["no_lineup_pct"] = 100 * one(
        f"SELECT COUNT(*) FROM events_clean c WHERE {LIVE} AND c.lineup_size = 0"
    ) / max(n_live, 1)

    # --- 8. cleaning funnel -------------------------------------------------
    vals = [total_raw, total_raw - n_dup, n_live]
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    bars = ax.bar(["collected", "after\nduplicates", "after\ncancellations"],
                  vals, color=[SEQ[2], SEQ[4], BLUE], width=0.55)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + max(vals) * 0.02,
                f"{v:,}", ha="center", fontsize=9, color=INK)
    ax.set_ylabel("events")
    ax.set_title("Cleaning removes one listing in seven")
    style(ax)
    save(fig, "fig08_cleaning_funnel.png")

    # --- 9. on-sale lead time -----------------------------------------------
    lead = [r["lead_time_days"] for r in q(
        f"""SELECT c.lead_time_days FROM events_clean c WHERE {LIVE}
            AND c.lead_time_days BETWEEN 0 AND 400""")]
    med = sorted(lead)[len(lead) // 2] if lead else 0
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.hist(lead, bins=40, color=BLUE)
    ax.axvline(med, color=ORANGE, linewidth=2)
    ax.text(med + 8, ax.get_ylim()[1] * 0.88, f"median {med} days",
            fontsize=8, color=INK_2)
    ax.set_xlabel("days from on-sale to the event")
    ax.set_ylabel("events")
    ax.set_title(f"Tickets go on sale a median of {med} days ahead")
    style(ax)
    save(fig, "fig09_lead_time.png")
    stats["median_lead"] = med

    # --- 10. venue x genre --------------------------------------------------
    top_v = [r["venue_canonical_id"] for r in q(
        f"""SELECT c.venue_canonical_id, COUNT(*) n FROM events_clean c
            WHERE {LIVE} AND c.venue_canonical_id IS NOT NULL
            GROUP BY 1 ORDER BY n DESC LIMIT 12""")]
    top_g = [r["genre_clean"] for r in q(
        f"""SELECT c.genre_clean, COUNT(*) n FROM events_clean c
            WHERE {LIVE} AND c.genre_clean IS NOT NULL
            GROUP BY 1 ORDER BY n DESC LIMIT 8""")]
    vname = {r["venue_id"]: r["name"] for r in q("SELECT venue_id, name FROM venues")}
    cell = Counter()
    for r in q(f"""SELECT c.venue_canonical_id v, c.genre_clean g
                   FROM events_clean c WHERE {LIVE} AND c.genre_clean IS NOT NULL"""):
        if r["v"] in top_v and r["g"] in top_g:
            cell[(r["v"], r["g"])] += 1
    grid = [[cell.get((v, g), 0) for g in top_g] for v in top_v]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    im = ax.imshow(grid, cmap=RAMP, aspect="auto")
    ax.set_xticks(range(len(top_g)))
    ax.set_xticklabels(top_g, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(top_v)))
    ax.set_yticklabels([vname.get(v, v)[:30] for v in top_v], fontsize=8)
    hi = max(max(r) for r in grid) or 1
    for i, row in enumerate(grid):
        for j, val in enumerate(row):
            if val:
                ax.text(j, i, str(val), ha="center", va="center", fontsize=7.5,
                        color="white" if val > hi * 0.55 else INK)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_title("Venues specialise: each room programmes a narrow band of genres")
    fig.colorbar(im, ax=ax, shrink=0.8, label="events")
    save(fig, "fig10_venue_genre_heatmap.png")

    conn.close()

    print("\n" + "=" * 64)
    print("  NUMBERS FOR THE WRITE-UP")
    print("=" * 64)
    print(f"  collected             {stats['raw']:,}")
    print(f"  duplicates removed    {stats['duplicates']:,}")
    print(f"  cancelled removed     {stats['cancelled']:,}")
    print(f"  live events           {stats['live']:,}")
    print(f"  distinct venues       {stats['n_venues']}")
    print(f"  electronic            {stats['electronic']}  "
          f"(by genre {stats['elec_genre']}, by lineup only {stats['elec_lineup']})")
    print(f"  weekend share         {stats['weekend_share']:.0f}%")
    print(f"  events with no lineup {stats['no_lineup_pct']:.0f}%")
    print(f"  median lead time      {stats['median_lead']} days")
    print(f"  busiest month         {stats['peak_month'][0]} ({stats['peak_month'][1]})")
    print(f"  date span             {stats['months_span'][0]} to {stats['months_span'][1]}")
    print(f"  busiest venue         {stats['top_venue'][0]} ({stats['top_venue'][1]})")
    print("  top genres            " + ", ".join(f"{g} {n}" for g, n in stats["genre_top"]))
    print("  completeness          " + ", ".join(f"{l} {v:.0f}%" for l, v in stats["completeness"]))
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
