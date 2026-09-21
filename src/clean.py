"""
Clean and deduplicate the collected events.

    python src/clean.py

Writes to `events_clean` and never to `events`, so a cleaning rule can be
changed and re-run without re-collecting. Handles four defects found in the
real data: placeholder strings stored as genres, one venue listed under
several ids, ticket tiers listed as artists, and the same show listed twice.
Also derives the fields every later model wants: lead time, weekday, lineup
size, and whether the event is electronic.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re

from db import connect, init_db

# Values Ticketmaster uses to mean "no value". They are strings, not nulls.
NULL_TOKENS = {"undefined", "none", "n/a", "", "unknown"}

# Genres counting as electronic. Compared after norm_text(), which strips
# punctuation, so the sets are normalised at import too -- otherwise
# "Dance/Electronic" could never match "dance electronic".
#
# "trap" is deliberately absent: Ticketmaster files it under Hip-Hop/Rap more
# often than Dance/Electronic, so it pulled rap bills into the electronic set.
_ELECTRONIC_GENRES_RAW = {"dance/electronic", "electronic", "dance"}
_ELECTRONIC_SUBGENRES_RAW = {
    "house", "techno", "trance", "dubstep", "drum and bass", "drum & bass",
    "electronica", "downtempo", "ambient", "breakbeat", "hardcore", "garage",
    "jungle", "idm", "edm", "dance", "electro", "bass", "future bass",
    "deep house", "tech house", "progressive house", "melodic techno",
    "dance/electronic",
}

# Attractions that are not performers. Matched at the start of the name only,
# so a band actually called "Parking Lot Party" is not caught by accident.
_JUNK_ATTRACTION_PREFIXES = (
    "club seating", "premium seating", "platinum seat", "vip package",
    "vip upgrade", "ticket upgrade", "meet and greet", "meet & greet",
    "hotel package", "parking", "shuttle", "suite rental", "box office",
    "lounge access", "merchandise",
)

# Words that carry no identifying information in an event title. Stripping them
# lets "Sara Landry" and "Sara Landry - The HEL Tour" collapse to one show.
TITLE_NOISE = re.compile(
    r"\b(tour|live|presents?|featuring|feat|ft|with|w/|the|a|an|and|"
    r"night|show|concert|experience|official|afterparty|after party|"
    r"vip|ga|general admission|early|late|set|dj set|b2b|"
    r"\d{4})\b", re.IGNORECASE)


def norm_text(value: str | None) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    s = (value or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(value: str | None) -> str:
    """Normalised title with generic promotional words removed."""
    s = norm_text(value)
    s = TITLE_NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# Normalised once, after norm_text exists, so comparisons are like-for-like.
ELECTRONIC_GENRES = {norm_text(g) for g in _ELECTRONIC_GENRES_RAW}
ELECTRONIC_SUBGENRES = {norm_text(g) for g in _ELECTRONIC_SUBGENRES_RAW}


def clean_token(value: str | None) -> str | None:
    """Turn Ticketmaster's "Undefined" / "None" strings into a real NULL."""
    if value is None:
        return None
    return None if value.strip().lower() in NULL_TOKENS else value.strip()


def is_junk_attraction(name: str | None) -> bool:
    """True for ticket products and venue services listed as artists."""
    n = (name or "").strip().lower()
    return any(n.startswith(p) for p in _JUNK_ATTRACTION_PREFIXES)


def is_electronic(genre: str | None, subgenre: str | None,
                  lineup_genres: list[str]) -> bool:
    """
    True if the event's genre or subgenre is electronic, or any artist on the
    bill is. The lineup check catches mixed bills filed under a broader genre,
    and finds about a quarter of all electronic events.
    """
    if norm_text(genre) in ELECTRONIC_GENRES:
        return True
    if norm_text(subgenre) in ELECTRONIC_SUBGENRES:
        return True
    return any(norm_text(g) in ELECTRONIC_GENRES for g in lineup_genres)


def canonical_venues(conn) -> tuple[dict, list]:
    """
    Map each venue id onto one id per real building.

    Two ids are the same venue when they share a city and one name is a
    word-boundary prefix of the other. A prefix test rather than a shared-word
    test keeps "Club Vinyl", "The Basement at Club Vinyl" and "The Rooftop at
    Vinyl" apart. One-word names are skipped. The busiest id wins.

    Returns (mapping, merges).
    """
    venues = [(r["venue_id"], norm_text(r["name"]), norm_text(r["city"] or ""),
               r["name"])
              for r in conn.execute("SELECT venue_id, name, city FROM venues")]

    counts = {r["venue_id"]: r["n"] for r in conn.execute(
        "SELECT venue_id, COUNT(*) n FROM events "
        "WHERE venue_id IS NOT NULL GROUP BY venue_id")}

    # Shortest names first, so a short name becomes the root of its family.
    venues.sort(key=lambda v: (len(v[1]), v[0]))
    parent = {v[0]: v[0] for v in venues}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, (vid_a, name_a, city_a, _) in enumerate(venues):
        if len(name_a.split()) < 2:
            continue
        for vid_b, name_b, city_b, _ in venues[i + 1:]:
            if city_a != city_b or not name_b:
                continue
            if name_b == name_a or name_b.startswith(name_a + " "):
                ra, rb = find(vid_a), find(vid_b)
                if ra != rb:
                    parent[rb] = ra

    families = {}
    for vid, _, _, _ in venues:
        families.setdefault(find(vid), []).append(vid)

    display = {v[0]: v[3] for v in venues}
    mapping, merges = {}, []
    for members in families.values():
        best = max(members, key=lambda v: (counts.get(v, 0), v))
        for vid in members:
            mapping[vid] = best
        if len(members) > 1:
            merges.append((display.get(best), [display.get(v) for v in members
                                               if v != best]))
    return mapping, merges


def merge_identities(identities: list[str]) -> dict:
    """
    Within one venue and date, map each identity onto a representative.

    Two listings of one show usually differ only by a trailing phrase, so a
    word-boundary prefix relation joins them.
    """
    uniq = sorted({i for i in identities if i}, key=lambda s: (len(s), s))
    parent = {i: i for i in uniq}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(uniq):
        for b in uniq[i + 1:]:
            if b == a or b.startswith(a + " "):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    return {i: find(i) for i in uniq}


def identity_of(headliner: str | None, title: str | None) -> str:
    """
    The string saying which show this is, for duplicate grouping.

    Headliner and title must use the same normalisation or they never compare
    equal: one listing resolves via the artist, its twin via the title, and
    the two would disagree about words like "the" and "and".
    """
    for candidate in (headliner, title):
        stripped = norm_title(candidate)
        if stripped:
            return stripped
        plain = norm_text(candidate)
        if plain:
            return plain
    return "unknown"


def dedup_group(venue_id: str | None, local_date: str | None,
                identity: str) -> str:
    """Key identifying one real-world concert: venue, date, and who is playing."""
    blob = f"{venue_id or '?'}|{(local_date or '?')[:10]}|{identity or 'unknown'}"
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def days_between(earlier: str | None, later: str | None) -> int | None:
    """Whole days between two ISO dates, or None if either is missing."""
    def parse(v):
        if not v:
            return None
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    a, b = parse(earlier), parse(later)
    return (b - a).days if a and b else None


def main() -> None:
    init_db()
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    with connect() as conn:
        events = conn.execute(
            """SELECT e.event_id, e.name, e.venue_id, e.local_date, e.status,
                      e.onsale_start, e.genre_name, e.subgenre_name,
                      e.price_min, e.price_max, e.fetched_at
               FROM events e""").fetchall()

        if not events:
            raise SystemExit("No events collected yet. Run collect_events.py first.")

        canon, merges = canonical_venues(conn)
        venue_names = {r["venue_id"]: f"{r['name']}, {r['city']}"
                       for r in conn.execute(
                           "SELECT venue_id, name, city FROM venues")}

        # lineup: every act on the bill, in billing order
        lineup = {}
        for r in conn.execute(
            """SELECT ea.event_id, ea.position, a.name, a.genre_name
               FROM event_attractions ea
               JOIN attractions a USING(attraction_id)
               ORDER BY ea.event_id, ea.position"""):
            lineup.setdefault(r["event_id"], []).append((r["name"], r["genre_name"]))

        # --- first pass: per-event facts ------------------------------------
        rows, buckets, junk_dropped = [], {}, 0
        for e in events:
            listed = lineup.get(e["event_id"], [])
            acts = [(n, g) for n, g in listed if not is_junk_attraction(n)]
            junk_dropped += len(listed) - len(acts)

            headliner = acts[0][0] if acts else None
            genres = [g for _, g in acts if g]

            genre = clean_token(e["genre_name"])
            subgenre = clean_token(e["subgenre_name"])
            cvenue = canon.get(e["venue_id"], e["venue_id"])
            date_key = (e["local_date"] or "?")[:10]
            identity = identity_of(headliner, e["name"])

            rows.append({
                "event_id": e["event_id"],
                "dedup_group": "",
                "venue_canonical_id": cvenue,
                "headliner": headliner,
                "is_duplicate": 0,
                "is_cancelled": 1 if (e["status"] or "").lower() in
                                ("cancelled", "canceled", "postponed") else 0,
                "genre_clean": genre,
                "subgenre_clean": subgenre,
                "is_electronic": 1 if is_electronic(genre, subgenre, genres) else 0,
                "name_clean": norm_title(e["name"]) or None,
                "lineup_size": len(acts),
                "lead_time_days": days_between(e["onsale_start"], e["local_date"]),
                "weekday": None,
                "cleaned_at": now,
            })
            buckets.setdefault((cvenue, date_key), []).append(identity)
            rows[-1]["_identity"] = identity
            rows[-1]["_bucket"] = (cvenue, date_key)

        # --- second pass: collapse title variants inside each bucket ---------
        reps = {key: merge_identities(ids) for key, ids in buckets.items()}
        groups = {}
        for row, e in zip(rows, events):
            key = row["_bucket"]
            rep = reps[key].get(row["_identity"], row["_identity"])
            row["dedup_group"] = dedup_group(key[0], key[1], rep)
            groups.setdefault(row["dedup_group"], []).append((e, row))

        # weekday, 0 = Sunday ... 6 = Saturday.
        # 1970-01-01 was a Thursday, hence the +4 offset.
        for row, e in zip(rows, events):
            d = days_between("1970-01-01", e["local_date"])
            row["weekday"] = ((d + 4) % 7) if d is not None else None

        # --- duplicate resolution -------------------------------------------
        # Keep the richest row: most artists, then a known price. The rest are
        # flagged rather than deleted, so the decision stays auditable.
        dup_count = 0
        for group, members in groups.items():
            if len(members) < 2:
                continue

            def quality(pair):
                e, row = pair
                return (row["lineup_size"],
                        1 if e["price_min"] is not None else 0,
                        -(len(e["fetched_at"] or "")))
            members.sort(key=quality, reverse=True)
            for _, row in members[1:]:
                row["is_duplicate"] = 1
                dup_count += 1

        payload = [{k: v for k, v in r.items() if not k.startswith("_")}
                   for r in rows]

        conn.execute("DELETE FROM events_clean")
        conn.executemany(
            """INSERT INTO events_clean (event_id, dedup_group, venue_canonical_id,
                 headliner, is_duplicate, is_cancelled, genre_clean,
                 subgenre_clean, is_electronic, name_clean, lineup_size,
                 lead_time_days, weekday, cleaned_at)
               VALUES (:event_id, :dedup_group, :venue_canonical_id, :headliner,
                 :is_duplicate, :is_cancelled, :genre_clean, :subgenre_clean,
                 :is_electronic, :name_clean, :lineup_size, :lead_time_days,
                 :weekday, :cleaned_at)""", payload)

        # --- report ----------------------------------------------------------
        total = len(rows)
        electronic = sum(r["is_electronic"] for r in rows)
        cancelled = sum(r["is_cancelled"] for r in rows)
        no_genre = sum(1 for r in rows if r["genre_clean"] is None)
        no_lineup = sum(1 for r in rows if r["lineup_size"] == 0)
        usable = sum(1 for r in rows if not r["is_duplicate"] and not r["is_cancelled"])

        print(f"\n  events processed        {total:>7}")
        print(f"  duplicates flagged      {dup_count:>7}"
              f"  ({100 * dup_count / max(total, 1):.1f}%)")
        print(f"  cancelled or postponed  {cancelled:>7}")
        print(f"  usable (neither)        {usable:>7}")
        print(f"\n  electronic              {electronic:>7}"
              f"  ({100 * electronic / max(total, 1):.1f}%)")
        print(f"  genre missing/placeholder {no_genre:>5}")
        print(f"  no lineup attached      {no_lineup:>7}"
              f"  ({100 * no_lineup / max(total, 1):.1f}%)")
        print(f"  non-artist listings removed {junk_dropped:>3}")

        lead = [r["lead_time_days"] for r in rows if r["lead_time_days"] is not None]
        if lead:
            lead.sort()
            print(f"\n  median on-sale lead time  {lead[len(lead) // 2]:>5} days"
                  f"   (n={len(lead)})")

        if merges:
            print(f"\n  VENUES MERGED ({len(merges)})")
            for keep, dropped in merges:
                print(f"    {keep}")
                for d in dropped:
                    print(f"      <- {d}")

        # Still sharing a venue and a night. Usually two real bills in one
        # building, but a missed duplicate would show up here, so print them.
        survivors = {}
        for row, e in zip(rows, events):
            if row["is_duplicate"] or row["is_cancelled"]:
                continue
            survivors.setdefault(row["_bucket"], []).append(
                (row["headliner"] or e["name"], e["name"]))
        clustered = {k: v for k, v in survivors.items() if len(v) > 1}
        print(f"\n  venue-nights with more than one surviving event: {len(clustered)}")
        for (cv, day), members in sorted(clustered.items(),
                                         key=lambda kv: -len(kv[1]))[:8]:
            print(f"    {day}  {venue_names.get(cv, cv)}")
            for who, title in members[:4]:
                print(f"        {str(title)[:58]}")
        print()


if __name__ == "__main__":
    main()
