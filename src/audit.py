"""
Data quality audit. Reports; never writes.

    python src/audit.py

Re-derives the cleaning decisions from scratch and compares them against what
was stored, so a rule that stopped firing fails here instead of producing a
plausible number. PASS / WARN / FAIL per check; a FAIL exits non-zero, which
is what stops weekly_run.py from publishing.
"""

from __future__ import annotations

import datetime as dt
import re
import sys

from clean import (NULL_TOKENS, canonical_venues, identity_of, is_electronic,
                   is_junk_attraction, merge_identities, norm_text)
from db import connect

results = []


def report(level: str, label: str, detail: str = "") -> None:
    results.append(level)
    line = f"  {level:<4}  {label}"
    print(line if not detail else f"{line}\n          {detail}")


def check(ok: bool, label: str, detail: str = "", warn_only: bool = False) -> None:
    if ok:
        report("PASS", label)
    else:
        report("WARN" if warn_only else "FAIL", label, detail)


def main() -> None:
    with connect() as conn:
        n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        n_clean = conn.execute("SELECT COUNT(*) FROM events_clean").fetchone()[0]

        print("\n=== COVERAGE ===")
        check(n_events == n_clean,
              f"every event has a cleaned row ({n_clean}/{n_events})",
              "run src/clean.py")

        orphan = conn.execute("""SELECT COUNT(*) FROM events_clean c
                                 LEFT JOIN events e USING(event_id)
                                 WHERE e.event_id IS NULL""").fetchone()[0]
        check(orphan == 0, "no cleaned rows without a source event",
              f"{orphan} orphans")

        stale = conn.execute(
            "SELECT COUNT(DISTINCT cleaned_at) FROM events_clean").fetchone()[0]
        check(stale <= 1, "all rows cleaned in the same pass",
              f"{stale} distinct cleaned_at values", warn_only=True)

        print("\n=== REFERENTIAL INTEGRITY ===")
        for label, sql in (
            ("every event points at a known venue",
             """SELECT COUNT(*) FROM events e LEFT JOIN venues v USING(venue_id)
                WHERE e.venue_id IS NOT NULL AND v.venue_id IS NULL"""),
            ("every lineup row points at a known event",
             """SELECT COUNT(*) FROM event_attractions ea
                LEFT JOIN events e USING(event_id) WHERE e.event_id IS NULL"""),
            ("every lineup row points at a known artist",
             """SELECT COUNT(*) FROM event_attractions ea
                LEFT JOIN attractions a USING(attraction_id)
                WHERE a.attraction_id IS NULL"""),
            ("every observation points at a known event",
             """SELECT COUNT(*) FROM event_observations o
                LEFT JOIN events e USING(event_id) WHERE e.event_id IS NULL"""),
        ):
            n = conn.execute(sql).fetchone()[0]
            check(n == 0, label, f"{n} broken references")

        no_venue = conn.execute(
            "SELECT COUNT(*) FROM events WHERE venue_id IS NULL").fetchone()[0]
        check(no_venue == 0, "no event is missing a venue",
              f"{no_venue} events have no venue", warn_only=True)

        print("\n=== DUPLICATES ===")
        collide = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT dedup_group FROM events_clean
                WHERE NOT is_duplicate AND NOT is_cancelled
                GROUP BY dedup_group HAVING COUNT(*) > 1)""").fetchone()[0]
        check(collide == 0, "no duplicate group keeps two live rows",
              f"{collide} groups keep more than one")

        singled = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT dedup_group FROM events_clean
                GROUP BY dedup_group HAVING SUM(NOT is_duplicate) = 0)""").fetchone()[0]
        check(singled == 0, "no duplicate group lost every row",
              f"{singled} groups have no survivor")

        # Re-derive grouping from scratch and compare against what is stored.
        canon, merges = canonical_venues(conn)
        lineup = {}
        for r in conn.execute("""SELECT ea.event_id, a.name, a.genre_name
                                 FROM event_attractions ea
                                 JOIN attractions a USING(attraction_id)
                                 ORDER BY ea.event_id, ea.position"""):
            lineup.setdefault(r["event_id"], []).append((r["name"], r["genre_name"]))

        rows = conn.execute("""SELECT e.event_id, e.name, e.venue_id, e.local_date,
                                      e.genre_name, e.subgenre_name, e.status,
                                      e.price_min, e.price_max, e.onsale_start,
                                      c.is_duplicate, c.is_cancelled, c.is_electronic,
                                      c.genre_clean, c.subgenre_clean,
                                      c.venue_canonical_id, c.headliner,
                                      c.lineup_size, c.lead_time_days
                               FROM events e JOIN events_clean c USING(event_id)
                            """).fetchall()

        buckets = {}
        for r in rows:
            acts = [(n, g) for n, g in lineup.get(r["event_id"], [])
                    if not is_junk_attraction(n)]
            head = acts[0][0] if acts else None
            cv = canon.get(r["venue_id"], r["venue_id"])
            key = (cv, (r["local_date"] or "?")[:10])
            buckets.setdefault(key, []).append(
                (r, identity_of(head, r["name"]), acts))

        missed = []
        for key, members in buckets.items():
            reps = merge_identities([i for _, i, _ in members])
            live = {}
            for r, ident, _ in members:
                if r["is_duplicate"] or r["is_cancelled"]:
                    continue
                live.setdefault(reps.get(ident, ident), []).append(r["name"])
            for rep, names in live.items():
                if len(names) > 1:
                    missed.append((key, rep, names))
        check(not missed, "independent re-derivation finds no missed duplicate",
              f"{len(missed)} clusters: " +
              "; ".join(f"{k[1]} {n}" for k, _, n in missed[:3]))

        print("\n=== VENUES ===")
        seen = {}
        unmerged = []
        for v in conn.execute("SELECT venue_id, name, city FROM venues"):
            k = (norm_text(v["name"]), norm_text(v["city"] or ""))
            if k in seen and canon.get(v["venue_id"]) != canon.get(seen[k]):
                unmerged.append(f"{v['name']}, {v['city']}")
            seen.setdefault(k, v["venue_id"])
        check(not unmerged, "no two venues share a name and city unmerged",
              ", ".join(unmerged[:5]))
        report("PASS", f"{len(merges)} venue families merged")

        nullcv = sum(1 for r in rows if not r["venue_canonical_id"])
        check(nullcv == no_venue, "every event carries a canonical venue",
              f"{nullcv} rows without one", warn_only=True)

        print("\n=== CATEGORIZATION ===")
        leaked = [r["genre_clean"] for r in rows
                  if r["genre_clean"] and r["genre_clean"].lower() in NULL_TOKENS]
        leaked += [r["subgenre_clean"] for r in rows
                   if r["subgenre_clean"] and r["subgenre_clean"].lower() in NULL_TOKENS]
        check(not leaked, "no placeholder string survives as a genre",
              f"{len(leaked)} leaked, e.g. {leaked[:3]}")

        wrong = 0
        for key, members in buckets.items():
            for r, _, acts in members:
                want = is_electronic(r["genre_clean"], r["subgenre_clean"],
                                     [g for _, g in acts if g])
                if want != bool(r["is_electronic"]):
                    wrong += 1
        check(wrong == 0, "is_electronic matches the rules it claims to apply",
              f"{wrong} rows disagree")

        badsize = 0
        for key, members in buckets.items():
            for r, _, acts in members:
                if r["lineup_size"] != len(acts):
                    badsize += 1
        check(badsize == 0, "lineup_size counts only real artists",
              f"{badsize} rows disagree")

        junk_head = [r["headliner"] for r in rows
                     if r["headliner"] and is_junk_attraction(r["headliner"])]
        check(not junk_head, "no ticket product is billed as a headliner",
              f"{len(junk_head)} found, e.g. {junk_head[:3]}")

        elec = sum(1 for r in rows if r["is_electronic"]
                   and not r["is_duplicate"] and not r["is_cancelled"])
        nogenre = sum(1 for r in rows if not r["genre_clean"])
        report("PASS", f"{elec} live electronic events; {nogenre} rows have no genre")

        print("\n=== FIELD SANITY ===")
        baddate = [r["local_date"] for r in rows
                   if r["local_date"] and not re.match(r"^\d{4}-\d{2}-\d{2}", r["local_date"])]
        check(not baddate, "every date parses as YYYY-MM-DD", f"{len(baddate)} malformed")

        nodate = sum(1 for r in rows if not r["local_date"])
        check(nodate == 0, "no event is missing a date", f"{nodate} missing",
              warn_only=True)

        today = dt.date.today()
        past = sum(1 for r in rows if r["local_date"]
                   and r["local_date"][:10] < today.isoformat()
                   and not r["is_duplicate"])
        report("PASS", f"{past} events already in the past (kept as archive)")

        badprice = sum(1 for r in rows
                       if r["price_min"] is not None and r["price_max"] is not None
                       and r["price_min"] > r["price_max"])
        check(badprice == 0, "no event has a minimum price above its maximum",
              f"{badprice} inverted")

        negprice = sum(1 for r in rows
                       if (r["price_min"] or 0) < 0 or (r["price_max"] or 0) < 0)
        check(negprice == 0, "no negative prices", f"{negprice} negative")

        noprice = sum(1 for r in rows if r["price_min"] is None)
        report("PASS", f"{noprice} of {len(rows)} events have no published price")

        neglead = sum(1 for r in rows if (r["lead_time_days"] or 0) < 0)
        check(neglead == 0, "no event went on sale after it happened",
              f"{neglead} negative lead times", warn_only=True)

        print("\n=== ARCHIVE ===")
        unobserved = conn.execute("""SELECT COUNT(*) FROM events e
                                     WHERE NOT EXISTS (SELECT 1 FROM event_observations o
                                     WHERE o.event_id = e.event_id)""").fetchone()[0]
        check(unobserved == 0, "every event has at least one observation",
              f"{unobserved} never observed")

        days = conn.execute(
            "SELECT COUNT(DISTINCT substr(observed_at,1,10)) FROM event_observations"
        ).fetchone()[0]
        report("PASS" if days > 1 else "WARN",
               f"{days} distinct collection day(s) recorded",
               "" if days > 1 else "the archive only becomes useful across weeks")

    fails = results.count("FAIL")
    warns = results.count("WARN")
    print("\n" + "=" * 58)
    print(f"  {results.count('PASS')} passed, {warns} warnings, {fails} failures")
    print("=" * 58 + "\n")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
