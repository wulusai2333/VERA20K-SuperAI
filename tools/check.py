# -*- coding: utf-8 -*-
"""Validate the mod and every map with VERA20k's headless probe.

    python tools/check.py --game-dir "<游戏目录>"

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
    # The probe prints UTF-8 JSON, and a mod's About/Name may hold non-ASCII
    # text (this mod's title is "超级AI").  ``text=True`` alone decodes with the
    # console code page (cp936/GBK on a Chinese Windows) and raises
    # UnicodeDecodeError on that JSON, so name the encoding explicitly.
    result = subprocess.run(
        [os.path.join(game_dir, "vera20k.exe"), "--probe"] + args,
        cwd=game_dir, capture_output=True, encoding="utf-8",
        errors="replace", timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def main():
    # A Chinese Windows console defaults to cp936 and raises UnicodeEncodeError
    # on the mod's own title; write UTF-8 and let an unrenderable glyph become
    # "?" instead of killing the report.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
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

    # Sidebar names the mod adds: `UIName=` is a CSF label, so the text lives in
    # the mod's own `ares.csf`.  A label the table does not hold is drawn
    # literally as `MISSING:'NAME:X'` in game, and a half-copied install is
    # exactly how that happens -- so compare the installed file with the one in
    # this repository, not just its presence.
    print("sidebar names")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import csf
    except ImportError as exc:  # tools/ not importable: skip, do not fail
        print("  SKIP ares.csf (%s)" % exc)
    else:
        installed = os.path.join(game_dir, "Mods", "SuperAI", "ares.csf")
        source = os.path.join(ROOT, "mod", "SuperAI", "ares.csf")
        try:
            labels = csf.read(installed)
        except (OSError, ValueError) as exc:
            failures += 1
            print("  FAIL %s (%s)" % (installed, exc))
        else:
            print("  csf  %-10s %d label(s): %s"
                  % (os.path.basename(installed), len(labels),
                     ", ".join("%s=%s" % pair for pair in sorted(labels.items()))))
            try:
                expected = csf.read(source)
            except (OSError, ValueError) as exc:
                failures += 1
                print("  FAIL repository copy %s (%s)" % (source, exc))
            else:
                if expected != labels:
                    failures += 1
                    print("  FAIL installed ares.csf differs from %s" % source)

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
        print("%d check(s) failed" % failures)
        return 1
    print("all maps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
