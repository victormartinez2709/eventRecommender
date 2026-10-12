"""
Module 2: build the venue table used on the Clustering and PCA tabs.

    python venue_features.py

Clustering and PCA need numeric, unlabeled data. The cleaned data is one row
per event with text columns, so this makes one row per venue with 16 numeric
columns. It reads the current database: running it after a new weekly
collection changes the numbers on the Clustering and PCA tabs.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from config import DB_PATH

MIN_EVENTS = 8   #venues with fewer events are left out

#Ticketmaster genre -> our genre group ("World" here is almost all Latin)
GENRE_GROUP = {"Rock": "rock", "Alternative": "alternative", "Metal": "metal",
               "Pop": "pop", "Hip-Hop/Rap": "hiphop_rnb", "R&B": "hiphop_rnb",
               "Country": "country_folk", "Folk": "country_folk",
               "World": "latin_world", "Latin": "latin_world"}
GROUPS = ["electronic", "rock", "alternative", "metal", "pop",
          "hiphop_rnb", "country_folk", "latin_world", "other"]


def table_image(df, title, path):
    """Save a few rows of a table as a picture for the website."""
    fig, ax = plt.subplots(figsize=(14, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


#we read the live events (no duplicates, no cancellations)
conn = sqlite3.connect(DB_PATH)
ev = pd.read_sql("""
    SELECT v.name AS venue, v.city, e.local_date, e.local_time, c.genre_clean,
           c.is_electronic, c.lineup_size, c.lead_time_days, c.weekday
    FROM events_clean c
    JOIN events e USING (event_id)
    JOIN venues v ON v.venue_id = c.venue_canonical_id
    WHERE NOT c.is_duplicate AND NOT c.is_cancelled""", conn)
conn.close()
raw = ev.copy()   #kept for the "before" picture

#text columns -> numbers
ev["group"] = np.where(ev["is_electronic"] == 1, "electronic",
                       ev["genre_clean"].map(GENRE_GROUP).fillna("other"))
time = pd.to_datetime(ev["local_time"], format="%H:%M:%S", errors="coerce")
ev["start_hour"] = time.dt.hour + time.dt.minute / 60
ev["is_weekend"] = ev["weekday"].isin([5, 6]).astype(int)      #5 = Fri, 6 = Sat
ev["is_late"] = (ev["start_hour"] >= 21).astype(int)
ev["is_multi"] = (ev["lineup_size"] >= 2).astype(int)
#same rule as Module 1: lead times outside 0-400 days are placeholders
ev.loc[~ev["lead_time_days"].between(0, 400), "lead_time_days"] = np.nan

#one row per venue
g = ev.groupby(["venue", "city"])
venues = pd.crosstab([ev["venue"], ev["city"]], ev["group"], normalize="index")
venues = venues[GROUPS].add_prefix("share_")
venues["weekend_share"] = g["is_weekend"].mean()
venues["late_start_share"] = g["is_late"].mean()
venues["mean_start_hour"] = g["start_hour"].mean()
venues["mean_lineup"] = g["lineup_size"].mean()
venues["multi_artist_share"] = g["is_multi"].mean()
venues["median_lead_days"] = g["lead_time_days"].median()
venues["n_events"] = g.size()

venues = venues[venues["n_events"] >= MIN_EVENTS].reset_index()
venues["log_events"] = np.log(venues["n_events"])
#4 venues have no valid lead time: use the median of the other venues
venues["median_lead_days"] = venues["median_lead_days"].fillna(venues["median_lead_days"].median())
venues = venues.sort_values("n_events", ascending=False).reset_index(drop=True)

#labeled version (only to read the results) and the model input (numbers only)
cols = ["venue", "city", "n_events"] + [c for c in venues.columns if c not in ("venue", "city", "n_events")]
venues[cols].round(4).to_csv("exports/module2/venue_profiles_labeled.csv", index=False)
features = venues.drop(columns=["venue", "city", "n_events"])
features.round(4).to_csv("exports/module2/venue_features.csv", index=False)

#pictures of the data for the Data Prep sections
before = raw[raw["venue"].isin(venues["venue"])].sort_values(["venue", "local_date"]).groupby("venue").head(1)
table_image(before.head(10).fillna("NULL"),
            "Before: one row per event (text and numbers)",
            "assets/figures/clustering/prep_before_events.png")
short = lambda c: c.replace("share_", "").replace("_share", "").replace("mean_", "").replace("median_", "")
table_image(features.head(10).round(2).rename(columns=short),
            "After: one row per venue, numbers only, no labels",
            "assets/figures/clustering/prep_after_features.png")
X = pd.DataFrame(StandardScaler().fit_transform(features), columns=features.columns)
table_image(X.head(10).round(2).rename(columns=short),
            "PCA input: standardized (mean 0, standard deviation 1)",
            "assets/figures/pca/prep_standardized.png")

print(len(ev), "live events at", ev["venue"].nunique(), "venues")
print(len(venues), "venues with at least", MIN_EVENTS, "events:", venues["n_events"].sum(), "events")
