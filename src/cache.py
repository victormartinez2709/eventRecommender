"""
Response cache for the Ticketmaster API.

Saves quota and time on repeated runs, and ages entries by how far ahead the
query looks: a window already in the past cannot gain events, while next
month changes daily. Keyed by a hash of the request with the API key removed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re

from db import connect, init_db

# How long a cached response stays usable, by how far in the future the query
# reaches. Past windows are effectively frozen; near-future windows move fast.
TTL_PAST_DAYS = 90          # slice ends before today
TTL_NEAR_FUTURE_HOURS = 12  # slice ends within 60 days
TTL_FAR_FUTURE_HOURS = 72   # slice ends beyond that

NEAR_FUTURE_DAYS = 60


def cache_key(path: str, params: dict) -> str:
    """Stable id for a request. The API key is excluded so a key rotation keeps the cache."""
    clean = {k: v for k, v in sorted(params.items()) if k != "apikey"}
    blob = f"{path}?{json.dumps(clean, sort_keys=True)}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _slice_end(params: dict) -> dt.date | None:
    """The end of the requested date window, if there is one."""
    raw = params.get("endDateTime")
    if not raw:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(raw))
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def ttl_seconds(params: dict) -> int:
    """How long this response stays fresh, by how far ahead it looks."""
    end = _slice_end(params)
    today = dt.date.today()

    if end is None:
        return TTL_NEAR_FUTURE_HOURS * 3600
    if end < today:
        return TTL_PAST_DAYS * 86400
    if (end - today).days <= NEAR_FUTURE_DAYS:
        return TTL_NEAR_FUTURE_HOURS * 3600
    return TTL_FAR_FUTURE_HOURS * 3600


def get(path: str, params: dict) -> dict | None:
    """Return the cached payload if present and still fresh."""
    key = cache_key(path, params)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with connect() as conn:
        row = conn.execute(
            "SELECT payload, expires_at FROM api_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if not row or row["expires_at"] <= now:
            return None
        conn.execute(
            "UPDATE api_cache SET hits = hits + 1, last_hit_at = ? WHERE cache_key = ?",
            (now, key))
    try:
        return json.loads(row["payload"])
    except (json.JSONDecodeError, TypeError):
        return None


def put(path: str, params: dict, payload: dict) -> None:
    """Store a response with an expiry chosen by ttl_seconds."""
    key = cache_key(path, params)
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(seconds=ttl_seconds(params))
    safe_params = {k: v for k, v in params.items() if k != "apikey"}

    with connect() as conn:
        conn.execute(
            """INSERT INTO api_cache (cache_key, path, params, payload, fetched_at,
                 expires_at, hits, last_hit_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
               ON CONFLICT(cache_key) DO UPDATE SET
                 payload = excluded.payload,
                 fetched_at = excluded.fetched_at,
                 expires_at = excluded.expires_at""",
            (key, path, json.dumps(safe_params, sort_keys=True),
             json.dumps(payload), now.isoformat(), expires.isoformat()))


def stats() -> dict:
    with connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS entries,
                      COALESCE(SUM(hits), 0) AS hits,
                      SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) AS fresh
               FROM api_cache""",
            (dt.datetime.now(dt.timezone.utc).isoformat(),)).fetchone()
    return dict(row) if row else {}


def purge(expired_only: bool = True) -> int:
    """Delete cache entries. Returns how many went."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with connect() as conn:
        if expired_only:
            cur = conn.execute("DELETE FROM api_cache WHERE expires_at <= ?", (now,))
        else:
            cur = conn.execute("DELETE FROM api_cache")
        return cur.rowcount


if __name__ == "__main__":
    import sys
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "purge":
        print(f"removed {purge(expired_only=False)} cache entries")
    elif len(sys.argv) > 1 and sys.argv[1] == "purge-expired":
        print(f"removed {purge(expired_only=True)} expired entries")
    else:
        s = stats()
        print(f"cache entries : {s.get('entries', 0)}")
        print(f"still fresh   : {s.get('fresh', 0)}")
        print(f"total hits    : {s.get('hits', 0)}")
