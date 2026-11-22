# -*- coding: utf-8 -*-
"""Build the SuperAI mod from a stock Yuri's Revenge rules folder.

The mod is a full replacement of ``rulesmd.ini`` / ``artmd.ini`` / ``aimd.ini``.
This script starts from the retail files, applies a fixed list of edits and
writes them next to the ``mod.ini`` that ships in this repository.

    python tools/build_mod.py --rules-dir "F:/Games/red2" --out mod/SuperAI

``--rules-dir`` must contain the retail ``rulesmd.ini``, ``artmd.ini`` and
``aimd.ini`` (a YR install, or the extracted files next to the game).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil

# --------------------------------------------------------------- rules edits
# key: (retail value, mod value)
RULES_EDITS = {
    "TeamDelays": ("2000,2500,3500", "300,450,600"),
    "MultiplayerAICM": ("400,0,0", "100000,100000,100000"),
    "BuildSpeed": (".7", ".025"),
    # 40 planned base defences per side.  The plan holds this many "-1"
    # (defence) nodes; `choose_building` turns each into a real gun when the
    # house already owns the gun's prerequisites and *deletes* the node
    # otherwise, so early nodes are spent, not postponed.  Retail is 25/20/6.
    "AlliedBaseDefenseCounts": ("25,20,6", "40,40,40"),
    "SovietBaseDefenseCounts": ("25,22,6", "40,40,40"),
    "ThirdBaseDefenseCounts": ("25,22,6", "40,40,40"),
    # Retail turns half the defence draws into walls, and every wall segment is
    # a plan node taken from the defence budget (ProtectWithWall= buildings get
    # a ring each).  Measured before this change: 92 GAWALL vs 63 real defences
    # in one Allied base.  10% keeps the ring as an accent.
    "AIPickWallDefensePercent": ("50,25,10", "10,10,10"),
    # Retail refineries duplicate themselves (`AIExtraRefineries=2,1,0`, see
    # `recalc_base_plan`) *on top of* Ares `AIBuildCounts`.  Yuri's 2x2
    # YAREFN, four copies, plus two random extra insertions, filled 56% of one
    # base plan.  `AIBuildCounts` now covers the count; the duplicate pass is
    # what made refineries swamp everything after them.
    "AIExtraRefineries": ("2,1,0", "0,0,0"),
    # Yuri is a separate problem in two places, and this one key drives both:
    #
    # * `recalc_base_plan` duplicates the refinery `AISlaveMinerNumber - 1`
    #   times when the country owns NO harvester -- and YuriCountry owns
    #   neither HARV nor CMIN.  Retail 4 on hard therefore inserted 3 extra
    #   YAREFNs at random plan positions.  (For Allied/Soviet the same slot is
    #   `AIExtraRefineries`, which is why setting that alone did not help Yuri.)
    # * `node_may_replan` lets a resource-gathering building replan its node as
    #   soon as it is lost, with NO `AIRestrictReplaceTime` wait, for as long as
    #   the house holds fewer than `AISlaveMinerNumber` gatherers.  YAREFN is
    #   the game's only `ResourceGatherer=yes` building, so in a fight Yuri
    #   rebuilds a dying refinery on the same cell forever -- measured: 8
    #   placements on (817,554) in 11 seconds.
    #
    # 2 makes the gate satisfiable (2 refineries, not 4) and halves the
    # duplication.  The slaves (SLAV) are `Slaved=yes`, not `ResourceGatherer=`,
    # so they never count towards it.
    "AISlaveMinerNumber": ("4,3,2", "2,2,2"),
    "Paranoid": ("yes", "no"),
    "TotalAITeamCap": ("30,30,30", "10,10,10"),
    # One defensive team, not zero.  With zero, a house under attack keeps
    # throwing every unit into attack teams and never garrisons; the defence
    # team occupies one of the ten slots.
    "MaximumAIDefensiveTeams": ("2,2,2", "1,1,1"),
    "MinimumAIDefensiveTeams": ("1,1,1", "1,1,1"),
    "UseMinDefenseRule": ("yes", "yes"),
    "AIHateDelays": ("30,50,70", "8,12,18"),
    "AIBaseSpacing": ("1", "1"),
    "AIRestrictReplaceTime": ("400", "120"),
    "AITriggerSuccessWeightDelta": ("20", "50"),
    "AITriggerFailureWeightDelta": ("-50", "0"),
    "DissolveUnfilledTeamDelay": ("5000", "900"),
}

#: Per-section key rewrites, applied inside the named section only.
#:
#: The three repair depots ship `AIBuildThis=no` and the base-plan generator
#: (`recalc_candidate_allowed`) only ever admits a type whose `AIBuildThis` is
#: yes -- so retail ships the *entire* MCV recovery chain unreachable:
#:
#:   AMCV Prerequisite=GAWEAP,GADEPT   SMCV ...=NAWEAP,NADEPT
#:   PCV  Prerequisite=YAWEAP,YAGRND
#:
#: plus three "this house owns zero construction yards" AI triggers and three
#: MCV team types (`Max=1`, script `043F23CC-G` = move somewhere clear and
#: deploy).  With the depots enabled the chain works; without them the AI can
#: never satisfy the MCV prerequisite no matter how much money it has.
SECTION_KEY_EDITS = {
    "GADEPT": {"AIBuildThis": "yes"},
    "NADEPT": {"AIBuildThis": "yes"},
    "YADEPT": {"AIBuildThis": "yes"},
}

#: Comment written beside a rewritten key, replacing the retail one.  Retail's
#: note on these lines reads "taken out to remove useless building - DB",
#: which is exactly the trap this mod is fixing: leaving it in place makes the
#: next reader think the value is still ``no``.
SECTION_KEY_COMMENTS = {
    "AIBuildThis": ";SuperAI: enabled so the AI can build its MCV (see docs/ai-tuning-playbook.md)",
}

#: Ares AIBuildCounts per building type (planned copies per computer base).
#:
#: Ares ``AIBuildCounts`` = how many nodes of that type the base plan holds.
#: Read carefully what the engine does with them, because it is not what the
#: name suggests (``base_plan_generation.rs``, Ares
#: ``HouseClass_GenerateAIBuildList_CountExtra``): for each type, past the
#: construction yard, its FIRST node spawns ``count - 1`` copies, each at a
#: RANDOM position from that node to the end of the plan.  A high count is
#: therefore not "build six power plants first" but "scatter five more power
#: plants across the rest of the plan", pushing the war factory, radar, tech
#: centre and repair depot towards the tail.  Retail Ares defaults are 1.
#:
#: History: a flat 60 (the 1.x setting) produced 403 power plants and 12 war
#: factories, because power is the first type in the list and inherited the
#: largest share of the scatter.  Keep the EARLY types small and the LATE
#: types at their real base count -- the ordering information is what gets
#: destroyed by high counts, not the totals.
BUILD_COUNTS = {
    "GAPOWR": 3, "NAPOWR": 3, "YAPOWR": 3,
    "GAREFN": 2, "NAREFN": 2, "YAREFN": 2,
    "GAPILE": 2, "NAHAND": 2, "YABRCK": 2,
    "GAWEAP": 3, "NAWEAP": 3, "YAWEAP": 3,
    "GATECH": 2, "NATECH": 2, "YATECH": 2,
    "GAAIRC": 1, "NARADR": 1, "AMRADR": 1, "NAPSIS": 1,
    # Now that the depots are in the plan, they must actually be scheduled.
    "GADEPT": 2, "NADEPT": 2, "YADEPT": 1,
    # PCV's prerequisite is YAWEAP,YAGRND (YADEPT is commented out retail).
    "YAGRND": 1,
}

CONSTRUCTION_YARDS = ("GACNST", "NACNST", "YACNST")
REFINERIES = ("GAREFN", "NAREFN", "YAREFN")

#: Retail script used by the three MCV teams: move to a clear spot and deploy.
MCV_DEPLOY_SCRIPT = "043F23CC-G"

#: Our no-assembly attack script.
ATTACK_SCRIPT = "ZAIATK01-G"
ATTACK_SCRIPT_BODY = [
    "[%s]" % ATTACK_SCRIPT,
    "Name=SuperAI Charge",
    "0=0,6",
    "1=49,0",
    "2=0,2",
    "3=0,1",
    "4=0,5",
    "",
]

MAX_ENTRY, MAX_TOTAL, MULTIPLIER = 16, 40, 1


def apply_rules_edits(lines):
    applied = set()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z]+)=(.*?)(\s*;.*)?(\r?\n)?$", line)
        if not m or m.group(1) not in RULES_EDITS:
            continue
        key = m.group(1)
        old, new = RULES_EDITS[key]
        if m.group(2).strip() == old:
            lines[i] = key + "=" + new + (m.group(3) or "") + (m.group(4) or "")
            applied.add(key)
    missing = set(RULES_EDITS) - applied
    if missing:
        raise SystemExit("rules keys not replaced: %r" % sorted(missing))


def insert_after_section_header(lines, section, text):
    for i, line in enumerate(lines):
        if line.strip() == "[" + section + "]":
            lines.insert(i + 1, text)
            return
    raise SystemExit("section [%s] not found" % section)


def apply_section_key_edits(lines):
    """Rewrite keys inside named sections, keeping each line's comment.

    Unlike :data:`RULES_EDITS` these keys are not unique in the file (every
    building has an ``AIBuildThis=``), so the section has to be tracked while
    scanning.  A section whose key does not exist is an error: it means the
    retail file is not the one this script was written against.
    """
    remaining = {name: dict(edits) for name, edits in SECTION_KEY_EDITS.items()}
    section = None
    for i, line in enumerate(lines):
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            section = header.group(1).strip()
            continue
        if section not in remaining:
            continue
        m = re.match(r"^([A-Za-z]+)=(.*?)(\s*;.*)?(\r?\n)?$", line)
        if not m or m.group(1) not in remaining[section]:
            continue
        key = m.group(1)
        comment = SECTION_KEY_COMMENTS.get(key, m.group(3) or "")
        if comment and not comment[0].isspace():
            comment = " " + comment
        lines[i] = key + "=" + remaining[section].pop(key) + comment \
            + (m.group(4) or "")
        if not remaining[section]:
            del remaining[section]
    if remaining:
        raise SystemExit(
            "section keys not replaced: "
            + ", ".join("[%s] %s" % (s, ", ".join(sorted(k)))
                        for s, k in sorted(remaining.items())))


def build_rules(source_dir, out_dir):
    text = open(os.path.join(source_dir, "rulesmd.ini"), "rb").read().decode("latin-1")
    lines = text.splitlines(keepends=True)

    apply_rules_edits(lines)
    apply_section_key_edits(lines)

    # Deployed construction yards reveal the map: no power, no radar needed.
    for yard in CONSTRUCTION_YARDS:
        insert_after_section_header(lines, yard, "SpySat=yes\r\n")

    # VERA extension: computers target the nearest enemy, so FFA games fight.
    if not any(l.startswith("AINearestEnemy=") for l in lines):
        for i, line in enumerate(lines):
            if line.startswith("AISafeDistance="):
                lines.insert(i + 1, "AINearestEnemy=yes\r\n")
                break
        else:
            raise SystemExit("AISafeDistance= not found")

    # Ore-free maps still fund the AI: refineries pay a trickle (oil derrick key).
    for refn in REFINERIES:
        insert_after_section_header(lines, refn, "ProduceCashDelay=60\r\n")
        insert_after_section_header(lines, refn, "ProduceCashAmount=100\r\n")

    # Ares AIBuildCounts: many planned copies of each building type.
    out = []
    inserted = set()
    for line in lines:
        out.append(line)
        m = re.match(r"^\[([^\]]+)\]\s*$", line)
        if m and m.group(1).strip() in BUILD_COUNTS and m.group(1).strip() not in inserted:
            name = m.group(1).strip()
            count = BUILD_COUNTS[name]
            out.append("AIBuildCounts=%d,%d,%d\r\n" % (count, count, count))
            inserted.add(name)
    lines = out

    open(os.path.join(out_dir, "rulesmd.ini"), "wb").write("".join(lines).encode("latin-1"))
    return len(inserted)


class Aimd:
    """Small section-aware editor for aimd.ini."""

    def __init__(self, text):
        self.lines = text.splitlines(keepends=True)
        self.starts = {}
        self.reindex()

    def reindex(self):
        self.starts = {}
        for i, line in enumerate(self.lines):
            m = re.match(r"^\[([^\]]+)\]\s*$", line)
            if m:
                self.starts[m.group(1).strip()] = i

    def bounds(self, name):
        start = self.starts[name]
        end = len(self.lines)
        for index in self.starts.values():
            if start < index < end:
                end = index
        return start + 1, end

    def values(self, name):
        out = {}
        start, end = self.bounds(name)
        for i in range(start, end):
            line = self.lines[i]
            if "=" in line and not line.lstrip().startswith(";"):
                key, value = line.split("=", 1)
                out[key.strip().lower()] = (value.strip(), i)
        return out

    def members(self, name):
        out = []
        start, end = self.bounds(name)
        for i in range(start, end):
            m = re.match(r"^(\d+)\s*=\s*(\d+)\s*,\s*([^,\r\n]+)(.*?)(\r?\n)?$", self.lines[i])
            if m:
                out.append((i, int(m.group(1)), int(m.group(2)), m.group(3).strip(),
                            m.group(4), m.group(5) or ""))
        return out

    def team_ids(self):
        start, end = self.bounds("TeamTypes")
        return [l.split("=", 1)[1].strip() for l in self.lines[start:end] if "=" in l]

    def replace_value(self, index, key, value):
        line = self.lines[index]
        eol = "\r\n" if line.endswith("\r\n") else "\n"
        self.lines[index] = "%s=%s%s" % (key, value, eol)

    def insert_value(self, section, key, value):
        index = self.bounds(section)[0]
        self.lines.insert(index, "%s=%s\r\n" % (key, value))
        self.reindex()

    def text(self):
        return "".join(self.lines)


def build_aimd(source_dir, out_dir):
    text = open(os.path.join(source_dir, "aimd.ini"), "rb").read().decode("latin-1")
    doc = Aimd(text)

    team_ids = doc.team_ids()

    # Retail attack teams exclude engineers, spies, miners and base defences;
    # only their task forces are rescaled, so support teams keep their size.
    exclude = re.compile(
        r"(Engineer|Spy|Capture|Guard|Defense|Miner|MCV|Naval|Bombard|Anti-|Repair|Scout)",
        re.I,
    )
    attack = []
    for tid in team_ids:
        fields = doc.values(tid)
        if fields.get("aggressive", ("", 0))[0].lower() != "yes":
            continue
        if fields.get("isbasedefense", ("", 0))[0].lower() == "yes":
            continue
        if exclude.search(fields.get("name", ("", 0))[0]):
            continue
        attack.append(tid)

    attack_tf = {doc.values(t)[ "taskforce" ][0] for t in attack if "taskforce" in doc.values(t)}
    other_tf = set()
    for tid in team_ids:
        if tid in attack:
            continue
        fields = doc.values(tid)
        if "taskforce" in fields:
            other_tf.add(fields["taskforce"][0])
    shared = attack_tf & other_tf

    scaled = 0
    for task_force in sorted(attack_tf - shared):
        if task_force not in doc.starts:
            continue
        rows, total = [], 0
        for line_no, index, count, unit, rest, eol in doc.members(task_force):
            new_count = min(MAX_ENTRY, count * MULTIPLIER)
            rows.append([line_no, index, count, new_count, unit, rest, eol])
            total += new_count
        if total > MAX_TOTAL:
            over = total - MAX_TOTAL
            for row in sorted(rows, key=lambda r: -r[3]):
                if over <= 0:
                    break
                cut = min(over, max(0, row[3] - row[2]))
                row[3] -= cut
                over -= cut
        for line_no, index, count, new_count, unit, rest, eol in rows:
            if new_count != count:
                doc.lines[line_no] = "%d=%d,%s%s%s" % (index, new_count, unit, rest, eol)
        scaled += 1

    # Register and append the no-assembly attack script.
    start, end = doc.bounds("ScriptTypes")
    next_index = 0
    for i in range(start, end):
        m = re.match(r"^(\d+)=", doc.lines[i])
        if m:
            next_index = max(next_index, int(m.group(1)) + 1)
    doc.lines.insert(end, "%d=%s\r\n" % (next_index, ATTACK_SCRIPT))
    doc.lines.extend(line + "\r\n" for line in ATTACK_SCRIPT_BODY)
    doc.reindex()

    # Every team charges except the three MCV teams, which deploy expansions.
    switched = 0
    for tid in team_ids:
        fields = doc.values(tid)
        name = fields.get("name", ("", 0))[0]
        if re.search(r"(^|\W)MCV(\W|$)", name, re.I):
            if "script" in fields:
                doc.replace_value(fields["script"][1], "Script", MCV_DEPLOY_SCRIPT)
            if "aggressive" in fields:
                doc.replace_value(fields["aggressive"][1], "Aggressive", "no")
            continue
        if "script" in fields:
            doc.replace_value(fields["script"][1], "Script", ATTACK_SCRIPT)
            switched += 1
        for key, wanted in (("Aggressive", "yes"), ("IsBaseDefense", "no")):
            if key.lower() in fields:
                doc.replace_value(fields[key.lower()][1], key, wanted)
            else:
                doc.insert_value(tid, key, wanted)

    # Attack triggers: high weight, floor at 150, enabled on every difficulty.
    boosted = 0
    start, end = doc.bounds("AITriggerTypes")
    for i in range(start, end):
        line = doc.lines[i]
        if "=" not in line or line.lstrip().startswith(";"):
            continue
        key, value = line.split("=", 1)
        tokens = value.rstrip("\r\n").split(",")
        if len(tokens) != 18 or tokens[1].strip() not in attack:
            continue
        eol = line[len(line.rstrip("\r\n")):]
        tokens[7], tokens[8], tokens[9] = "250.000000", "150.000000", "250.000000"
        tokens[15], tokens[16], tokens[17] = "1", "1", "1"
        doc.lines[i] = key + "=" + ",".join(tokens) + eol
        boosted += 1

    # Base recovery.  The stock "this house owns zero Construction Yards"
    # triggers (condition 1 with GACNST/NACNST/YACNST) rebuild an MCV, but
    # retail enables them on hard only (`0,0,1`) and weights them 70/60/70,
    # while our 67 attack triggers now sit at 250 -- so a crippled computer
    # would keep drawing attack teams it cannot fill instead of restarting.
    # Put them on every difficulty at the same 250 the attack triggers use.
    #
    # Do NOT raise them to 5000.  In `ai_team_creation.rs` PRIORITY_WEIGHT is
    # 5000 and it is a *takeover* marker, not a boost: the first eligible
    # 5000-weight trigger clears every other trigger out of the draw, so one
    # unfillable MCV team would stop that house from ever creating another
    # team until DissolveUnfilledTeamDelay expired -- forever, since the team
    # cannot be filled while the depot is missing.
    recovered = 0
    start, end = doc.bounds("AITriggerTypes")
    for i in range(start, end):
        line = doc.lines[i]
        if "=" not in line or line.lstrip().startswith(";"):
            continue
        key, value = line.split("=", 1)
        tokens = value.rstrip("\r\n").split(",")
        if len(tokens) != 18 or "MCV" not in tokens[0].upper():
            continue
        eol = line[len(line.rstrip("\r\n")):]
        tokens[7], tokens[8], tokens[9] = "250.000000", "250.000000", "250.000000"
        tokens[15], tokens[16], tokens[17] = "1", "1", "1"
        doc.lines[i] = key + "=" + ",".join(tokens) + eol
        recovered += 1

    # Guard: PRIORITY_WEIGHT (5000) means "this trigger wins outright" -- the
    # first eligible 5000-weight trigger clears every other trigger out of the
    # draw (`ai_team_creation.rs`).  Retail uses it on purpose for
    # superweapon/spy-guard triggers, whose condition passes only in a narrow
    # situation.  It is a bug on a team that cannot be filled: the house would
    # then create nothing at all until DissolveUnfilledTeamDelay expired, and
    # an MCV team is exactly that while the depot is missing.  So the guard is
    # aimed at the recovery triggers only.
    start, end = doc.bounds("AITriggerTypes")
    for i in range(start, end):
        line = doc.lines[i]
        if "=" not in line or line.lstrip().startswith(";"):
            continue
        tokens = line.split("=", 1)[1].rstrip("\r\n").split(",")
        if len(tokens) != 18 or "MCV" not in tokens[0].upper():
            continue
        if any(float(tokens[n] or 0) >= 5000 for n in (7, 8, 9)):
            raise SystemExit(
                "MCV recovery trigger %s carries the 5000 priority weight; an "
                "unfillable team at that weight starves every other trigger"
                % line.split("=", 1)[0])

    open(os.path.join(out_dir, "aimd.ini"), "wb").write(doc.text().encode("latin-1"))
    return len(attack), switched, scaled, boosted, recovered, len(shared)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", required=True,
                        help="folder containing retail rulesmd.ini / artmd.ini / aimd.ini")
    parser.add_argument("--out", required=True, help="output mod folder")
    parser.add_argument("--no-art", action="store_true",
                        help="do not copy artmd.ini (the mod does not change it)")
    args = parser.parse_args()

    for name in ("rulesmd.ini", "aimd.ini"):
        if not os.path.isfile(os.path.join(args.rules_dir, name)):
            raise SystemExit("missing %s in %s" % (name, args.rules_dir))

    os.makedirs(args.out, exist_ok=True)
    buildings = build_rules(args.rules_dir, args.out)
    teams, switched, scaled, boosted, recovered, shared = build_aimd(args.rules_dir, args.out)
    if not args.no_art:
        source = os.path.join(args.rules_dir, "artmd.ini")
        if not os.path.isfile(source):
            raise SystemExit("missing artmd.ini in %s" % args.rules_dir)
        shutil.copyfile(source, os.path.join(args.out, "artmd.ini"))

    print("rules: AIBuildCounts on %d building types" % buildings)
    print("aimd : %d attack teams, %d charged, %d task forces rescaled, "
          "%d triggers boosted, %d MCV triggers re-armed "
          "(%d shared task forces skipped)"
          % (teams, switched, scaled, boosted, recovered, shared))
    print("output:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
