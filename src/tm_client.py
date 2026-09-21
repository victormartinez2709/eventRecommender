"""
A polite client for the Ticketmaster Discovery API.

Responsibilities:
  1. Stay inside the published limits: 5 requests/second, 5000 calls/day.
  2. Retry throttling and server errors rather than losing a slice.
  3. Write every raw response to disk before anything parses it.

Quick test once your .env has a key:
    python src/tm_client.py
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import time
from pathlib import Path

import requests

import cache
from config import (DAILY_BUDGET, MIN_INTERVAL, RAW_DIR, USE_CACHE,
                    USER_AGENT, require_api_key)

BASE_URL = "https://app.ticketmaster.com/discovery/v2"


class QuotaExhausted(RuntimeError):
    """Raised when the daily call budget is used up, so a run stops cleanly."""


class TicketmasterClient:
    def __init__(self, min_interval: float = MIN_INTERVAL, raw_dir: Path = RAW_DIR):
        self.api_key = require_api_key()
        self.min_interval = min_interval
        self.raw_dir = Path(raw_dir)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_call = 0.0
        self.calls_made = 0
        self.cache_hits = 0
        self.use_cache = USE_CACHE
        self.quota_remaining: int | None = None

    # -- internals ----------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        wait = self.min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    @staticmethod
    def _redact(url: str) -> str:
        """Strip the API key before anything is written to disk."""
        return re.sub(r"(apikey=)[^&]*", r"\1REDACTED", url)

    def _write_raw(self, kind: str, url: str, status: int, payload) -> None:
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        out_dir = self.raw_dir / kind / f"dt={day}"
        out_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "request_url": self._redact(url),
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "http_status": status,
            "payload": payload,
        }
        with gzip.open(out_dir / "part-000.jsonl.gz", "at", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get(self, path: str, params: dict | None = None, kind: str = "misc"):
        """
        One rate-limited GET. Returns (http_status, parsed_payload).

        Raises QuotaExhausted once the daily budget is spent, so a long run
        stops cleanly rather than hammering a closed door.
        """
        params_for_cache = dict(params or {})

        # A cached page costs nothing and returns instantly. Past date windows
        # are cached for months; near-future windows for hours. See cache.py.
        if self.use_cache:
            hit = cache.get(path, params_for_cache)
            if hit is not None:
                self.cache_hits += 1
                return 200, hit

        if self.calls_made >= DAILY_BUDGET:
            raise QuotaExhausted(
                f"Local budget of {DAILY_BUDGET} calls reached. "
                f"The quota resets daily; re-run tomorrow to continue."
            )

        params = dict(params or {})
        params["apikey"] = self.api_key
        url = f"{BASE_URL}{path}"

        for attempt in range(1, 5):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == 4:
                    return None, {"_error": str(exc)}
                time.sleep(2 ** attempt)
                continue

            self.calls_made += 1

            # Ticketmaster reports remaining quota on every response.
            remaining = resp.headers.get("Rate-Limit-Available")
            if remaining is not None:
                try:
                    self.quota_remaining = int(remaining)
                except ValueError:
                    pass

            if resp.status_code == 429:
                # Either the per-second limit or the daily quota.
                if self.quota_remaining == 0:
                    raise QuotaExhausted("Ticketmaster reports 0 calls remaining today.")
                time.sleep(2 ** attempt)
                continue

            if resp.status_code in (500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue

            payload = None
            if resp.text.strip():
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {"_unparseable": resp.text[:1000]}

            self._write_raw(kind, resp.url, resp.status_code, payload)

            if self.use_cache and resp.status_code == 200 and isinstance(payload, dict):
                cache.put(path, params_for_cache, payload)

            return resp.status_code, payload

        return None, None

    # -- public API ---------------------------------------------------------

    def search_events(self, page: int = 0, size: int = 200, **filters):
        """
        One page of event search results.

        Deep paging is capped at the 1000th item (size * page < 1000), so the
        caller must slice by date rather than paging indefinitely.
        """
        params = {"page": page, "size": size, **filters}
        return self.get("/events.json", params=params, kind="events")

    def get_attraction(self, attraction_id: str):
        return self.get(f"/attractions/{attraction_id}.json", kind="attractions")

    def search_classifications(self, page: int = 0, size: int = 200):
        return self.get("/classifications.json",
                        params={"page": page, "size": size}, kind="classifications")


if __name__ == "__main__":
    from config import SEGMENT_ID, STATE_CODE

    client = TicketmasterClient()
    status, payload = client.search_events(
        size=3, stateCode=STATE_CODE, segmentId=SEGMENT_ID, sort="date,asc")

    print(f"HTTP {status} | quota remaining: {client.quota_remaining} "
          f"| cache hits: {client.cache_hits}")

    if status == 401:
        print("\n401 Unauthorized. The key reached Ticketmaster and was rejected.")
        print("Most likely one of:")
        print("  - .env holds the Consumer SECRET rather than the Consumer KEY")
        print("  - the key was only just created and is not active yet (wait a few minutes)")
        print("  - the key was copied with a stray space or line break")
        print("\nCheck the key at https://developer-acct.ticketmaster.com/user/login")
        raise SystemExit(1)

    if status == 429:
        print("\n429. Either the 5 requests/second limit or the daily quota of 5000.")
        raise SystemExit(1)

    if not isinstance(payload, dict):
        print("Unexpected response:", payload)
        raise SystemExit(1)

    total = (payload.get("page") or {}).get("totalElements")
    print(f"total {STATE_CODE} music events visible: {total}\n")

    for ev in (payload.get("_embedded") or {}).get("events", []):
        dates = (ev.get("dates") or {}).get("start") or {}
        venues = (ev.get("_embedded") or {}).get("venues") or [{}]
        acts = (ev.get("_embedded") or {}).get("attractions") or []
        cls = (ev.get("classifications") or [{}])[0]
        prices = ev.get("priceRanges") or [{}]
        print(f"  {ev.get('name')}")
        print(f"    {dates.get('localDate')} {dates.get('localTime') or ''} "
              f"at {venues[0].get('name')} ({venues[0].get('city', {}).get('name')})")
        print(f"    genre: {(cls.get('segment') or {}).get('name')} / "
              f"{(cls.get('genre') or {}).get('name')} / "
              f"{(cls.get('subGenre') or {}).get('name')}")
        print(f"    lineup: {', '.join(a.get('name', '?') for a in acts) or '(none listed)'}")
        print(f"    price: {prices[0].get('min')}-{prices[0].get('max')} "
              f"{prices[0].get('currency') or ''}\n")
