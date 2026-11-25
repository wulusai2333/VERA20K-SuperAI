"""Guard the "additive-only" rule against the RETAIL rules, not against our last build.

The rule: unless a specific retail unit or behaviour is named as the target, the mod
only *adds* things -- new sections, new rows at the end of a registry, new keys on a
retail section.  What is protected is the retail data itself
(the official ``rulesmd.ini``), never our own previous version: our ``ZAI*``
sections and our registry rows are ours to rename or delete.

So the comparison is retail-vs-built, and every deviation has to be listed in the
two allowlists below (which are the machine-readable copy of the registry in
``docs/boundaries-and-lessons.md``).  Anything else fails the build.
"""

from __future__ import annotations

import argparse
import re
import sys

#: Retail sections whose *existing* keys we are allowed to change the value of.
RETAIL_VALUE_EDITS = {
    # AI tuning (the point of this mod).
    "General": {
        "aiextrarefineries", "aipickwalldefensepercent", "airestrictreplacetime",
        "aisafedistance", "aislaveminernumber", "buildspeed",
        "dissolveunfilledteamdelay", "maximumaidefensiveteams",
        "minimumaidefensiveteams", "multiplayeraicm",
        "targetdistancecoefficientdefault", "teamdelays", "totalaiteamcap",
        "usemindefenserule",
    },
    "AI": {"airstriplimit", "airstripratio", "computerbasedefenseresponse", "paranoid"},
    "GADEPT": {"aibuildthis"},
    "NADEPT": {"aibuildthis"},
    "YADEPT": {"aibuildthis"},
}

#: Retail sections where we may *add* keys without touching any existing value.
RETAIL_KEY_ADDITIONS = {
    "General": {"ainearestenemy"},
    "GACNST": {"spysat"}, "NACNST": {"spysat"}, "YACNST": {"spysat"},
    "GAPILE": {"aibuildcounts"}, "GAWEAP": {"aibuildcounts"},
    "NAHAND": {"aibuildcounts"}, "NAWEAP": {"aibuildcounts"},
    "YABRCK": {"aibuildcounts"}, "YAWEAP": {"aibuildcounts"},
    "GAREFN": {"producecashamount", "producecashdelay"},
    "NAREFN": {"producecashamount", "producecashdelay"},
    "YAREFN": {"producecashamount", "producecashdelay"},
    # Retail superweapons: AI auto-fire keys (no retail key is changed).
    "NukeSpecial": {"sw.aitargeting", "sw.allowai", "sw.allowplayer", "sw.autofire",
                    "sw.requirestarget", "sw.useaitargeting"},
    "IronCurtainSpecial": {"sw.affectshouse", "sw.affectstarget", "sw.airequirestarget",
                           "sw.aitargeting", "sw.aitargeting.constraints",
                           "sw.aitargeting.preference", "sw.allowai", "sw.allowplayer",
                           "sw.autofire", "sw.requirestarget", "sw.useaitargeting"},
    "LightningStormSpecial": {"sw.aitargeting", "sw.allowai", "sw.allowplayer",
                              "sw.autofire", "sw.requirestarget", "sw.useaitargeting"},
    "ChronoSphereSpecial": {"sw.affectshouse", "sw.affectstarget", "sw.airequirestarget",
                            "sw.aitargeting", "sw.aitargeting.constraints",
                            "sw.aitargeting.preference", "sw.allowai", "sw.allowplayer",
                            "sw.autofire", "sw.requirestarget", "sw.useaitargeting"},
    "PsychicDominatorSpecial": {"sw.aitargeting", "sw.allowai", "sw.allowplayer",
                                "sw.autofire", "sw.requirestarget", "sw.useaitargeting"},
    "GeneticConverterSpecial": {"sw.aitargeting", "sw.allowai", "sw.allowplayer",
                                "sw.autofire", "sw.requirestarget", "sw.useaitargeting"},
}

#: Registries where new rows may only be appended (numeric keys above retail's max).
REGISTRY_SECTIONS = ("VehicleTypes", "InfantryTypes", "AircraftTypes", "BuildingTypes",
                     "SuperWeaponTypes", "WeaponTypes", "WarheadTypes")


def parse_ini(path: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = None
    with open(path, "rb") as handle:
        for raw in handle.read().decode("latin-1").splitlines():
            line = raw.strip()
            header = re.match(r"^\[([^\]]+)\]", line)
            if header:
                current = header.group(1).strip()
                sections.setdefault(current, {})
                continue
            if current and line and not line.startswith(";") and "=" in line:
                key, value = line.split("=", 1)
                sections[current][key.strip().lower()] = value.split(";")[0].strip()
    return sections


def diff_retail(retail: dict[str, dict[str, str]],
                built: dict[str, dict[str, str]]) -> dict[str, list]:
    """Classify every difference into allowed / violation buckets."""
    new_sections = sorted(name for name in built if name not in retail)
    value_changes, key_additions, key_removals = [], [], []
    for name, keys in retail.items():
        if name not in built:
            key_removals.append((name, "<whole section>"))
            continue
        for key, value in keys.items():
            if key not in built[name]:
                key_removals.append((name, key))
            elif built[name][key] != value:
                value_changes.append((name, key))
        for key in built[name]:
            if key not in keys:
                key_additions.append((name, key))
    return {
        "new_sections": new_sections,
        "value_changes": value_changes,
        "key_additions": key_additions,
        "key_removals": key_removals,
    }


def check(retail: dict[str, dict[str, str]], built: dict[str, dict[str, str]]) -> list[str]:
    """Return the list of violations (empty means the build is compliant)."""
    result = diff_retail(retail, built)
    problems = []

    for name, key in result["value_changes"]:
        if key not in RETAIL_VALUE_EDITS.get(name, set()):
            problems.append("%s: retail key %r was changed and is not in the "
                            "allowlist" % (name, key))
    for name, key in result["key_additions"]:
        if key in RETAIL_KEY_ADDITIONS.get(name, set()):
            continue
        if name in REGISTRY_SECTIONS and key.isdigit():
            highest = max((int(k) for k in retail.get(name, {}) if k.isdigit()), default=0)
            if int(key) > highest:
                continue
        problems.append("%s: key %r was added to a retail section and is not in the "
                        "allowlist" % (name, key))
    for name, key in result["key_removals"]:
        problems.append("%s: retail key %r was removed" % (name, key))
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retail-dir", help="folder with the official rulesmd.ini")
    parser.add_argument("--mod-dir", help="folder with the built rulesmd.ini")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        retail = {"General": {"buildspeed": "1", "teamdelays": "3"},
                  "VehicleTypes": {"1": "MTNK"},
                  "ZEP": {"strength": "2000"}}
        ok = {"General": {"buildspeed": "0.5", "teamdelays": "3", "ainearestenemy": "yes"},
              "VehicleTypes": {"1": "MTNK", "85": "ZAINukeGunship"},
              "ZEP": {"strength": "2000"},
              "ZAINukeGunship": {"strength": "100000"}}
        assert not check(retail, ok), check(retail, ok)
        bad = dict(ok)
        bad["ZEP"] = {"strength": "9999"}
        assert check(retail, bad), "a changed retail value must be rejected"
        bad2 = dict(ok)
        bad2["General"] = dict(ok["General"], maxspeed="12")
        assert check(retail, bad2), "an unregistered added key must be rejected"
        bad3 = dict(ok)
        bad3["VehicleTypes"] = {"1": "MTNK"}  # lost a retail row
        print("selftest OK")
        return 0

    if not (args.retail_dir and args.mod_dir):
        parser.error("--retail-dir and --mod-dir are required (or use --selftest)")

    import os
    retail = parse_ini(os.path.join(args.retail_dir, "rulesmd.ini"))
    built = parse_ini(os.path.join(args.mod_dir, "rulesmd.ini"))
    problems = check(retail, built)
    result = diff_retail(retail, built)
    if problems:
        for line in problems[:12]:
            print("RETAIL VIOLATION: %s" % line)
        print("%d violation(s); add them to tools/check_retail.py only after the "
              "change was explicitly requested and registered" % len(problems))
        return 1
    if not args.quiet:
        print("retail diff OK: %d allowed value edits, %d allowed key additions, "
              "%d new sections, 0 removals"
              % (len(result["value_changes"]), len(result["key_additions"]),
                 len(result["new_sections"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
