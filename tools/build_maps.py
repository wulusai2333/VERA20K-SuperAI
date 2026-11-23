# -*- coding: utf-8 -*-
"""Build the SuperAI map pack.

Subcommands
-----------
``ice``     sample 1v7 map -> spectator edition, plus a no-ore variant
``flat``    a generated random map -> uniform flat stage with spectator triggers
``retrigger`` replace an existing map's trigger block, terrain untouched
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


#: Ice Lake ground tile (snow theater): tile, sub, height.  Seven of the eight
#: retail start cells stand on exactly this, so it is proven walkable and
#: buildable -- filling the new ground with it cannot introduce a cliff.
ICE_GROUND = (696, 0, 1)

#: Canvas for the 120-player version.  504x512 is the size the proven
#: SuperAI-Flat120 map uses for 120 starts (515584 cells).
ICE120_SIZE = (504, 512)
ICE120_LOCAL = (2, 5, 500, 500)

#: `[Header]` values for that canvas, copied from the proven Flat120 map.
#: Width/Height are the playfield dimensions the minimap uses; StartX/StartY is
#: the camera start.  They are not derivable from Size alone (Flat120 uses
#: 499x500 for a 504x512 map), so the known-good numbers are pinned here.
ICE120_HEADER = {"Width": 499, "Height": 500, "StartX": 6, "StartY": 258}

#: Where the original lake block lands: a rigid translation of every IceLake
#: cell.  ``dx=12, dy=328`` is equivalent to ``dh=-316, dv=+340``, which puts the
#: block (h [-179,179], v [181,420]) at h [-495,-137], v [521,760] -- the
#: upper-left of the playfield (which is h in (-500,500], v in (518,1520]).
ICE_GRAFT = (12, 328)

#: AI start lattice: rows of ``v`` with points spread along ``h``, all of it
#: below/right of the lake block so the player keeps the corner to himself.
ICE120_AI_V = (770, 1520)
ICE120_STEP_H = 48
ICE120_STEP_V = 56
ICE120_MIN_SPACING = 40


def section_list(text):
    """Section names in file order."""
    return [m.group(1).strip() for m in re.finditer(r"(?m)^\[([^\]]+)\]", text)]


def rebuild_header(waypoints, starting_points):
    """``[Header]`` for the 120 canvas, with ``WaypointN`` for every start.

    The header keeps its own coordinate space: half-tile of the diamond axes,
    ``((x-y+512)/2, (x+y+1)/2)``.  That formula reproduces all eight starts of
    both Ice Lake maps exactly and 119 of Flat120's 120 (one rounding edge), so
    it is the engine's own conversion rather than a guess.
    """
    lines = ["[Header]"]
    for key in ("Width", "Height", "StartX", "StartY"):
        lines.append("%s=%d" % (key, ICE120_HEADER[key]))
    for index, (x, y) in enumerate(waypoints, start=1):
        lines.append("Waypoint%d=%d,%d"
                     % (index, ((x - y) + 512) // 2, ((x + y) + 1) // 2))
    lines.append("NumberStartingPoints=%d" % starting_points)
    return "\r\n".join(lines) + "\r\n\r\n"


def cmd_ice120(args):
    """120-player Ice Lake: player alone in the upper-left, 119 AI lower-right.

    Ice Lake's terrain is only 43080 cells (a playfield of roughly 359x240
    screen cells); 119 computer bases cannot fit in it.  So the lake is used as
    *material*: a 504x512 ice canvas is generated, the original lake block is
    translated into the upper-left corner for the player, and the new ice in the
    lower-right holds the 119 computer starts.
    """
    src = vm.read_text(args.src)
    width, height = ICE120_SIZE
    tile, sub, level = ICE_GROUND
    dx, dy = ICE_GRAFT

    # 1. Canvas: every cell of a 504x512 diamond, filled with the lake's ground.
    canvas = {cell: [tile, sub, level, 0]
              for cell in vm.diamond_cells(width, height)}

    # 2. Graft the original lake into the upper-left.
    ice = vm.decode_terrain(src)
    grafted = 0
    graft_cells = []
    for x, y, t, s, z, legacy in ice:
        key = (x + dx, y + dy)
        if key not in canvas:
            raise SystemExit("grafted lake cell %s falls outside the canvas" % (key,))
        canvas[key] = [t, s, z, legacy]
        graft_cells.append(key)
        grafted += 1
    if grafted != len(ice):
        raise SystemExit("grafted %d of %d lake cells" % (grafted, len(ice)))

    # The lake block, in screen space, where it now sits on the canvas.
    lake_h = [min(x - y for x, y in graft_cells), max(x - y for x, y in graft_cells)]
    lake_v = [min(x + y for x, y in graft_cells), max(x + y for x, y in graft_cells)]

    # 3. Player start: the retail player cell, moved with the lake.
    body = vm.section_body(src, "Waypoints")
    player = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("0=") and line.split("=", 1)[1].strip().isdigit():
            player = vm.unpack_cell(int(line.split("=", 1)[1].strip()))
            break
    if player is None:
        raise SystemExit("source map has no waypoint 0")
    player_cell = (player[0] + dx, player[1] + dy)
    if player_cell not in canvas:
        raise SystemExit("player cell %s is outside the canvas" % (player_cell,))

    # 4. 119 computer starts on the ice, below/right of the lake.
    bounds = (width, height, ICE120_LOCAL[0], ICE120_LOCAL[1],
              ICE120_LOCAL[2], ICE120_LOCAL[3])
    h_lo, h_hi = lake_h
    v_lo, v_hi = lake_v

    def in_lake(h, v):
        return h_lo <= h <= h_hi and v_lo <= v <= v_hi

    candidates = []
    for v in range(ICE120_AI_V[0], ICE120_AI_V[1], ICE120_STEP_V):
        # A cell needs ``x``/``y`` integral, i.e. ``h`` and ``v`` of the same
        # parity; step in 2-cell strides from a start of the right parity or
        # every candidate on this row is rejected.
        start = -width + 1
        if (start + v) % 2:
            start += 1
        for h in range(start, width, 2 * ICE120_STEP_H):
            if (h + v) % 2:
                continue
            x, y = vm.hv_to_cell(h, v)
            if x < 0 or y < 0 or (x, y) not in canvas:
                continue
            if not vm.in_playfield(bounds, x, y):
                continue
            if in_lake(h, v):
                continue
            candidates.append((x, y))
    if len(candidates) < args.ai:
        raise SystemExit(
            "only %d start candidates for %d computers; widen ICE120_AI_V or "
            "shrink ICE120_STEP_H" % (len(candidates), args.ai))

    # Spread the picks over the whole candidate set instead of taking the first
    # N, which would pile every base into the top rows.
    step = (len(candidates) - 1) / float(args.ai - 1)
    picks, used = [], set()
    for index in range(args.ai):
        point = candidates[int(round(index * step))]
        if point in used:
            point = next(p for p in candidates if p not in used)
        used.add(point)
        picks.append(point)

    waypoints = [player_cell] + picks
    if len(waypoints) != args.players:
        raise SystemExit("%d waypoints for %d slots" % (len(waypoints), args.players))

    # 5. Assemble a minimal map: exactly the sections the engine needs.
    keep = ("Header", "Basic", "Map", "Lighting")
    parts = [rebuild_header(waypoints, len(waypoints))]
    for name in keep:
        if name == "Header":
            continue
        if not vm.has_section(src, name):
            raise SystemExit("source map has no [%s]" % name)
        parts.append("[%s]\r\n%s\r\n" % (name, vm.section_body(src, name).strip("\r\n")))

    text = "".join(parts)
    text = vm.set_value(text, "Name", "Super AI Ice Lake 120 No Ore")
    text = vm.set_value(text, "Size", "0,0,%d,%d" % (width, height))
    text = vm.set_value(text, "LocalSize", "%d,%d,%d,%d" % ICE120_LOCAL)
    for key, value in (("MaxPlayer", str(args.players)),
                       ("MaxPlayers", str(args.players)),
                       ("MinPlayer", "2"), ("MinPlayers", "2"),
                       ("FreeRadar", "yes"), ("MultiplayerOnly", "1"),
                       ("GameMode", "standard"),
                       ("TiberiumGrows", "no"), ("TiberiumSpreads", "no")):
        text = vm.set_value(text, key, value) if vm.get_value(text, key) is not None \
            else vm.ensure_value(text, key, value)

    records = [[x, y, t, s, z, legacy] for (x, y), (t, s, z, legacy)
               in sorted(canvas.items(), key=lambda kv: (kv[0][1], kv[0][0]))]
    text += vm.encode_terrain(records, "\r\n") + "\r\n"
    text += "[Waypoints]\r\n\r\n"
    text = vm.replace_waypoints(text, waypoints, newline="\r\n")
    # `add_triggers` anchors on [Waypoints] and refuses to merge blocks, so the
    # waypoint section has to be in place first.
    text = vm.add_triggers(
        text,
        vm.trigger_block(len(waypoints), reveal=True, iron_curtain=True,
                         hunt=True, newline="\r\n"),
    )

    # 6. Refuse to ship a map whose starts cannot work.
    if len(records) != len(vm.diamond_cells(width, height)):
        raise SystemExit("terrain cell count %d != canvas" % len(records))
    if player_cell == waypoints[0] and not in_lake(*vm.cell_to_hv(*player_cell)):
        raise SystemExit("player start is not on the grafted lake")
    for index, (x, y) in enumerate(picks, start=1):
        if in_lake(*vm.cell_to_hv(x, y)):
            raise SystemExit("computer start %d sits inside the lake block" % index)
        if not vm.in_playfield(bounds, x, y):
            raise SystemExit("computer start %d is outside the playfield" % index)
    for i in range(len(picks)):
        for j in range(i + 1, len(picks)):
            hi, vi = vm.cell_to_hv(*picks[i])
            hj, vj = vm.cell_to_hv(*picks[j])
            if abs(hi - hj) < ICE120_MIN_SPACING and abs(vi - vj) < ICE120_MIN_SPACING:
                raise SystemExit("computer starts %d and %d are too close"
                                 % (i + 1, j + 1))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    vm.write_text(args.out, text)
    print("written %s (%d cells, %d starts: player %s, %d computers in the "
          "lower-right, %d bytes)"
          % (args.out, len(records), len(waypoints), player_cell, len(picks), len(text)))


def cmd_flat(args):
    text = vm.read_text(args.src)
    text = vm.drop_sections(text, vm.OBJECT_SECTIONS)
    newline = "\r\n" if args.terrain_newline == "crlf" else "\n"
    text, records = vm.uniform_terrain(text, args.tile, args.sub, args.height, newline)
    text = vm.set_name(text, args.name, free_radar=True)
    text = vm.ensure_value(text, "FreeRadar", "yes")

    players = args.players or vm.count_waypoints(text)

    if args.move_player_corner or args.player_inside:
        left, top, width, height = vm.local_size(text)
        if args.player_inside:
            # The playfield is a diamond, not the LocalSize rectangle: the
            # bottom-left corner of the rectangle cannot hold a 4x4 yard, and a
            # unit seeded there is ring-placed elsewhere (out of the curtain).
            x, y = vm.deploy_cell(text, margin=args.player_inside)
        else:
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
            iron_curtain_initial=full,
            hunt=True,
        ),
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    vm.write_text(args.out, text)
    print("written %s (%d cells, %d players, triggers=%s, %d bytes)"
          % (args.out, records, players, args.triggers, len(text)))


def cmd_retrigger(args):
    """Rewrite only the four trigger sections, leaving terrain and starts."""
    text = vm.read_text(args.src)
    newline = "\r\n" if "\r\n" in text else "\n"
    text = vm.drop_sections(text, vm.TRIGGER_SECTIONS, separator=newline)
    players = args.players or vm.count_waypoints(text)
    full = args.triggers == "full"
    text = vm.add_triggers(
        text,
        vm.trigger_block(
            players,
            reveal=full,
            iron_curtain=full,
            iron_curtain_initial=full,
            hunt=True,
            newline=newline,
        ),
    )
    vm.write_text(args.out, text)
    print("written %s (%d players, triggers=%s, %d bytes)"
          % (args.out, players, args.triggers, len(text)))


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

    ice120 = sub.add_parser(
        "ice120", help="120-player Ice Lake: player upper-left, computers lower-right")
    ice120.add_argument("--src", required=True, help="the 1v7 no-ore map (terrain donor)")
    ice120.add_argument("--out", required=True, help="output .yrm")
    ice120.add_argument("--players", type=int, default=120)
    ice120.add_argument("--ai", type=int, default=119, help="computer slots")
    ice120.set_defaults(func=cmd_ice120)

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
    flat.add_argument("--player-inside", type=int, metavar="N", default=0,
                      help="put waypoint 0 on the bottom-left cell where a 4x4 yard "
                           "fits, N cells clear of the playfield edge")
    flat.add_argument("--corner-gap", type=int, default=3,
                      help="cells between playfield bottom and the player start")
    flat.set_defaults(func=cmd_flat)

    retrigger = sub.add_parser("retrigger", help="replace a map's trigger block")
    retrigger.add_argument("--src", required=True)
    retrigger.add_argument("--out", required=True)
    retrigger.add_argument("--players", type=int, default=0,
                           help="start slots (default: read from [Waypoints])")
    retrigger.add_argument("--triggers", choices=("full", "hunt"), default="full",
                           help="full = reveal + iron curtain + hunt; hunt = All to Hunt only")
    retrigger.set_defaults(func=cmd_retrigger)

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
