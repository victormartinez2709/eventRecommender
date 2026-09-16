"""
Work out why the events endpoint returns an empty list.

Tries the same well-known artist several ways and reports how many events each
variant returns. Prints no secrets: the API key is stripped from every URL.

    python src/diagnose_events.py
"""

from __future__ import annotations

import json
import urllib.parse

from bit_client import BandsintownClient, encode_artist_key

# Amelie Lens tours constantly, so any variant that works must return events.
NAME = "Amelie Lens"
ARTIST_ID = "12760751"

VARIANTS = [
    ("by name, date=all",        f"/artists/{encode_artist_key(NAME)}/events",     {"date": "all"}),
    ("by name, no date param",   f"/artists/{encode_artist_key(NAME)}/events",     {}),
    ("by name, date=upcoming",   f"/artists/{encode_artist_key(NAME)}/events",     {"date": "upcoming"}),
    ("by name, date=past",       f"/artists/{encode_artist_key(NAME)}/events",     {"date": "past"}),
    ("by name, explicit range",  f"/artists/{encode_artist_key(NAME)}/events",     {"date": "2015-01-01,2026-12-31"}),
    ("by id_, date=all",         f"/artists/id_{ARTIST_ID}/events",                {"date": "all"}),
    ("by id_, no date param",    f"/artists/id_{ARTIST_ID}/events",                {}),
    ("by id_, date=upcoming",    f"/artists/id_{ARTIST_ID}/events",                {"date": "upcoming"}),
]


def main() -> None:
    client = BandsintownClient()
    print(f"Testing the events endpoint with {NAME} (id {ARTIST_ID})\n")
    print(f"{'variant':<28} {'HTTP':<6} {'type':<8} {'events'}")
    print("-" * 60)

    results = []
    for label, path, params in VARIANTS:
        status, payload = client._get(path, params=params, kind="diagnose")
        kind = type(payload).__name__
        count = len(payload) if isinstance(payload, list) else "-"
        print(f"{label:<28} {str(status):<6} {kind:<8} {count}")
        results.append((label, count))

    print()
    working = [label for label, count in results if isinstance(count, int) and count > 0]
    if working:
        print("WORKING variants:")
        for label in working:
            print(f"  - {label}")
        print("\nThe endpoint is fine; the request shape was wrong. Send this to Claude.")
    else:
        print("No variant returned events.")
        print("That points at the API key being scoped to your own artist only,")
        print("which Bandsintown's terms allow. Send this output to Claude.")


if __name__ == "__main__":
    main()
