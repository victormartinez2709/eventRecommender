"""
Round two. The profile endpoint reports that these artists DO have upcoming
events, so the data is visible to this key -- only the event list comes back
empty. That points at request shape rather than permissions.

Main suspect: Bandsintown's documentation writes the path with a TRAILING SLASH
("/artists/{name}/events/?app_id=..."), and our client omits it.

    python src/diagnose_events2.py

Prints no secrets.
"""

from __future__ import annotations

from bit_client import BandsintownClient, encode_artist_key

# (name, bandsintown id, upcoming_event_count the profile endpoint reported)
ARTISTS = [
    ("MGNA Crrrta", "15559410", 32),
    ("Ninajirachi", "13058776", 20),
    ("Amelie Lens", "12760751", 6),
]


def main() -> None:
    client = BandsintownClient()
    print("Profile endpoint says these artists have upcoming events.")
    print("Testing whether a trailing slash on /events/ changes anything.\n")
    print(f"{'artist':<14} {'addressed by':<10} {'slash':<7} {'date':<10} {'HTTP':<6} {'events'}")
    print("-" * 66)

    hits = []
    for name, artist_id, expected in ARTISTS:
        for how, key in (("name", encode_artist_key(name)), ("id_", f"id_{artist_id}")):
            for slash_label, suffix in (("no", "/events"), ("yes", "/events/")):
                for date in ("upcoming", "all"):
                    status, payload = client._get(
                        f"/artists/{key}{suffix}", params={"date": date}, kind="diagnose2"
                    )
                    count = len(payload) if isinstance(payload, list) else "-"
                    print(f"{name:<14} {how:<10} {slash_label:<7} {date:<10} "
                          f"{str(status):<6} {count}")
                    if isinstance(count, int) and count > 0:
                        hits.append((name, how, slash_label, date, count))

    print()
    if hits:
        print("*** WORKING COMBINATIONS ***")
        for name, how, slash_label, date, count in hits:
            print(f"  {name}: by {how}, trailing slash = {slash_label}, date={date} -> {count} events")
        print("\nRequest shape was the problem. Send this to Claude and the crawler gets fixed.")
    else:
        print("Still nothing, in any combination.")
        print("The profile endpoint reports events exist but the list endpoint")
        print("returns none, so this is an access limit on your key rather than")
        print("a bug we can code around. Send this to Claude.")


if __name__ == "__main__":
    main()
