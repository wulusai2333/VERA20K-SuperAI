# -*- coding: utf-8 -*-
r"""Build the MassSkirmish mod from stock Yuri's Revenge rules.

    python tools/build_mass_skirmish.py `
        --rules-dir F:\Games\red2 --out mod/MassSkirmish --profile stage1

The prototype starts from the retail rulesmd/aimd/artmd/mpmodesmd files and
applies a small, explicit AI package.  It never reads ``mod/SuperAI``.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil

import mass_skirmish_aimd as ai

HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*(?:;.*)?$")

SW_MODE = {
    "NAMISL": ("nuke", None, None),
    "GAWEAT": ("lightningstorm", None, None),
    "YAPPET": ("psychicdominator", None, None),
    "YAGNTC": ("geneticmutator", None, None),
    "GACSPH": ("offensive", "offensive_cell_set", "offensive"),
    "NAIRON": ("ironcurtain", "defensive_cell_set", "defensive"),
}
SW_SECTIONS = tuple(SW_MODE)
REPAIR_DEPOTS = ("GADEPT", "NADEPT", "YADEPT")
REFINERIES = ("GAREFN", "NAREFN", "YAREFN")
YARDS = ("GACNST", "NACNST", "YACNST")
MCVS = ("AMCV", "SMCV", "PCV")
BUILD_COUNTS = {
    "GAPILE": 2, "NAHAND": 2, "YABRCK": 2,
    "GAWEAP": 3, "NAWEAP": 3, "YAWEAP": 3,
    "GAAIRC": 2, "AMRADR": 2,
}


class Rules:
    def __init__(self, text: str):
        self.lines = text.splitlines(keepends=True)
        self.reindex()

    def reindex(self) -> None:
        self.starts = {}
        for i, line in enumerate(self.lines):
            m = HEADER_RE.match(line)
            if m:
                self.starts[m.group(1).strip()] = i

    def bounds(self, name: str) -> tuple[int, int]:
        if name not in self.starts:
            raise KeyError("section [%s] not found" % name)
        start = self.starts[name]
        end = len(self.lines)
        for index in self.starts.values():
            if start < index < end:
                end = index
        return start + 1, end

    def get(self, name: str, key: str) -> str | None:
        s, e = self.bounds(name)
        for i in range(s, e):
            if re.match(r"^\s*%s\s*=" % re.escape(key), self.lines[i], re.I):
                return self.lines[i].split("=", 1)[1].strip()
        return None

    def set(self, name: str, key: str, value: str) -> None:
        s, e = self.bounds(name)
        for i in range(s, e):
            if re.match(r"^\s*%s\s*=" % re.escape(key), self.lines[i], re.I):
                self.lines[i] = "%s=%s\r\n" % (key, value)
                return
        self.lines.insert(s, "%s=%s\r\n" % (key, value))
        self.reindex()

    def delete(self, name: str, key: str) -> bool:
        """Remove every ``key=`` line in a section; return True if any moved."""
        s, e = self.bounds(name)
        removed = False
        for i in range(e - 1, s - 1, -1):
            if re.match(r"^\s*%s\s*=" % re.escape(key), self.lines[i], re.I):
                del self.lines[i]
                removed = True
        if removed:
            self.reindex()
        return removed

    def insert_after_key(self, name: str, key: str, new_key: str, value: str) -> None:
        s, e = self.bounds(name)
        for i in range(s, e):
            if re.match(r"^\s*%s\s*=" % re.escape(key), self.lines[i], re.I):
                self.lines.insert(i + 1, "%s=%s\r\n" % (new_key, value))
                self.reindex()
                return
        self.set(name, new_key, value)

    def registry(self, name: str) -> list[str]:
        out = []
        for line in self.lines[self.bounds(name)[0]:self.bounds(name)[1]]:
            m = re.match(r"^\d+\s*=\s*([^\s;]+)", line)
            if m:
                out.append(m.group(1).strip())
        return out

    def text(self) -> str:
        return "".join(self.lines)


def edit_rules(retail_text: str, profile: str, base_target: int, sw_copies: int) -> tuple[str, dict]:
    r = Rules(retail_text)
    general = "General"

    r.set(general, "BuildSpeed", ".025")
    r.set(general, "MultiplayerAICM", "100000,100000,100000")
    r.set(general, "TeamDelays", "180,270,360")
    r.set(general, "TotalAITeamCap", "12,12,12")
    r.set(general, "DissolveUnfilledTeamDelay", "2400")
    r.set(general, "UseMinDefenseRule", "no")
    r.set(general, "MinimumAIDefensiveTeams", "0,0,0")
    r.set(general, "MaximumAIDefensiveTeams", "0,0,0")
    r.set(general, "AIPickWallDefensePercent", "0,0,0")
    r.set(general, "AIRestrictReplaceTime", "15")
    r.set(general, "MaximumBuildingPlacementFailures", "3")
    r.set(general, "AISafeDistance", "12")
    r.insert_after_key(general, "AISafeDistance", "AIFriendlyDistance", "20")
    r.insert_after_key(general, "AISafeDistance", "AINearestEnemy", "yes")
    r.set(general, "TargetDistanceCoefficientDefault", "-0.4")
    r.set(general, "AlliedBaseDefenseCounts", "10,10,10")
    r.set(general, "SovietBaseDefenseCounts", "10,10,10")
    r.set(general, "ThirdBaseDefenseCounts", "10,10,10")
    r.set(general, "AIVirtualPurifiers", "4,2,0")
    r.set(general, "AIExtraRefineries", "0,0,0")
    r.set(general, "AISlaveMinerNumber", "2,2,2")

    # AIBaseSpacing lives in [AI], not [General]; keep retail 1 and assert.
    ai_base_spacing = r.get("AI", "AIBaseSpacing")
    if ai_base_spacing is None:
        r.set("AI", "AIBaseSpacing", "1")
    elif ai_base_spacing != "1":
        r.set("AI", "AIBaseSpacing", "1")

    for yard in YARDS:
        # BuildLimit only constrained the human sidebar; VERA20k's AI factory
        # ignores it.  Remove it instead of pretending it is an AI cap.
        r.delete(yard, "BuildLimit")
        # Keep yards in the AI base-plan seed.  AIBuildThis=no removes the
        # BuildConst seed entirely and leaves build_const_order empty, which
        # makes the AI build only power/defences.  Direct-yard spam must be
        # fixed in the engine, not by this flag.
        r.set(yard, "AIBuildThis", "yes")
        r.set(yard, "SpySat", "yes")
    for mcv in MCVS:
        r.delete(mcv, "BuildLimit")
    for depot in REPAIR_DEPOTS:
        r.set(depot, "AIBuildThis", "yes")
    for refn in REFINERIES:
        r.set(refn, "ProduceCashAmount", "100")
        r.set(refn, "ProduceCashDelay", "60")

    for name, count in BUILD_COUNTS.items():
        r.set(name, "AIBuildCounts", "%d,%d,%d" % (count, count, count))

    for name in SW_SECTIONS:
        mode, constraints, preference = SW_MODE[name]
        # Retail has BuildLimit=1 on superweapons; delete it too so the human
        # player is not capped by a key the AI factory never reads.
        r.delete(name, "BuildLimit")
        r.set(name, "AIBuildThis", "yes")
        r.set(name, "SW.AllowAI", "yes")
        r.set(name, "SW.AutoFire", "yes")
        r.set(name, "SW.UseAITargeting", "yes")
        r.set(name, "SW.AITargeting", mode)
        r.set(name, "AIBuildCounts", "%d,%d,%d" % (sw_copies, sw_copies, sw_copies))
        if constraints:
            r.set(name, "SW.AITargeting.Constraints", constraints)
        if preference:
            r.set(name, "SW.AITargeting.Preference", preference)
        if name == "NAIRON":
            r.set(name, "SW.AIRequiresHouse", "owner")
            r.set(name, "SW.AIRequiresTarget", "units")
            r.set(name, "SW.AffectsHouse", "owner")
        if name == "GACSPH":
            r.set(name, "SW.AIRequiresTarget", "units")

    # Assert the rules package, then compute the dense BuildingTypes index
    # used by action 46.  Retail has a duplicate NAPSYA, so YACNST is 300,
    # not the raw list position 301.
    building_ids = r.registry("BuildingTypes")
    seen = set()
    dense = []
    for item in building_ids:
        key = item.upper()
        if key in seen:
            continue
        seen.add(key)
        dense.append(key)
    for name, expected in (("GACNST", 2), ("NACNST", 25), ("YACNST", 300)):
        actual = dense.index(name) if name in dense else None
        if actual != expected:
            raise SystemExit("[BuildingTypes] dense index %s=%r, expected %d" % (name, actual, expected))

    for yard in YARDS + MCVS:
        if r.get(yard, "BuildLimit") is not None:
            raise SystemExit("%s still has BuildLimit (AI ignores it; remove for players too)" % yard)
    for yard in YARDS:
        if r.get(yard, "AIBuildThis") != "yes":
            raise SystemExit("%s AIBuildThis != yes (base plan needs the yard seed)" % yard)
    for name in SW_SECTIONS:
        if r.get(name, "BuildLimit") is not None:
            raise SystemExit("%s still has BuildLimit (AI ignores it; remove for players too)" % name)
        if r.get(name, "AIBuildThis") != "yes":
            raise SystemExit("%s AIBuildThis != yes" % name)
        if r.get(name, "AIBuildCounts") != "%d,%d,%d" % (sw_copies, sw_copies, sw_copies):
            raise SystemExit("%s AIBuildCounts mismatch" % name)
    for depot in REPAIR_DEPOTS:
        if r.get(depot, "AIBuildThis") != "yes":
            raise SystemExit("%s AIBuildThis != yes" % depot)
    if r.get(general, "AIPickWallDefensePercent") != "0,0,0":
        raise SystemExit("AIPickWallDefensePercent")
    if r.get(general, "UseMinDefenseRule") != "no":
        raise SystemExit("UseMinDefenseRule")
    if r.get(general, "MinimumAIDefensiveTeams") != "0,0,0":
        raise SystemExit("MinimumAIDefensiveTeams")

    stats = {
        "profile": profile,
        "base_target": base_target,
        "sw_copies": sw_copies,
        "build_limit_removed": list(YARDS + MCVS + SW_SECTIONS),
        "yards_ai_build_this": "yes",
        "air_restrict_replace_time": 15,
        "buildingtypes_dense": {"GACNST": 2, "NACNST": 25, "YACNST": 300},
        "aibuildcounts": BUILD_COUNTS,
    }
    return r.text(), stats


MOD_INI = """[Mod]
Name=Mass Skirmish AI
Version=0.1.0
Author=VERA20K-SuperAI contributors
About=Stage 1 prototype: official YR rules, 120-AI mass skirmish AI. BuildLimit was removed from construction yards, MCVs and superweapons because VERA20k's AI factory ignores it; it only constrained the human sidebar. The current throttle is AIRestrictReplaceTime=15 (1 second of lost-node replan delay, measured in-game to reduce overbuilding). AIBuildCounts remains a planning target (3 per superweapon type in Stage 1), not a hard cap. Construction yards stay AIBuildThis=yes: setting it to no empties the AI base-plan seed and makes the AI build only power/defences. Attacks leave immediately and decapitate construction yards first.
Terms=Tools and docs MIT; rules/maps are fan-derived, non-commercial use only.

[Files]
Rules=rulesmd.ini
Art=artmd.ini
AI=aimd.ini
Modes=mpmodesmd.ini

[Extensions]
Ares=yes
"""


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", default=r"F:\Games\red2")
    parser.add_argument("--out", default=os.path.join("mod", "MassSkirmish"))
    parser.add_argument("--profile", choices=("stage1", "max"), default="stage1")
    parser.add_argument("--base-target", type=int, default=None)
    parser.add_argument("--sw-copies", type=int, default=None)
    args = parser.parse_args()

    base_target = args.base_target or (4 if args.profile == "stage1" else 20)
    sw_copies = args.sw_copies or (3 if args.profile == "stage1" else 20)
    if base_target < 1 or base_target > 20:
        raise SystemExit("--base-target must be 1..20")
    if sw_copies < 1 or sw_copies > 20:
        raise SystemExit("--sw-copies must be 1..20 (20 per type; 2 types = ceiling 40 per faction)")

    for name in ("rulesmd.ini", "aimd.ini", "artmd.ini", "mpmodesmd.ini"):
        if not os.path.isfile(os.path.join(args.rules_dir, name)):
            raise SystemExit("missing %s in %s" % (name, args.rules_dir))

    os.makedirs(args.out, exist_ok=True)
    retail_rules = open(os.path.join(args.rules_dir, "rulesmd.ini"), "rb").read().decode("latin-1")
    retail_aimd = open(os.path.join(args.rules_dir, "aimd.ini"), "rb").read().decode("latin-1")
    rules_text, rules_stats = edit_rules(retail_rules, args.profile, base_target, sw_copies)

    rules_lines = rules_text.splitlines(keepends=True)
    air = ai.classify_units(rules_lines)
    ai.set_rules_air(air)
    # One house builds one airfield type (`GAAIRC` or `AMRADR`), 4 pads each;
    # the mass-skirmish air teams must stay inside that capacity.
    ai.set_air_pads(4 * max(BUILD_COUNTS["GAAIRC"], BUILD_COUNTS["AMRADR"]))
    aimd_text, aimd_stats, log = ai.build_aimd(retail_aimd, base_target)

    out = args.out
    with open(os.path.join(out, "rulesmd.ini"), "wb") as handle:
        handle.write(rules_text.encode("latin-1"))
    with open(os.path.join(out, "aimd.ini"), "wb") as handle:
        handle.write(aimd_text.encode("latin-1"))
    shutil.copyfile(os.path.join(args.rules_dir, "artmd.ini"), os.path.join(out, "artmd.ini"))
    shutil.copyfile(os.path.join(args.rules_dir, "mpmodesmd.ini"), os.path.join(out, "mpmodesmd.ini"))
    with open(os.path.join(out, "mod.ini"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(MOD_INI)

    report = []
    report.append("MassSkirmish build report")
    report.append("profile=%s base_target=%d sw_copies=%d" % (args.profile, base_target, sw_copies))
    report.append("rules_dir=%s" % args.rules_dir)
    report.append("")
    for key, value in rules_stats.items():
        report.append("%s=%r" % (key, value))
    report.append("")
    for key, value in aimd_stats.items():
        report.append("%s=%r" % (key, value))
    report.append("")
    report.append("log:")
    report.extend("  " + line for line in log)
    report.append("")
    for name in ("mod.ini", "rulesmd.ini", "aimd.ini", "artmd.ini", "mpmodesmd.ini"):
        path = os.path.join(out, name)
        report.append("%s bytes=%d sha256=%s" % (name, os.path.getsize(path), sha256(path)))
    with open(os.path.join(out, "build-report.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(report) + "\n")

    print("MassSkirmish: %s" % out)
    print("  profile=%s base_target=%d sw_copies=%d" % (args.profile, base_target, sw_copies))
    print("  TF=%d Team=%d Script=%d Trigger=%d" % (
        aimd_stats["taskforces"], aimd_stats["teamtypes"],
        aimd_stats["scripttypes"], aimd_stats["aitriggers"]))
    print("  mixed=%r mcv=%d sw=%d" % (
        aimd_stats["mixed_taskforces"], aimd_stats["mcv_teams"],
        aimd_stats["superweapon_teams"]))
    print("  report=%s" % os.path.join(out, "build-report.txt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
