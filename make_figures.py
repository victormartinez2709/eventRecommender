#!/usr/bin/env python3
"""
Generates every figure on the project website.

The dataset is artist-level: Bandsintown artist profiles, enriched with
MusicBrainz genres, tags and geography, plus an independent MusicBrainz sample
of Colorado artists. Bandsintown's events endpoint is restricted to the key
holder's own artist, so there are no event, venue or lineup figures.

    python make_figures.py [path/to/bandsintown.sqlite]

Missing figures fall back to a labelled placeholder, so the site never breaks.
"""
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ACCENT = "#3b6ea5"
ACCENT_2 = "#c2571a"
INK = "#1a1a1c"
MUTED = "#5b5b63"
GRID = "#dcdce0"

plt.rcParams.update({
    "figure.dpi": 140, "savefig.dpi": 140, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.labelsize": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})

OUT = Path(__file__).resolve().parent / "assets" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

FIGURES = [
    "fig01_follower_distribution.png",
    "fig02_top_artists.png",
    "fig03_upcoming_events.png",
    "fig04_followers_vs_events.png",
    "fig05_match_method.png",
    "fig06_field_completeness.png",
    "fig07_top_genres.png",
    "fig08_genres_per_artist.png",
    "fig09_artist_geography.png",
    "fig10_colorado_precision.png",
    "raw_sample.png",
    "clean_sample.png",
]


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"  wrote {name}")


def placeholder(name, label):
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                               facecolor="#f7f7f8", edgecolor=GRID, linewidth=1))
    ax.text(0.5, 0.58, label, ha="center", va="center", fontsize=12,
            fontweight="bold", color=INK, transform=ax.transAxes)
    ax.text(0.5, 0.36, "Figure pending — run make_figures.py after collection",
            ha="center", va="center", fontsize=9, color=MUTED, transform=ax.transAxes)
    save(fig, name)


CO_CITIES = [
    ("Denver", 39.739, -104.990), ("Boulder", 40.015, -105.270),
    ("Colorado Springs", 38.834, -104.821), ("Fort Collins", 40.585, -105.084),
    ("Greeley", 40.423, -104.709), ("Pueblo", 38.254, -104.609),
    ("Morrison", 39.654, -105.190), ("Englewood", 39.648, -104.988),
    ("Aspen", 39.191, -106.818), ("Vail", 39.640, -106.374),
    ("Breckenridge", 39.482, -106.038), ("Steamboat Springs", 40.485, -106.831),
    ("Grand Junction", 39.064, -108.551), ("Durango", 37.275, -107.880),
    ("Lafayette", 39.993, -105.090),
]
OFFSETS = {"Denver": (13, -4, "left"), "Englewood": (0, -14, "center"),
           "Morrison": (-10, -2, "right"), "Lafayette": (10, 0, "left"),
           "Boulder": (-9, 2, "right"), "Greeley": (10, -2, "left"),
           "Fort Collins": (0, 9, "center"), "Vail": (0, 9, "center"),
           "Breckenridge": (0, -14, "center"), "Aspen": (-9, -2, "right")}


def intro_map():
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.add_patch(plt.Rectangle((-109.06, 36.99), 7.02, 4.01,
                               facecolor="#f4f6f9", edgecolor=GRID, linewidth=1.2))
    for name, lat, lon in CO_CITIES:
        primary = name == "Denver"
        ax.scatter(lon, lat, s=150 if primary else 45, color=ACCENT,
                   alpha=1.0 if primary else 0.55, edgecolor="white",
                   linewidth=1.2, zorder=3)
        dx, dy, ha = OFFSETS.get(name, (0, 8, "center"))
        ax.annotate(name, (lon, lat), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=8.5 if primary else 7.2,
                    fontweight="bold" if primary else "normal",
                    color=INK if primary else MUTED, zorder=4)
    ax.set_xlim(-109.6, -101.5); ax.set_ylim(36.6, 41.4)
    ax.set_xlabel("Longitude (°)"); ax.set_ylabel("Latitude (°)")
    ax.set_title("Colorado cities in the study region")
    grid(ax, axis="both"); save(fig, "intro_map.png")


def build_real(conn):
    conn.row_factory = sqlite3.Row
    def q(sql, p=()):
        return conn.execute(sql, p).fetchall()

    def table_exists(name):
        return bool(q("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    # -- 1. follower distribution -------------------------------------------
    rows = q("""SELECT s.tracker_count AS t FROM artists a
                JOIN artist_snapshots s USING(artist_id)
                WHERE s.tracker_count > 0 GROUP BY a.artist_id""")
    vals = [r["t"] for r in rows]
    if vals:
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.hist(vals, bins=np.logspace(0, np.log10(max(vals)) + 0.1, 30),
                color=ACCENT, rwidth=0.9)
        ax.set_xscale("log")
        ax.set_title("Distribution of artist follower counts")
        ax.set_xlabel("Bandsintown followers (log scale)")
        ax.set_ylabel("Number of artists")
        grid(ax); save(fig, "fig01_follower_distribution.png")

    # -- 2. top artists ------------------------------------------------------
    rows = q("""SELECT a.name AS n, MAX(s.tracker_count) AS t FROM artists a
                JOIN artist_snapshots s USING(artist_id)
                GROUP BY a.artist_id ORDER BY t DESC LIMIT 20""")
    if rows:
        fig, ax = plt.subplots(figsize=(7.2, 6.0))
        names = [r["n"][:30] for r in rows][::-1]
        vals = [r["t"] for r in rows][::-1]
        ax.barh(names, vals, color=ACCENT, height=0.72)
        ax.set_xscale("log")
        ax.set_title(f"Most-followed artists in the dataset (top {len(rows)})")
        ax.set_xlabel("Followers (log scale)")
        grid(ax, axis="x"); save(fig, "fig02_top_artists.png")

    # -- 3. upcoming events --------------------------------------------------
    rows = q("""SELECT MAX(s.upcoming_event_count) AS u FROM artists a
                JOIN artist_snapshots s USING(artist_id) GROUP BY a.artist_id""")
    vals = [r["u"] or 0 for r in rows]
    if vals:
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        top = max(max(vals), 1)
        ax.hist(vals, bins=np.arange(-0.5, min(top, 60) + 1.5, 2),
                color=ACCENT, rwidth=0.9)
        ax.set_title("Upcoming events announced per artist")
        ax.set_xlabel("Upcoming events"); ax.set_ylabel("Number of artists")
        grid(ax); save(fig, "fig03_upcoming_events.png")

    # -- 4. followers vs upcoming events ------------------------------------
    rows = q("""SELECT MAX(s.tracker_count) AS t, MAX(s.upcoming_event_count) AS u
                FROM artists a JOIN artist_snapshots s USING(artist_id)
                GROUP BY a.artist_id""")
    pts = [(r["t"], r["u"]) for r in rows if r["t"] and r["t"] > 0]
    if pts:
        fig, ax = plt.subplots(figsize=(7.2, 4.0))
        ax.scatter([p[0] for p in pts], [(p[1] or 0) + 0.5 for p in pts],
                   s=34, color=ACCENT, alpha=0.7, edgecolor="white", linewidth=0.6)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_title("Audience size against announced activity")
        ax.set_xlabel("Followers (log scale)")
        ax.set_ylabel("Upcoming events + 0.5 (log scale)")
        grid(ax, axis="both"); save(fig, "fig04_followers_vs_events.png")

    # -- 5. how each artist was matched to MusicBrainz -----------------------
    if table_exists("artists_mb"):
        total = q("SELECT COUNT(*) c FROM artists")[0]["c"]
        rows = q("SELECT match_method m, COUNT(*) c FROM artists_mb GROUP BY m")
        counts = {r["m"]: r["c"] for r in rows}
        counts["unmatched"] = total - sum(counts.values())
        labels = ["mbid", "name-search", "unmatched"]
        vals = [counts.get(k, 0) for k in labels]
        pretty = ["Exact (MusicBrainz ID\nsupplied by Bandsintown)",
                  "Fuzzy (name search,\nscore ≥ 90)", "No match found"]
        fig, ax = plt.subplots(figsize=(7.2, 3.8))
        bars = ax.bar(pretty, vals, color=[ACCENT, ACCENT, ACCENT_2], width=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v}\n({100*v/max(total,1):.0f}%)",
                    ha="center", va="bottom", fontsize=9, color=MUTED)
        ax.set_title("How each artist was linked to MusicBrainz")
        ax.set_ylabel("Number of artists")
        ax.set_ylim(0, max(vals) * 1.25 if max(vals) else 1)
        grid(ax); save(fig, "fig05_match_method.png")

    # -- 6. field completeness ----------------------------------------------
    total = q("SELECT COUNT(*) c FROM artists")[0]["c"] or 1
    checks = [
        ("Name", "SELECT COUNT(*) c FROM artists WHERE name IS NOT NULL AND name != ''"),
        ("Follower count", "SELECT COUNT(DISTINCT artist_id) c FROM artist_snapshots WHERE tracker_count IS NOT NULL"),
        ("Image URL", "SELECT COUNT(*) c FROM artists WHERE image_url IS NOT NULL AND image_url != ''"),
        ("MusicBrainz ID", "SELECT COUNT(*) c FROM artists WHERE mbid IS NOT NULL AND mbid != ''"),
        ("Facebook page", "SELECT COUNT(*) c FROM artists WHERE facebook_page_url IS NOT NULL AND facebook_page_url != ''"),
    ]
    if table_exists("artists_mb"):
        checks += [
            ("MusicBrainz record", "SELECT COUNT(*) c FROM artists_mb"),
            ("Area (geography)", "SELECT COUNT(*) c FROM artists_mb WHERE area IS NOT NULL OR begin_area IS NOT NULL"),
        ]
    if table_exists("artist_tags"):
        checks.append(("Any genre tag", "SELECT COUNT(DISTINCT artist_id) c FROM artist_tags"))
    labels, pcts = [], []
    for label, sql in checks:
        labels.append(label)
        pcts.append(100 * q(sql)[0]["c"] / total)
    order = np.argsort(pcts)
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.barh([labels[i] for i in order], [pcts[i] for i in order],
            color=ACCENT, height=0.68)
    for y, i in enumerate(order):
        ax.text(pcts[i], y, f" {pcts[i]:.0f}%", va="center", fontsize=8.5, color=MUTED)
    ax.set_xlim(0, 108)
    ax.set_title("Field completeness across both data sources")
    ax.set_xlabel("Percent of artists with a value")
    grid(ax, axis="x"); save(fig, "fig06_field_completeness.png")

    # -- 7. top genres -------------------------------------------------------
    if table_exists("artist_tags"):
        rows = q("""SELECT tag, COUNT(DISTINCT artist_id) c FROM artist_tags
                    WHERE source = 'musicbrainz-genre'
                    GROUP BY tag ORDER BY c DESC LIMIT 20""")
        if rows:
            fig, ax = plt.subplots(figsize=(7.2, 6.0))
            ax.barh([r["tag"][:28] for r in rows][::-1],
                    [r["c"] for r in rows][::-1], color=ACCENT, height=0.72)
            ax.set_title(f"Most common genres (top {len(rows)})")
            ax.set_xlabel("Number of artists carrying the genre")
            grid(ax, axis="x"); save(fig, "fig07_top_genres.png")

        # -- 8. genres per artist -------------------------------------------
        rows = q("""SELECT COUNT(*) c FROM artist_tags
                    WHERE source='musicbrainz-genre' GROUP BY artist_id""")
        vals = [r["c"] for r in rows]
        if vals:
            fig, ax = plt.subplots(figsize=(7.2, 3.6))
            ax.hist(vals, bins=np.arange(0.5, min(max(vals), 25) + 1.5, 1),
                    color=ACCENT, rwidth=0.86)
            ax.set_title("Number of genre labels per artist")
            ax.set_xlabel("Genres assigned"); ax.set_ylabel("Number of artists")
            grid(ax); save(fig, "fig08_genres_per_artist.png")

    # -- 9. geography --------------------------------------------------------
    if table_exists("artists_mb"):
        rows = q("""SELECT COALESCE(NULLIF(area,''), NULLIF(begin_area,''), 'unknown') a,
                           COUNT(*) c FROM artists_mb
                    GROUP BY a ORDER BY c DESC LIMIT 15""")
        if rows:
            fig, ax = plt.subplots(figsize=(7.2, 5.0))
            ax.barh([str(r["a"])[:28] for r in rows][::-1],
                    [r["c"] for r in rows][::-1], color=ACCENT, height=0.72)
            ax.set_title(f"Where the artists are from (top {len(rows)} areas)")
            ax.set_xlabel("Number of artists")
            grid(ax, axis="x"); save(fig, "fig09_artist_geography.png")

    # -- 10. Colorado search precision --------------------------------------
    if table_exists("mb_colorado_artists"):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(mb_colorado_artists)")}
        if "is_colorado" in cols:
            rows = q("""SELECT query_area q,
                               SUM(is_colorado) hit,
                               COUNT(*) - SUM(is_colorado) miss
                        FROM mb_colorado_artists GROUP BY q ORDER BY COUNT(*) DESC""")
            if rows:
                fig, ax = plt.subplots(figsize=(7.2, 4.4))
                def clean(q):
                    q = str(q).replace('"', '')
                    if q.startswith("beginarea:"):
                        return q[len("beginarea:"):] + " (origin)"
                    if q.startswith("area:"):
                        return q[len("area:"):]
                    return q
                labs = [clean(r["q"]) for r in rows][::-1]
                hit = [r["hit"] or 0 for r in rows][::-1]
                miss = [r["miss"] or 0 for r in rows][::-1]
                ax.barh(labs, hit, color=ACCENT, height=0.68, label="Genuinely Colorado")
                ax.barh(labs, miss, left=hit, color=ACCENT_2, height=0.68,
                        label="Search noise (other states)")
                ax.set_title("Precision of each MusicBrainz area query")
                ax.set_xlabel("Artists returned")
                # legend below the axes so it cannot sit on top of a bar
                ax.legend(frameon=False, fontsize=9, ncol=2,
                          loc="upper center", bbox_to_anchor=(0.5, -0.16))
                grid(ax, axis="x"); save(fig, "fig10_colorado_precision.png")

    # -- raw / clean samples -------------------------------------------------
    raw_text = (
        '{\n  "id": "15559410",\n  "name": "MGNA Crrrta",\n'
        '  "url": "https://www.bandsintown.com/a/15559410?app_id=REDACTED",\n'
        '  "mbid": "",\n  "tracker_count": 8821,\n  "upcoming_event_count": 32,\n'
        '  "image_url": "https://photos.bandsintown.com/large/...jpeg",\n'
        '  "facebook_page_url": "",\n'
        '  "links": [\n    {"type": "spotify", "url": "https://open.spotify.com/..."}\n  ]\n}'
    )
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.axis("off")
    ax.text(0.02, 0.98, raw_text, family="monospace", fontsize=8.5,
            va="top", ha="left", color=INK, transform=ax.transAxes)
    ax.set_title("Raw API response, one artist, as stored", loc="left")
    save(fig, "raw_sample.png")

    rows = q("""SELECT a.name, s.tracker_count, a.mbid,
                       COALESCE(m.area, m.begin_area) AS area, m.match_method
                FROM artists a
                LEFT JOIN artist_snapshots s USING(artist_id)
                LEFT JOIN artists_mb m USING(artist_id)
                GROUP BY a.artist_id ORDER BY s.tracker_count DESC LIMIT 6"""
             ) if table_exists("artists_mb") else []
    fig, ax = plt.subplots(figsize=(7.8, 2.6))
    ax.axis("off")
    if rows:
        cells = [[str(c)[:22] if c not in (None, "") else "—" for c in tuple(r)] for r in rows]
        table = ax.table(cellText=cells,
                         colLabels=["name", "followers", "mbid", "area", "match"],
                         loc="center", cellLoc="left")
        table.auto_set_font_size(False); table.set_fontsize(7.5); table.scale(1, 1.35)
        for (r, _), cell in table.get_celld().items():
            cell.set_edgecolor(GRID)
            if r == 0:
                cell.set_facecolor("#f7f7f8"); cell.set_text_props(weight="bold")
    ax.set_title("Cleaned data, artists joined to MusicBrainz", loc="left")
    save(fig, "clean_sample.png")


def main():
    default_db = Path(__file__).resolve().parent / "data" / "bandsintown.sqlite"
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_db

    intro_map()

    ok = False
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            n = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
            if n:
                print(f"Database found with {n} artists — building figures.")
                build_real(conn); ok = True
            conn.close()
        except sqlite3.Error as exc:
            print(f"Could not read {db_path}: {exc}")
    if not ok:
        print(f"No usable data at {db_path} — writing placeholders.")

    for f in FIGURES:
        if not (OUT / f).exists():
            placeholder(f, f.replace(".png", "").split("_", 1)[-1].replace("_", " ").title())

    print(f"\nFigures in {OUT}")


if __name__ == "__main__":
    main()
