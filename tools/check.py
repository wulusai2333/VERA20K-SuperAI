# -*- coding: utf-8 -*-
"""Validate the mod and every map with VERA20k's headless probe.

    python tools/check.py --game-dir "F:/Games/VERA20K"

The probe loads the rules, the AI INI and the map, then prints JSON.  This
script turns that into a pass/fail table, so a broken edit is caught before
starting a match.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ra2_dir(game_dir):
    config = os.path.join(game_dir, "config.toml")
    with open(config, "rb") as handle:
        data = tomllib.load(handle)
    return data["paths"]["ra2_dir"]


def probe(game_dir, args):
    result = subprocess.run(
        [os.path.join(game_dir, "vera20k.exe"), "--probe"] + args,
        cwd=game_dir, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", required=True)
    parser.add_argument("--maps", default=os.path.join(ROOT, "maps"))
    args = parser.parse_args()

    game_dir = os.path.abspath(args.game_dir)
    data_dir = ra2_dir(game_dir)

    print("rules / AI")
    report = probe(game_dir, ["--ra2-dir", data_dir, "--mod", "SuperAI"])
    settings = report["rules_parts"]["settings"]
    mod = settings.get("mod")
    if isinstance(mod, dict):
        mod = "%s v%s" % (mod.get("title", "?"), mod.get("version", "?"))
    print("  mod=%s ares=%s check=%s"
          % (mod, settings.get("ares"), report["rules_parts"].get("mod_check")))
    for entry in report["rules_parts"]["files"]:
        if entry["id"] in ("rules", "art", "ai"):
            print("  %-5s %-10s changed=%s" % (entry["id"], entry["source"], entry["changed"]))

    failures = 0
    print("maps")
    for path in sorted(glob.glob(os.path.join(args.maps, "*.yrm"))):
        try:
            report = probe(game_dir, ["--ra2-dir", data_dir, "--mod", "SuperAI",
                                      "--map", os.path.abspath(path)])
            info = report["map"]
            print("  OK   %-34s %8d bytes  starts=%s"
                  % (os.path.basename(path), info["byte_length"],
                     report.get("max_start_waypoints")))
        except Exception as exc:  # noqa: BLE001 - report and keep checking
            failures += 1
            print("  FAIL %-34s %s" % (os.path.basename(path), exc))

    if failures:
        print("%d map(s) failed" % failures)
        return 1
    print("all maps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
