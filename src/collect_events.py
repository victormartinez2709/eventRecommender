"""
Collect Colorado events from the Ticketmaster Discovery API.

The one constraint that shapes this file: deep paging is capped at the 1000th
item of any single query (size * page < 1000). A year of Colorado music events
is well over that, so the collector slices the calendar into windows and, when
a window still reports more than 1000 results, splits it in half and tries
again. Every slice is logged with its total and whether it was truncated, so
coverage is measurable rather than assumed.

    python src/collect_events.py                    # the configured window
    python src/collect_events.py --months-back 24   # go further back
    python src/collect_events.py --taxonomy         # also fetch the genre taxonomy

Raw responses are written to raw/; nothing is parsed here. Run normalize_tm.py
afterwards to build the tables.
"""

from __future__ import annotations

import argparse
import datetime as dt

from config import (GENRE_ID, MONTHS_BACK, MONTHS_FORWARD, SEGMENT_ID,
                    STATE_CODE)
from db import connect, init_db
from tm_client import QuotaExhausted, TicketmasterClient

PAGE_SIZE = 200          # the largest page the API accepts
DEEP_PAGING_CAP = 1000   # size * page must stay under this
MIN_SLICE_DAYS = 1       # do not split finer than a single day


def iso(d: dt.date, end: bool = False) -> str:
    """Ticketmaster wants UTC timestamps like 2026-09-17T00:00:00Z."""
    t = "23:59:59" if end else "00:00:00"
    return f"{d.isoformat()}T{t}Z"


def month_edges(months_back: int, months_forward: int) -> list[tuple[dt.date, dt.date]]:
    """Month-long windows spanning the configured range, oldest first."""
    today = dt.date.today()
    first = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    for _ in range(months_back - 1):
        first = (first - dt.timedelta(days=1)).replace(day=1)

    edges, cursor = [], first
    for _ in range(months_back + months_forward + 1):
        nxt = (cursor.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        edges.append((cursor, nxt - dt.timedelta(days=1)))
        cursor = nxt
    return edges


def log_slice(start, end, params, total, pages, truncated) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO collection_log
               (slice_start, slice_end, params, total_elements, pages_fetched,
                truncated, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (start.isoformat(), end.isoformat(), params, total, pages,
             1 if truncated else 0,
             dt.datetime.now(dt.timezone.utc).isoformat()))


def collect_slice(client: TicketmasterClient, start: dt.date, end: dt.date,
                  filters: dict, depth: int = 0) -> int:
    """
    Fetch one date window, splitting it if the API reports more results than
    deep paging can reach. Returns the number of events seen.
    """
    indent = "  " * (depth + 1)
    query = dict(filters, startDateTime=iso(start), endDateTime=iso(end, end=True))

    status, payload = client.search_events(page=0, size=PAGE_SIZE, **query)
    if status != 200 or not isinstance(payload, dict):
        print(f"{indent}{start} to {end}: HTTP {status} — skipped")
        return 0

    page_info = payload.get("page") or {}
    total = page_info.get("totalElements", 0)
    total_pages = page_info.get("totalPages", 0)

    # Too many results to page through: halve the window and recurse.
    span = (end - start).days
    if total > DEEP_PAGING_CAP and span > MIN_SLICE_DAYS:
        mid = start + dt.timedelta(days=span // 2)
        print(f"{indent}{start} to {end}: {total} results, splitting")
        seen = collect_slice(client, start, mid, filters, depth + 1)
        seen += collect_slice(client, mid + dt.timedelta(days=1), end, filters, depth + 1)
        return seen

    truncated = total > DEEP_PAGING_CAP
    reachable = min(total_pages, DEEP_PAGING_CAP // PAGE_SIZE)
    print(f"{indent}{start} to {end}: {total} events, {reachable} page(s)"
          + ("  ** TRUNCATED **" if truncated else ""))

    pages_fetched = 1 if total else 0
    for page in range(1, reachable):
        status, _ = client.search_events(page=page, size=PAGE_SIZE, **query)
        if status != 200:
            break
        pages_fetched += 1

    log_slice(start, end, repr(sorted(filters.items())), total, pages_fetched, truncated)
    return total


def collect_taxonomy(client: TicketmasterClient) -> None:
    """Fetch the full segment/genre/subGenre taxonomy."""
    print("\nFetching the classification taxonomy")
    page = 0
    while True:
        status, payload = client.search_classifications(page=page, size=200)
        if status != 200 or not isinstance(payload, dict):
            break
        info = payload.get("page") or {}
        print(f"  page {page + 1} of {info.get('totalPages', '?')}")
        page += 1
        if page >= info.get("totalPages", 0):
            break


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--months-back", type=int, default=MONTHS_BACK)
    parser.add_argument("--months-forward", type=int, default=MONTHS_FORWARD)
    parser.add_argument("--state", default=STATE_CODE)
    parser.add_argument("--taxonomy", action="store_true",
                        help="also fetch the full genre taxonomy")
    args = parser.parse_args()

    init_db()
    client = TicketmasterClient()

    filters = {"stateCode": args.state, "segmentId": SEGMENT_ID, "sort": "date,asc"}
    if GENRE_ID:
        filters["genreId"] = GENRE_ID

    print(f"\nCollecting {args.state} events")
    print(f"  segment : {SEGMENT_ID}")
    print(f"  genre   : {GENRE_ID or 'all'}")
    print(f"  window  : {args.months_back} months back, {args.months_forward} forward\n")

    total = 0
    try:
        if args.taxonomy:
            collect_taxonomy(client)
        for start, end in month_edges(args.months_back, args.months_forward):
            total += collect_slice(client, start, end, filters)
    except QuotaExhausted as exc:
        print(f"\nStopping: {exc}")

    print(f"\n{total} events seen across all slices.")
    print(f"{client.calls_made} API calls used"
          + (f", {client.quota_remaining} remaining today." if client.quota_remaining
             is not None else "."))
    print("\nNow run:  python src/normalize_tm.py")


if __name__ == "__main__":
    main()
