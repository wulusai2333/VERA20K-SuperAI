# -*- coding: utf-8 -*-
"""Build the SuperAI map pack.

Subcommands
-----------
``ice``     sample 1v7 map -> spectator edition, plus a no-ore variant
``flat``    a generated random map -> uniform flat stage with spectator triggers
``uniform`` rewrite every terrain cell to one tile / one height
``info``    print what a map contains (sizes, waypoints, terrain, triggers)

Examples
--------
    python tools/build_maps.py ice --src "ice lake (1v7).yrm" --out maps
    python tools/build_maps.py flat --src Flat200-raw.yrm --out maps/SuperAI-Flat200.yrm \
        --name "Super AI Flat 200" --players 8 --triggers hunt
    python tools/build_maps.py flat --src Flat120-raw.yrm --out maps/SuperAI-Flat120.yrm \
        --name "Super AI Flat 120" --players 120 --triggers full --move-player-corner

Flat maps are expected to come from VERA20k's ``--generate-map`` with
``Ruggedness=0`` / ``WaterAmount=0`` / ``Vegetation=0``.  See tools/sed/.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import veramap as vm


def cmd_ice(args):
    text = vm.read_text(args.src)
    text = vm.set_name(text, "Super AI Ice Lake 1v7", free_radar=True)
    text = vm.ensure_value(text, "FreeRadar", "yes")

    players = vm.count_waypoints(text)
    text = vm.add_triggers(
        text,
        vm.trigger_block(players, reveal=True, iron_curtain=True, hunt=True,
                         newline="\r\n", hunt_prefix="02", hunt_name="AIHuntAll"),
    )

    os.makedirs(args.out, exist_ok=True)
    main_path = os.path.join(args.out, "SuperAI-IceLake-1v7.yrm")
    vm.write_text(main_path, text)
    print("written %s (%d players, %d bytes)" % (main_path, players, len(text)))

    if not args.no_ore:
        no_ore = vm.drop_sections(text, ("OverlayPack", "OverlayDataPack"), separator="\r\n")
        no_ore = vm.ensure_value(no_ore, "TiberiumGrows", "no")
        no_ore = vm.ensure_value(no_ore, "TiberiumSpreads", "no")
        no_ore = vm.set_name(no_ore, "Super AI Ice Lake 1v7 No Ore")
        path = os.path.join(args.out, "SuperAI-IceLake-1v7-NoOre.yrm")
        vm.write_text(path, no_ore)
        print("written %s (%d bytes)" % (path, len(no_ore)))


def cmd_flat(args):
    text = vm.read_text(args.src)
    text = vm.drop_sections(text, vm.OBJECT_SECTIONS)
    newline = "\r\n" if args.terrain_newline == "crlf" else "\n"
    text, records = vm.uniform_terrain(text, args.tile, args.sub, args.height, newline)
    text = vm.set_name(text, args.name, free_radar=True)
    text = vm.ensure_value(text, "FreeRadar", "yes")

    players = args.players or vm.count_waypoints(text)

    if args.move_player_corner:
        left, top, width, height = vm.local_size(text)
        x, y = left, top + height + args.corner_gap
        packed = vm.pack_cell(x, y)
        text = vm.set_waypoint(text, 0, packed)
        print("player start -> cell (%d, %d) = %d, LocalSize=%s"
              % (x, y, packed, (left, top, width, height)))

    full = args.triggers == "full"
    text = vm.add_triggers(
        text,
        vm.trigger_block(
            players,
            reveal=full,
            iron_curtain=full,
            hunt=True,
        ),
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    vm.write_text(args.out, text)
    print("written %s (%d cells, %d players, triggers=%s, %d bytes)"
          % (args.out, records, players, args.triggers, len(text)))


def cmd_uniform(args):
    text = vm.read_text(args.src)
    newline = "\r\n" if args.terrain_newline == "crlf" else "\n"
    text, records = vm.uniform_terrain(text, args.tile, args.sub, args.height, newline)
    vm.write_text(args.out, text)
    print("written %s (%d cells -> tile %d, height %d)"
          % (args.out, records, args.tile, args.height))


def cmd_info(args):
    text = vm.read_text(args.src)
    print("file      :", args.src)
    print("name      :", vm.get_value(text, "Name", "?"))
    print("local size:", vm.local_size(text))
    print("size      :", vm.get_value(text, "Size", "?"))
    print("maxplayers:", vm.get_value(text, "MaxPlayers", "?"))
    print("waypoints :", vm.count_waypoints(text))

    triggers = 0
    if vm.has_section(text, "Triggers"):
        triggers = len([l for l in vm.section_body(text, "Triggers").splitlines()
                        if "=" in l and not l.strip().startswith(";")])
    print("triggers  :", triggers)

    if vm.has_section(text, "IsoMapPack5"):
        records = vm.decode_terrain(text)
        tiles = collections.Counter(r[2] for r in records)
        heights = collections.Counter(r[4] for r in records)
        print("terrain   : %d cells, top tiles %s, heights %s"
              % (len(records), tiles.most_common(3), heights.most_common(3)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ice = sub.add_parser("ice", help="build the Ice Lake spectator maps")
    ice.add_argument("--src", required=True, help="original 1v7 map")
    ice.add_argument("--out", required=True, help="output folder")
    ice.add_argument("--no-ore", action="store_true", help="skip the no-ore variant")
    ice.set_defaults(func=cmd_ice)

    flat = sub.add_parser("flat", help="build a flat spectator map")
    flat.add_argument("--src", required=True, help="raw generated map")
    flat.add_argument("--out", required=True, help="output .yrm")
    flat.add_argument("--name", required=True, help="map display name")
    flat.add_argument("--players", type=int, default=0,
                      help="start slots (default: read from [Waypoints])")
    flat.add_argument("--tile", type=int, default=418, help="terrain tile id (418 = flat land)")
    flat.add_argument("--sub", type=int, default=0, help="sub-tile index")
    flat.add_argument("--height", type=int, default=4, help="terrain level")
    flat.add_argument("--terrain-newline", choices=("lf", "crlf"), default="lf",
                      help="line ending inside [IsoMapPack5] (cosmetic only)")
    flat.add_argument("--triggers", choices=("full", "hunt"), default="full",
                      help="full = reveal + iron curtain + hunt; hunt = All to Hunt only")
    flat.add_argument("--move-player-corner", action="store_true",
                      help="move waypoint 0 below the playfield (spectator slot)")
    flat.add_argument("--corner-gap", type=int, default=3,
                      help="cells between playfield bottom and the player start")
    flat.set_defaults(func=cmd_flat)

    uniform = sub.add_parser("uniform", help="rewrite terrain only")
    uniform.add_argument("--src", required=True)
    uniform.add_argument("--out", required=True)
    uniform.add_argument("--tile", type=int, default=418)
    uniform.add_argument("--sub", type=int, default=0)
    uniform.add_argument("--height", type=int, default=4)
    uniform.add_argument("--terrain-newline", choices=("lf", "crlf"), default="lf")
    uniform.set_defaults(func=cmd_uniform)

    info = sub.add_parser("info", help="describe a map")
    info.add_argument("--src", required=True)
    info.set_defaults(func=cmd_info)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
