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
    "AlliedBaseDefenseCounts": ("25,20,6", "100,100,100"),
    "SovietBaseDefenseCounts": ("25,22,6", "100,100,100"),
    "ThirdBaseDefenseCounts": ("25,22,6", "100,100,100"),
    "Paranoid": ("yes", "no"),
    "TotalAITeamCap": ("30,30,30", "10,10,10"),
    "MaximumAIDefensiveTeams": ("2,2,2", "0,0,0"),
    "MinimumAIDefensiveTeams": ("1,1,1", "0,0,0"),
    "UseMinDefenseRule": ("yes", "no"),
    "AIHateDelays": ("30,50,70", "8,12,18"),
    "AIBaseSpacing": ("1", "1"),
    "AIRestrictReplaceTime": ("400", "120"),
    "AITriggerSuccessWeightDelta": ("20", "50"),
    "AITriggerFailureWeightDelta": ("-50", "0"),
    "DissolveUnfilledTeamDelay": ("5000", "900"),
}

#: Ares AIBuildCounts per building type (planned copies per computer base).
BUILD_COUNTS = {
    "GAPOWR": 60, "NAPOWR": 60, "YAPOWR": 60,
    "GAREFN": 60, "NAREFN": 60, "YAREFN": 60,
    "GAPILE": 60, "NAHAND": 60, "YABRCK": 60,
    "GAWEAP": 60, "NAWEAP": 60, "YAWEAP": 60,
    "GATECH": 40, "NATECH": 40, "YATECH": 40,
    "GAAIRC": 20, "NARADR": 40, "AMRADR": 40, "NAPSIS": 20,
    "GADEPT": 30, "NADEPT": 30,
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


def build_rules(source_dir, out_dir):
    text = open(os.path.join(source_dir, "rulesmd.ini"), "rb").read().decode("latin-1")
    lines = text.splitlines(keepends=True)

    apply_rules_edits(lines)

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

    open(os.path.join(out_dir, "aimd.ini"), "wb").write(doc.text().encode("latin-1"))
    return len(attack), switched, scaled, boosted, len(shared)


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
    teams, switched, scaled, boosted, shared = build_aimd(args.rules_dir, args.out)
    if not args.no_art:
        source = os.path.join(args.rules_dir, "artmd.ini")
        if not os.path.isfile(source):
            raise SystemExit("missing artmd.ini in %s" % args.rules_dir)
        shutil.copyfile(source, os.path.join(args.out, "artmd.ini"))

    print("rules: AIBuildCounts on %d building types" % buildings)
    print("aimd : %d attack teams, %d charged, %d task forces rescaled, "
          "%d triggers boosted (%d shared task forces skipped)"
          % (teams, switched, scaled, boosted, shared))
    print("output:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
