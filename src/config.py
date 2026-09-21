"""
Central configuration. Every other module imports from here, so there is exactly
one place where paths, the API key, and the collection settings are defined.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- credentials ----------------------------------------------------------
TM_API_KEY = os.getenv("TICKETMASTER_API_KEY")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "unknown@example.com")
USER_AGENT = f"CU-Boulder-CSCI5612-project/0.2 (+{CONTACT_EMAIL})"

# --- collection settings --------------------------------------------------
# Ticketmaster allows 5 requests/second. 0.25s keeps us comfortably under it.
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL_SECONDS", "0.25"))

# Daily quota is 5000 calls. Stop before exhausting it so a run never dies
# halfway through a date slice.
DAILY_BUDGET = int(os.getenv("DAILY_BUDGET", "4500"))

# How far back and forward to collect, in months from today.
MONTHS_BACK = int(os.getenv("MONTHS_BACK", "12"))
MONTHS_FORWARD = int(os.getenv("MONTHS_FORWARD", "12"))

# --- Supabase -------------------------------------------------------------
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- cache ----------------------------------------------------------------
# Set USE_CACHE=0 in .env to force every request to hit the API.
USE_CACHE = os.getenv("USE_CACHE", "1") not in ("0", "false", "False")

# --- paths ----------------------------------------------------------------
RAW_DIR = PROJECT_ROOT / "raw"
DATA_DIR = PROJECT_ROOT / "data"
EXPORT_DIR = PROJECT_ROOT / "exports"

# as an independent second source for the coverage comparison.
DB_PATH = DATA_DIR / "ticketmaster.sqlite"

# --- what to collect ------------------------------------------------------
STATE_CODE = os.getenv("STATE_CODE", "CO")

# Ticketmaster's classification taxonomy is segment > genre > subGenre.
# These two ids are stable and are what the Ticketmaster website itself uses.
SEGMENT_MUSIC = "KZFzniwnSyZfZ7v7nJ"
GENRE_DANCE_ELECTRONIC = "KnvZfZ7vAvF"

# Collect all music by default. Narrow to electronic only by setting
# GENRE_ID=KnvZfZ7vAvF in .env -- but collecting all music is more useful,
# because it lets you compare electronic against everything else.
SEGMENT_ID = os.getenv("SEGMENT_ID", SEGMENT_MUSIC)
GENRE_ID = os.getenv("GENRE_ID") or None

for _d in (RAW_DIR, DATA_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

def require_api_key() -> str:
    """
    Fail clearly and early, rather than letting the API return a bare 401.

    The two ways this goes wrong in practice: .env was never created, or it was
    created from the template and the placeholder was never replaced.
    """
    if not TM_API_KEY:
        raise RuntimeError(
            "TICKETMASTER_API_KEY is not set.\n"
            "Copy .env.example to .env and paste your Ticketmaster Consumer Key into it."
        )
    if "paste" in TM_API_KEY.lower() or "your" in TM_API_KEY.lower():
        raise RuntimeError(
            "TICKETMASTER_API_KEY still contains the placeholder text from .env.example.\n"
            "Open .env and replace it with your real Consumer Key."
        )
    if len(TM_API_KEY) < 20:
        raise RuntimeError(
            f"TICKETMASTER_API_KEY looks too short ({len(TM_API_KEY)} characters).\n"
            "Ticketmaster consumer keys are 32 characters. Check you copied the\n"
            "Consumer Key and not the Consumer Secret, and that nothing was truncated."
        )
    return TM_API_KEY
