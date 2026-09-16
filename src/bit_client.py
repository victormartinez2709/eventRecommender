"""
A polite, resumable client for the Bandsintown REST API.

Three responsibilities:
  1. Build correct URLs (artist names need careful encoding).
  2. Rate-limit and retry so you never hammer their servers.
  3. Write every raw response to disk before anything parses it.

Quick test once your .env is set up:
    python src/bit_client.py PETSSS
"""

from __future__ import annotations
import datetime as dt
import gzip
import json
import random
import re
import time
import urllib.parse
from pathlib import Path

import requests

from config import MIN_INTERVAL, RAW_DIR, USER_AGENT, require_app_id

BASE_URL = "https://rest.bandsintown.com"


def encode_artist_key(key: str) -> str:
    """
    Turn an artist name into something safe to put in a URL path.

    Bandsintown quirk: '/' and '?' inside an artist name must be DOUBLE-encoded,
    because a single %2F still gets read as a path separator by their router.
    So "AC/DC" has to become "AC%252FDC".

    Keys that already start with 'id_' or 'fbid_' are IDs, not names — pass through.
    """
    if key.startswith(("id_", "fbid_")):
        return key
    # safe="" means "percent-encode everything, including slashes".
    encoded = urllib.parse.quote(key, safe="")
    # Now double-encode the two troublemakers by escaping their percent signs.
    return encoded.replace("%2F", "%252F").replace("%3F", "%253F")


class BandsintownClient:
    def __init__(self, min_interval: float = MIN_INTERVAL, raw_dir: Path = RAW_DIR):
        self.app_id = require_app_id()
        self.min_interval = min_interval
        self.raw_dir = Path(raw_dir)
        # A Session reuses the underlying TCP connection between requests, which is
        # both faster and gentler on the server than opening a new one each time.
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_call = 0.0

    # -- internals ----------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep just long enough that requests are >= min_interval apart."""
        # monotonic() is a clock that only moves forward — unlike time.time(), it
        # can't jump if the OS adjusts the system clock mid-crawl.
        elapsed = time.monotonic() - self._last_call
        wait = self.min_interval - elapsed
        if wait > 0:
            # A little randomness ("jitter") keeps your traffic from looking like
            # a metronome, which is what naive bot detection looks for.
            time.sleep(wait + random.uniform(0.0, 0.3))
        self._last_call = time.monotonic()

    @staticmethod
    def _redact(url: str) -> str:
        """Strip the API key out of a URL before we write it to disk."""
        return re.sub(r"(app_id=)[^&]*", r"\1REDACTED", url)

    def _write_raw(self, kind: str, url: str, status: int, payload) -> None:
        """
        Append one JSON line to today's raw file. This is the single most
        important habit in the whole pipeline: parse bugs become re-parses
        instead of re-crawls, and your thesis stays reproducible.
        """
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        out_dir = self.raw_dir / kind / f"dt={day}"
        out_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "request_url": self._redact(url),
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "http_status": status,
            "payload": payload,
        }
        # "at" = append, text mode. gzip keeps these files ~10x smaller.
        # ensure_ascii=False so accented artist names stay readable in the file.
        with gzip.open(out_dir / "part-000.jsonl.gz", "at", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _get(self, path: str, params: dict | None = None, kind: str = "misc"):
        """
        Do one GET with retries. Returns (http_status, parsed_payload).
        Returns (None, None) if all attempts failed.
        """
        params = dict(params or {})
        params["app_id"] = self.app_id
        url = BASE_URL + path

        for attempt in range(1, 4):  # three tries, then give up
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=20)
            except requests.RequestException as exc:
                # Network-level failure (DNS, timeout, connection reset).
                if attempt == 3:
                    return None, {"_error": str(exc)}
                time.sleep(2 ** attempt)
                continue

            # 429 = too many requests; 5xx = their server is unhappy. Both are
            # worth retrying, with an exponentially growing pause.
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * 2 ** attempt)
                continue

            # Bandsintown returns an empty body for an unknown artist, so guard
            # the JSON parse rather than letting it raise.
            payload = None
            if resp.text.strip():
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {"_unparseable": resp.text[:1000]}

            self._write_raw(kind, resp.url, resp.status_code, payload)
            return resp.status_code, payload

        return None, None

    # -- public API ---------------------------------------------------------

    def get_artist(self, key: str):
        """key is an artist name, or 'id_<bandsintown_id>'."""
        return self._get(f"/artists/{encode_artist_key(key)}", kind="artists")

    def get_events(self, key: str, date: str = "all"):
        """
        date can be 'upcoming', 'past', 'all', or a range 'YYYY-MM-DD,YYYY-MM-DD'.
        Use 'all' for the main crawl — it backfills years of history in one call.
        """
        return self._get(
            f"/artists/{encode_artist_key(key)}/events",
            params={"date": date},
            kind="events",
        )


def _safe_dump(obj, limit: int = 1400) -> str:
    """
    Pretty-print a payload with the API key removed.

    Bandsintown echoes your app_id back inside the artist "url" field, so a plain
    dump of the response puts your key on screen (and into any screenshot of it).
    """
    return re.sub(r"(app_id=)[^\"&]*", r"\1REDACTED", json.dumps(obj, indent=2))[:limit]


if __name__ == "__main__":
    import sys

    who = sys.argv[1] if len(sys.argv) > 1 else "PETSSS"
    client = BandsintownClient()

    status, artist = client.get_artist(who)
    print(f"--- artist lookup: {who} (HTTP {status}) ---")
    print(_safe_dump(artist))

    status, events = client.get_events(who, date="all")
    count = len(events) if isinstance(events, list) else 0
    print(f"\n--- events: HTTP {status}, {count} events ---")
    if count:
        print(_safe_dump(events[0]))
