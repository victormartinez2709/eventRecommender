"""
Central configuration. Every other module imports from here, so there is exactly
one place where paths, the API key, and the crawl settings are defined.
"""

from __future__ import annotations
from pathlib import Path
import os

from dotenv import load_dotenv

# __file__ is this file's path. .resolve() makes it absolute, .parent goes up one
# directory. src/config.py -> src/ -> project root. Doing it this way means the
# scripts work no matter which directory you run them from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Reads the .env file and puts its contents into environment variables.
load_dotenv(PROJECT_ROOT / ".env")

# os.getenv returns None if the variable is not set, so we can give a clear error
# later rather than sending the string "None" to the API as a key.
APP_ID = os.getenv("BANDSINTOWN_APP_ID")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "unknown@example.com")

# A descriptive User-Agent is basic API etiquette: it tells the server who you are
# so that if your crawler misbehaves they can email you instead of silently banning you.
USER_AGENT = f"CU-Boulder-APPM-MS-thesis/0.1 (+{CONTACT_EMAIL})"

# float() and int() because environment variables are always strings.
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL_SECONDS", "1.0"))
MAX_DEPTH = int(os.getenv("MAX_DEPTH", "1"))

# Where things live.
RAW_DIR = PROJECT_ROOT / "raw"       # immutable API responses
DATA_DIR = PROJECT_ROOT / "data"     # the SQLite database
EXPORT_DIR = PROJECT_ROOT / "exports"  # Parquet snapshots for modelling
DB_PATH = DATA_DIR / "bandsintown.sqlite"

# The Colorado cities Bandsintown has pages for. The slug is what goes in the URL:
# https://www.bandsintown.com/c/<slug>/<date-range>/genre/<genre>
CO_CITIES = [
    "denver-co",
    "boulder-co",
    "colorado-springs-co",
    "fort-collins-co",
    "aspen-co",
    "vail-co",
    "breckenridge-co",
    "grand-junction-co",
    "durango-co",
    "pueblo-co",
    "steamboat-springs-co",
    "greeley-co",
    "morrison-co",       # Red Rocks
    "englewood-co",      # Fiddler's Green / Gothic
    "lafayette-co",
]

# Bandsintown's own genre slugs. "electronic" is the one you care about, but
# collecting a contrast genre or two makes for a much stronger evaluation chapter.
GENRES = ["electronic"]

# mkdir(parents=True, exist_ok=True) creates the folder and any missing parents,
# and does nothing if it already exists — so importing this module twice is safe.
for _d in (RAW_DIR, DATA_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def require_app_id() -> str:
    """Fail loudly and helpfully if the key is missing, instead of getting a 403."""
    if not APP_ID:
        raise RuntimeError(
            "BANDSINTOWN_APP_ID is not set.\n"
            "Copy .env.example to .env and paste your app_id into it."
        )
    return APP_ID
