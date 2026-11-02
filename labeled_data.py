"""
Module 3: build the labeled event table used on the Naive Bayes and
Decision Trees tabs.

    python labeled_data.py

Label: is the event electronic? (the Module 1 is_electronic flag)
Features: only the FORMAT of the event (no genre, no venue):
    start_hour      local start time as a number (20.5 = 8:30 pm)
    weekday         0 = Sunday ... 6 = Saturday
    lineup_size     number of artists listed
    lead_time_days  days between tickets going on sale and the event (-1 = unknown)
    month           month of the event

Only 17% of events are electronic, so we take all electronic events and the
same number of random non-electronic events (a balanced sample).
It reads the current database: running it again after a new collection
changes the numbers on the Naive Bayes and Decision Trees tabs.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from config import DB_PATH


def table_image(df, title, path, width=13):
    """Save a few rows of a table as a picture for the website."""
    fig, ax = plt.subplots(figsize=(width, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


#we read the live events (no duplicates, no cancellations)
conn = sqlite3.connect(DB_PATH)
ev = pd.read_sql("""
    SELECT e.name, v.name AS venue, e.local_date, e.local_time,
           c.lineup_size, c.lead_time_days, c.weekday, c.is_electronic
    FROM events_clean c
    JOIN events e USING (event_id)
    LEFT JOIN venues v ON v.venue_id = c.venue_canonical_id
    WHERE NOT c.is_duplicate AND NOT c.is_cancelled""", conn)
conn.close()

#format features (all numbers)
time = pd.to_datetime(ev["local_time"], format="%H:%M:%S", errors="coerce")
ev["start_hour"] = (time.dt.hour + time.dt.minute / 60).fillna(20)
#same rule as Module 1: lead times outside 0-400 days are placeholders -> -1 (unknown)
ev.loc[~ev["lead_time_days"].between(0, 400), "lead_time_days"] = -1
ev["month"] = pd.to_datetime(ev["local_date"]).dt.month
ev["label"] = np.where(ev["is_electronic"] == 1, "electronic", "not_electronic")

#balanced sample: every electronic event + the same number of other events
electronic = ev[ev["is_electronic"] == 1]
other = ev[ev["is_electronic"] == 0].sample(len(electronic), random_state=42)
labeled = pd.concat([electronic, other]).sample(frac=1, random_state=42).reset_index(drop=True)

cols = ["name", "venue", "local_date", "start_hour", "weekday", "lineup_size",
        "lead_time_days", "month", "label"]
labeled = labeled[cols]
labeled["start_hour"] = labeled["start_hour"].round(2)
labeled["lead_time_days"] = labeled["lead_time_days"].astype(int)
labeled.to_csv("exports/module3/events_labeled.csv", index=False)

show = labeled.head(10).copy()
show["name"] = show["name"].str.slice(0, 32)
show["venue"] = show["venue"].fillna("").str.slice(0, 24)
table_image(show, "Labeled data: one row per event, with its label",
            "assets/figures/naivebayes/labeled_sample.png", width=15)

print(len(ev), "live events,", len(electronic), "electronic")
print(len(labeled), "events in the balanced labeled sample")
print(labeled["label"].value_counts())
