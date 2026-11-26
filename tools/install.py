# -*- coding: utf-8 -*-
"""Install a mod and its maps into a VERA20k folder.

    python tools/install.py --game-dir "<游戏目录>" --mod MassSkirmish

``--enable`` rewrites the ``mod =`` line in ``config.toml`` (a .bak copy is
written first).  Without it the files are installed but you pick the mod in
Options -> Mods yourself.  The default is ``MassSkirmish``; pass
``--mod SuperAI`` for the older tuning mod.
"""
from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def copy_file(source, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.isfile(target) and filecmp.cmp(source, target, shallow=False):
        return False
    shutil.copy2(source, target)
    return True


def copy_folder(source, target):
    changed = 0
    for name in sorted(os.listdir(source)):
        path = os.path.join(source, name)
        if os.path.isfile(path):
            changed += copy_file(path, os.path.join(target, name))
    return changed


def enable_mod(game_dir, mod_name):
    config = os.path.join(game_dir, "config.toml")
    if not os.path.isfile(config):
        print("! config.toml not found; enable the mod in Options -> Mods")
        return False
    text = open(config, "r", encoding="utf-8").read()
    wanted = 'mod = "%s"' % mod_name
    if wanted in text:
        print("config: %s already set" % wanted)
        return False

    backup = config + ".bak"
    shutil.copyfile(config, backup)

    lines = text.splitlines(keepends=True)
    replaced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("mod ="):
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            lines[i] = wanted + eol
            replaced = True
            break
    if not replaced:
        for i, line in enumerate(lines):
            if line.strip() == "[paths]":
                eol = "\r\n" if line.endswith("\r\n") else "\n"
                lines.insert(i + 1, wanted + eol)
                replaced = True
                break
    if not replaced:
        print("! no [paths] section in config.toml; enable the mod manually")
        return False

    open(config, "w", encoding="utf-8", newline="").write("".join(lines))
    print("config: %s (backup: config.toml.bak)" % wanted)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", required=True, help="VERA20k folder (contains vera20k.exe)")
    parser.add_argument("--mod", default="MassSkirmish",
                        help="mod folder name (default: MassSkirmish)")
    parser.add_argument("--enable", action="store_true",
                        help="set mod = \"<mod>\" in config.toml")
    parser.add_argument("--no-maps", action="store_true", help="install the mod only")
    parser.add_argument("--force", action="store_true", help="continue without vera20k.exe")
    args = parser.parse_args()

    game_dir = os.path.abspath(args.game_dir)
    if not os.path.isfile(os.path.join(game_dir, "vera20k.exe")) and not args.force:
        raise SystemExit("vera20k.exe not found in %s (use --force to override)" % game_dir)

    mod_source = os.path.join(ROOT, "mod", args.mod)
    mod_target = os.path.join(game_dir, "Mods", args.mod)
    if not os.path.isdir(mod_source):
        raise SystemExit("mod folder not found: %s" % mod_source)
    changed = copy_folder(mod_source, mod_target)
    print("mod  : %s (%d file(s) updated)" % (mod_target, changed))

    if not args.no_maps:
        maps_source = os.path.join(ROOT, "maps")
        maps_target = os.path.join(game_dir, "Maps")
        changed = 0
        for name in sorted(os.listdir(maps_source)):
            if name.lower().endswith((".yrm", ".mmx", ".map", ".mpr")):
                changed += copy_file(os.path.join(maps_source, name),
                                     os.path.join(maps_target, name))
        print("maps : %s (%d file(s) updated)" % (maps_target, changed))

    if args.enable:
        enable_mod(game_dir, args.mod)

    print("done. Restart VERA20k; the mod is listed under Options -> Mods.")


if __name__ == "__main__":
    sys.exit(main())
