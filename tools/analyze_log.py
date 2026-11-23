# -*- coding: utf-8 -*-
"""Read VERA20k's ra2.log and judge what the AI actually built.

    python tools/analyze_log.py --log "<游戏目录>/logs/ra2.log"
    python tools/analyze_log.py --log ... --session last --json
    python tools/analyze_log.py --log ... --match 2 --strict

VERA20k logs one line per successful AI building placement::

    [<ts> INFO  vera20k_core::sim::ai_base_building] <House> placed <TYPE> at (x, y)

That line is printed *after* ``place_building`` succeeded, so the log is an
exact record of what reached the map -- not of what was planned.  The gap
between the two is the single most misread signal in this project (a house
can plan 40 defences and land 5), which is why this tool only ever counts
placements.

One ``vera20k.exe`` run appends to the same log and can hold several matches;
a session is split at ``VERA20k <version> starting`` and, inside one launch,
another match starts at ``sim::runtime] Initialized authored native``.

The checks below are the acceptance gates from ``docs/ai-tuning-playbook.md``.
They judge STRUCTURE (did the tech tree come up, in what order, in what
proportions), never strength -- balance is the player's call.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

#: A launch of the game.
SESSION_RE = re.compile(r"VERA20k (\S+) starting")
#: A second match inside one launch (map reload without a new process).
MATCH_RE = re.compile(r"sim::runtime\] Initialized authored native")
#: One successful AI building placement.
PLACED_RE = re.compile(
    r"\] (\S+) placed (\S+) at \((\d+), (\d+)\)"
)
#: The ISO timestamp at the head of every log line.
STAMP_RE = re.compile(r"^\[(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z")
#: An MCV that could not deploy where it stood.
BLOCKED_RE = re.compile(r"MCV deploy blocked at origin \((\d+), (\d+)\)")

#: Defence buildings, per side.  ``YAGGUN``/``NATBNK`` are Yuri's.
DEFENCES = {
    "GAPILL", "ATESLA", "NASAM",           # Allied
    "NALASR", "NABNKR", "TESLA", "NAFLAK",  # Soviet
    "YAGGUN", "NATBNK",                    # Yuri
}
WALLS = {"GAWALL", "NAWALL", "GAFWLL"}
#: Anti-air defences.  The picker chooses a category (air/armor/infantry) before
#: the building, so these only appear when the air category wins -- see
#: docs/ai-tuning-playbook.md.  Tracked separately because "too little AA" is
#: invisible in the per-family shares.
AA_DEFENCES = {"NASAM", "NAFLAK", "YAGGUN"}
POWER = {"GAPOWR", "NAPOWR", "YAPOWR"}
REFINERIES = {"GAREFN", "NAREFN", "YAREFN"}
BARRACKS = {"GAPILE", "NAHAND", "YABRCK"}
WAR_FACTORIES = {"GAWEAP", "NAWEAP", "YAWEAP"}
TECH = {"GATECH", "NATECH", "YATECH"}
RADARS = {"GAAIRC", "NARADR", "AMRADR", "NAPSIS"}
DEPOTS = {"GADEPT", "NADEPT", "YADEPT"}
#: MCV prerequisites: AMCV GAWEAP+GADEPT, SMCV NAWEAP+NADEPT,
#: PCV YAWEAP+YAGRND (YADEPT is commented out in the retail rules).
MCVS = {"AMCV", "SMCV", "PCV"}

#: The tech-tree order the AI is expected to come up in.
ORDER = [
    ("power", POWER),
    ("refinery", REFINERIES),
    ("barracks", BARRACKS),
    ("war factory", WAR_FACTORIES),
    ("radar", RADARS),
    ("tech", TECH),
    ("depot", DEPOTS),
]

# ------------------------------------------------------------------ gates
#: A house must place at least this many buildings before its shape is judged.
MIN_PLACEMENTS = 25
#: ``GAWEAP``/``NAWEAP`` first appears within this share of the placement list.
WAR_FACTORY_BY = 0.25
#: Defence share of one house's placements.
DEFENCE_MIN = 0.10
#: Wall share of one house's placements (walls are nodes stolen from defence).
WALL_MAX = 0.15
#: One type's share of one house's placements (power plants are exempt).
TYPE_MAX = 0.30
#: Placements of the same type on one cell.
SAME_CELL_MAX = 3
#: Anti-air share of one house's defences.  Retail's ``0/0/25`` shape kept the
#: Allied and Soviet AA guns air-only, which measured 12-17% of defences; the
#: mod gives them Yuri's ``25/10/25`` shape so they compete in every category.
AA_MIN = 0.20


def read_sessions(path):
    """Split the log into launches, then into matches.

    Returns ``[(session_index, match_index, [lines])]`` with ``match_index``
    1-based inside its launch.
    """
    groups = []
    session = -1
    match = 0
    current = None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if SESSION_RE.search(line):
                session += 1
                match = 1
                current = []
                groups.append((session, match, current))
                continue
            if current is None:
                continue
            if MATCH_RE.search(line):
                match += 1
                current = []
                groups.append((session, match, current))
                continue
            current.append(line)
    return groups


def parse(groups):
    """Per (session, match): the placements, the blocked MCVs and the houses.

    A placement is ``(type, (x, y), seconds_since_midnight)``; the time comes
    from the line's own ISO stamp so rebuild gaps can be measured.
    """
    out = []
    for session, match, lines in groups:
        houses = defaultdict(list)
        blocked = 0
        for line in lines:
            placed = PLACED_RE.search(line)
            if placed:
                house, type_id, x, y = placed.groups()
                stamp = STAMP_RE.match(line)
                seconds = (
                    int(stamp.group(4)) * 3600 + int(stamp.group(5)) * 60
                    + int(stamp.group(6))
                ) if stamp else 0
                houses[house].append((type_id, (int(x), int(y)), seconds))
                continue
            if BLOCKED_RE.search(line):
                blocked += 1
        if houses:
            out.append((session, match, houses, blocked))
    return out


def house_report(placements):
    """Everything one house's placement list says about itself."""
    types = Counter(type_id for type_id, _cell, _ts in placements)
    cells = Counter((type_id, cell) for type_id, cell, _ts in placements)
    first = {}
    for index, (type_id, _cell, _ts) in enumerate(placements):
        first.setdefault(type_id, index)
    total = len(placements)

    families = {}
    for name, members in ORDER:
        count = sum(types[m] for m in members if m in types)
        earliest = min(
            (first[m] for m in members if m in first), default=None
        )
        families[name] = {"count": count, "first_index": earliest}

    defence = sum(types[t] for t in DEFENCES if t in types)
    aa = sum(types[t] for t in AA_DEFENCES if t in types)
    walls = sum(types[t] for t in WALLS if t in types)
    return {
        "total": total,
        "types": dict(types.most_common()),
        "first_index": first,
        "families": families,
        "defence": defence,
        "defence_share": defence / total if total else 0.0,
        "aa": aa,
        "aa_share": aa / defence if defence else 0.0,
        "walls": walls,
        "wall_share": walls / total if total else 0.0,
        "depots": sum(types[t] for t in DEPOTS if t in types),
        "worst_cell": cells.most_common(3),
        "repeats": max(cells.values()) if cells else 0,
    }


def judge(house, report):
    """Apply the acceptance gates to one house.  Returns ``[(ok, text)]``."""
    checks = []
    total = report["total"]
    if total < MIN_PLACEMENTS:
        return [(
            None,
            "only %d placements (below the %d needed to judge shape)"
            % (total, MIN_PLACEMENTS),
        )]

    war_factory = report["families"]["war factory"]
    if war_factory["first_index"] is None:
        checks.append((False, "no war factory at all"))
    else:
        share = war_factory["first_index"] / total
        checks.append((
            share <= WAR_FACTORY_BY,
            "war factory first at #%d/%d (%.0f%%, gate %.0f%%)"
            % (war_factory["first_index"] + 1, total, share * 100,
               WAR_FACTORY_BY * 100),
        ))

    checks.append((
        report["defence_share"] >= DEFENCE_MIN,
        "defences %d (%.0f%%, gate %.0f%%)"
        % (report["defence"], report["defence_share"] * 100, DEFENCE_MIN * 100),
    ))
    checks.append((
        report["wall_share"] <= WALL_MAX,
        "walls %d (%.0f%%, gate <=%.0f%%)"
        % (report["walls"], report["wall_share"] * 100, WALL_MAX * 100),
    ))
    checks.append((
        report["aa_share"] >= AA_MIN,
        "AA defences %d of %d (%.0f%% of defences, gate %.0f%%)"
        % (report["aa"], report["defence"], report["aa_share"] * 100,
           AA_MIN * 100),
    ))

    # Power plants are exempt: a big base genuinely needs a lot of them and
    # ``AIExtra``/``BuildSpeed`` refill power on demand.
    offenders = [
        (type_id, count) for type_id, count in report["types"].items()
        if type_id not in POWER and count / total > TYPE_MAX
    ]
    checks.append((
        not offenders,
        "no type over %.0f%%%s" % (
            TYPE_MAX * 100,
            "" if not offenders else " (worst: %s %d/%d)" % (
                offenders[0][0], offenders[0][1], total),
        ),
    ))
    checks.append((
        report["repeats"] <= SAME_CELL_MAX,
        "same type on one cell at most %dx (gate %dx)%s"
        % (report["repeats"], SAME_CELL_MAX,
           "" if report["repeats"] <= SAME_CELL_MAX else " at "
           + ", ".join("%s %d,%d x%d" % (type_id, cell[0], cell[1], count)
                       for (type_id, cell), count in report["worst_cell"])),
    ))
    return checks


def report_rebuilds(matches, gap_seconds):
    """Count "this type came back after a gap, somewhere else".

    The engine does not log a building being lost, so a rebuild has to be
    inferred: the same type landing again after ``gap_seconds`` of silence for
    that type, on a different cell.  That is also what the mod's rebuild
    mechanism produces -- a lost building's plan node is replanned, its old cell
    is cleared and the site search picks a new one -- so the pattern is a fair
    proxy.  It cannot separate a rebuild from a slow new build, so treat the
    numbers as advisory and read them next to the gate report.
    """
    total = 0
    reported = 0
    for session, match, houses, _blocked in matches:
        print("=" * 78)
        print("session %d, match %d: rebuild-ish events "
              "(same type, >=%ds later, different cell)"
              % (session + 1, match, gap_seconds))
        for house in sorted(houses):
            per_type = defaultdict(list)
            for type_id, cell, seconds in houses[house]:
                per_type[type_id].append((seconds, cell))
            events = Counter()
            for type_id, entries in per_type.items():
                for (previous_ts, previous_cell), (ts, cell) in zip(
                        entries, entries[1:]):
                    if cell != previous_cell and ts - previous_ts >= gap_seconds:
                        events[type_id] += 1
            if not events:
                continue
            reported += 1
            total += sum(events.values())
            print("  %-12s %3d  %s"
                  % (house, sum(events.values()),
                     ", ".join("%s x%d" % pair for pair in events.most_common(6))))
    print("=" * 78)
    print("%d rebuild-ish event(s) across %d house(s)" % (total, reported))
    return total


def report_text(matches, strict):
    failures = 0
    judged = 0
    for session, match, houses, blocked in matches:
        print("=" * 78)
        print("session %d, match %d: %d houses placed buildings, "
              "%d MCV deploy refusals" % (session + 1, match, len(houses), blocked))
        for house in sorted(houses, key=lambda h: -len(houses[h])):
            report = house_report(houses[house])
            print("-" * 78)
            print("%s: %d placements, %d types"
                  % (house, report["total"], len(report["types"])))
            order = []
            for name, family in report["families"].items():
                if family["first_index"] is None:
                    order.append("%s=0" % name)
                else:
                    order.append("%s=%d(#%d)" % (
                        name, family["count"], family["first_index"] + 1))
            print("  families: " + "  ".join(order))
            print("  top types: " + "  ".join(
                "%s x%d" % pair for pair in list(report["types"].items())[:6]))
            print("  AA: %d of %d defences (%.0f%%)"
                  % (report["aa"], report["defence"], report["aa_share"] * 100))
            for ok, text in judge(house, report):
                if ok is None:
                    print("  SKIP  " + text)
                    continue
                judged += 1
                if not ok:
                    failures += 1
                print("  %s  %s" % ("PASS" if ok else "FAIL", text))
        # A house that never places a depot cannot rebuild its MCV (the MCV
        # prerequisites name one), which is the whole point of this exercise.
        without = [h for h in houses if house_report(houses[h])["depots"] == 0]
        if without:
            print("  NOTE  no depot placed by: " + ", ".join(sorted(without)))
    print("=" * 78)
    print("%d gate(s) judged, %d failed" % (judged, failures))
    return 1 if (strict and failures) else 0


def report_json(matches):
    payload = []
    for session, match, houses, blocked in matches:
        payload.append({
            "session": session + 1,
            "match": match,
            "blocked_mcv": blocked,
            "houses": {
                house: dict(house_report(placements),
                            checks=[
                                {"pass": ok, "detail": text}
                                for ok, text in judge(house, house_report(placements))
                            ])
                for house, placements in houses.items()
            },
        })
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", required=True,
                        help="path to the game log, e.g. <game-dir>/logs/ra2.log")
    parser.add_argument("--session", default="last",
                        help="'last', 'all', or a 1-based session number")
    parser.add_argument("--match", default="all",
                        help="'all' or a 1-based match number inside the session")
    parser.add_argument("--json", action="store_true", help="machine-readable")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when any gate fails")
    parser.add_argument("--rebuilds", nargs="?", type=int, const=20,
                        default=None, metavar="SECONDS",
                        help="report rebuild-ish events instead of the gate "
                             "report (default gap: 20s)")
    args = parser.parse_args()

    matches = parse(read_sessions(args.log))
    if not matches:
        print("%s holds no AI building placements" % args.log)
        return 1

    last = max(session for session, _, _, _ in matches)
    if args.session == "all":
        chosen = matches
    elif args.session == "last":
        chosen = [m for m in matches if m[0] == last]
    else:
        wanted = int(args.session) - 1
        chosen = [m for m in matches if m[0] == wanted]
    if args.match != "all":
        wanted = int(args.match)
        chosen = [m for m in chosen if m[1] == wanted]
    if not chosen:
        print("nothing matched -- available: "
              + ", ".join("session %d match %d" % (s + 1, m)
                          for s, m, _, _ in matches[-5:]))
        return 1

    if args.rebuilds is not None:
        report_rebuilds(chosen, args.rebuilds)
        return 0
    if args.json:
        print(report_json(chosen))
        return 0
    return report_text(chosen, args.strict)


if __name__ == "__main__":
    sys.exit(main())
