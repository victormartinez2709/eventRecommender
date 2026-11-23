"""
Module 4: build the event table used for linear regression on the
Regression tab.

    python lead_time_data.py

Target (a number): lead_time_days, the days between tickets going on sale
and the event. It tells us how early a show is announced.
Features:
    is_electronic         1 = electronic event (the Module 1 flag)
    start_hour            local start time as a number (20.5 = 8:30 pm)
    fri_sat               1 = the event is on a Friday or Saturday
    lineup_size           number of artists listed
    headliner_shows_log2  log2(1 + upcoming Ticketmaster events of the headliner),
                          how busy (how prominent) the headliner is
    days_out              days from 20 September 2026 (the first collection) to the
                          event. A show far in the future that is already listed must
                          have gone on sale early, so this keeps the date from
                          hiding inside the other coefficients.
    venue                 the venue, for the venues with 15+ events; the rest are "other"

Only events with a real on-sale date (lead time 0-400 days) are used.
It reads the current database: running it again after a new collection
changes the numbers on the Regression tab.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from config import DB_PATH

MIN_EVENTS = 15                             #venues with fewer events go into "other"
FIRST_COLLECTION = pd.Timestamp("2026-09-20")  #date of the first weekly collection

#we read the live events (no duplicates, no cancellations)
conn = sqlite3.connect(DB_PATH)
ev = pd.read_sql("""
    SELECT c.event_id, e.name, v.name AS venue, e.local_date, e.local_time,
           c.lead_time_days, c.is_electronic, c.lineup_size, c.weekday
    FROM events_clean c
    JOIN events e USING (event_id)
    LEFT JOIN venues v ON v.venue_id = c.venue_canonical_id
    WHERE NOT c.is_duplicate AND NOT c.is_cancelled""", conn)
headliner = pd.read_sql("""
    SELECT ea.event_id, a.upcoming_events
    FROM event_attractions ea JOIN attractions a USING (attraction_id)
    WHERE ea.position = 0""", conn)
conn.close()

ev = ev.merge(headliner, on="event_id", how="left")

#only real on-sale dates (same 0-400 day rule as Module 1) and a known start time
time = pd.to_datetime(ev["local_time"], format="%H:%M:%S", errors="coerce")
ev["start_hour"] = (time.dt.hour + time.dt.minute / 60).round(2)
ev = ev[ev["lead_time_days"].between(0, 400) & ev["start_hour"].notna()].copy()

#features
ev["fri_sat"] = ev["weekday"].isin([5, 6]).astype(int)
ev["headliner_shows_log2"] = np.log2(1 + ev["upcoming_events"].fillna(0)).round(3)
ev["days_out"] = (pd.to_datetime(ev["local_date"]) - FIRST_COLLECTION).dt.days
counts = ev["venue"].value_counts()
big = counts[counts >= MIN_EVENTS].index
ev["venue_group"] = np.where(ev["venue"].isin(big), ev["venue"], "other")

cols = ["name", "venue", "local_date", "is_electronic", "start_hour", "fri_sat", "lineup_size",
        "headliner_shows_log2", "days_out", "venue_group", "lead_time_days"]
data = ev[cols].sample(frac=1, random_state=42).reset_index(drop=True)
data["lead_time_days"] = data["lead_time_days"].astype(int)
data.to_csv("exports/module4/lead_time_events.csv", index=False)

print(len(data), "events with a real on-sale date,", int(data["is_electronic"].sum()), "electronic")
print(len(big), "venues with", MIN_EVENTS, "or more events; the rest are 'other'")
print(data["lead_time_days"].describe().round(1))
