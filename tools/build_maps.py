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
import re
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
#: retail computer start cells stand on exactly this, so it is proven walkable.
ICE_GROUND_TILE = 696
ICE_GROUND_HEIGHT = 1

#: ICE120_COLS/ROWS/SNAP_RADIUS belonged to the abandoned grid layout; the
#: sampler below needs neither.  ``CORNER_DROP`` samples a few extra points and
#: throws away the ones nearest the player, so the corner stays his alone.
ICE120_CORNER_DROP = 4
ICE120_MIN_SPACING = 10


def rebuild_header(text, waypoints):
    """Rewrite ``[Header]`` so its start list matches ``[Waypoints]``.

    The header keeps its own coordinate space -- half a tile of the diamond
    axes, ``((x-y+512)/2, (x+y+1)/2)``.  That formula reproduces all eight
    starts of both Ice Lake maps exactly (and 119 of Flat120's 120, one
    rounding edge), so it is the engine's own conversion, not a guess.
    ``NumberStartingPoints`` and the ``Width``/``Height``/``StartX``/``StartY``
    of the source are kept.
    """
    body = vm.section_body(text, "Header")
    kept = [line for line in body.splitlines()
            if line.strip() and not re.match(r"(?i)^(Waypoint\d+|NumberStartingPoints)=",
                                             line.strip())]
    lines = ["[Header]"] + kept
    for index, (x, y) in enumerate(waypoints, start=1):
        lines.append("Waypoint%d=%d,%d"
                     % (index, ((x - y) + 512) // 2, ((x + y) + 1) // 2))
    lines.append("NumberStartingPoints=%d" % len(waypoints))
    span = vm.section_span(text, "Header")
    return text[:span[0]] + "\r\n".join(lines) + "\r\n\r\n" + text[span[1]:]


def read_waypoints(text):
    body = vm.section_body(text, "Waypoints")
    out = {}
    for line in body.splitlines():
        line = line.strip()
        if "=" not in line or line.startswith(";"):
            continue
        key, value = line.split("=", 1)
        if key.isdigit() and value.strip().isdigit():
            out[int(key)] = vm.unpack_cell(int(value.strip()))
    return [out[i] for i in sorted(out)]
def cmd_ice120(args):
    """Write a 120-slot copy of the Ice Lake map, terrain untouched.

    Only the start list changes: waypoint 0 (the player) stays exactly where it
    is in the source -- the upper-right corner of this map -- and the 119
    computers are laid out on the proven ground in the lower-left.

    Everything else is copied byte for byte: ``[IsoMapPack5]``, ``Size``,
    ``LocalSize``, ``Theater``, lighting, terrain objects.  ``assert_ice120``
    checks that afterwards, so "I only moved the starts" is verifiable rather
    than a promise.
    """
    src = vm.read_text(args.src)
    waypoints = read_waypoints(src)
    if len(waypoints) < 2:
        raise SystemExit("source map has only %d waypoints" % len(waypoints))
    player = waypoints[0]
    player_h, player_v = vm.cell_to_hv(*player)

    # Cells the retail computer starts stand on: this is the only ground we can
    # promise is standable, because the stock data puts seven starts on it.
    ground = [(x, y) for x, y, tile, _sub, z, _legacy in vm.decode_terrain(src)
              if tile == ICE_GROUND_TILE and z == ICE_GROUND_HEIGHT]

    # Lower-left of the player: smaller h (further left), larger v (further down).
    region = [(x, y) for x, y in ground
              if vm.cell_to_hv(x, y)[0] < player_h and vm.cell_to_hv(x, y)[1] > player_v]
    if not region:
        raise SystemExit("no walkable ground in the lower-left of the player")
    hs = [vm.cell_to_hv(x, y)[0] for x, y in region]
    vs = [vm.cell_to_hv(x, y)[1] for x, y in region]
    if args.verbose:
        print("ground cells: %d total, %d in the lower-left" % (len(ground), len(region)))
        print("lower-left h %d..%d  v %d..%d" % (min(hs), max(hs), min(vs), max(vs)))

    # Even spacing on an irregular region: farthest-point sampling.  Seed with
    # the ground cell furthest from the player, then repeatedly take the cell
    # whose nearest chosen neighbour is furthest away.  That adapts to the lake's
    # patchy ground (a fixed grid left 51 of 132 cells over water) and always
    # yields exactly the requested count, all of them on proven ground.
    hv = {cell: vm.cell_to_hv(*cell) for cell in region}
    wanted = args.ai
    picks = []
    if region:
        seed = max(region, key=lambda c: max(abs(hv[c][0] - player_h),
                                            abs(hv[c][1] - player_v)))
        picks.append(seed)
        chosen = {seed}
        nearest = {c: max(abs(hv[c][0] - hv[seed][0]), abs(hv[c][1] - hv[seed][1]))
                   for c in region}
        target = wanted + ICE120_CORNER_DROP
        floor = args.spacing or 0
        while len(picks) < target:
            candidate, best = None, -1
            for c in region:                       # list order: deterministic
                if c in chosen:
                    continue
                if nearest[c] > best:
                    candidate, best = c, nearest[c]
            if candidate is None or best < floor:
                break
            picks.append(candidate)
            chosen.add(candidate)
            ch, cv = hv[candidate]
            for c in region:
                distance = max(abs(hv[c][0] - ch), abs(hv[c][1] - cv))
                if distance < nearest[c]:
                    nearest[c] = distance
    if len(picks) < wanted:
        raise SystemExit(
            "only %d ground cells for %d computers" % (len(picks), wanted))

    # The player keeps his corner: drop the starts closest to him, then number
    # the rest in a stable order so rebuilds stay byte-identical.
    picks.sort(key=lambda c: max(abs(hv[c][0] - player_h), abs(hv[c][1] - player_v)))
    picks = picks[len(picks) - wanted:]
    picks.sort(key=lambda c: (hv[c][1], hv[c][0]))
    if args.verbose:
        # Nearest-neighbour, not all pairs: the all-pairs maximum is just the
        # region's diagonal and says nothing about how packed the starts are.
        gaps = sorted(
            min(max(abs(hv[a][0] - hv[b][0]), abs(hv[a][1] - hv[b][1]))
                for j, b in enumerate(picks) if j != i)
            for i, a in enumerate(picks))
        print("nearest-neighbour spacing: min %d, median %d, max %d"
              % (gaps[0], gaps[len(gaps) // 2], gaps[-1]))

    all_points = [player] + picks
    if len(all_points) != args.players:
        raise SystemExit("%d waypoints for %d slots" % (len(all_points), args.players))

    text = vm.replace_waypoints(src, all_points, newline="\r\n")
    text = rebuild_header(text, all_points)
    text = vm.set_value(text, "Name", args.name)
    for key, value in (("MaxPlayer", str(args.players)),
                       ("MaxPlayers", str(args.players)),
                       ("MinPlayer", "2"), ("MinPlayers", "2")):
        text = vm.set_value(text, key, value) if vm.get_value(text, key) is not None \
            else vm.ensure_value(text, key, value)

    # The stock AIHuntAll only covers slots 1..7.  Keep the same three triggers
    # but widen All to Hunt to every computer slot, or slots 8+ never leave home.
    text = vm.drop_sections(text, vm.TRIGGER_SECTIONS, separator="\r\n")
    text = vm.add_triggers(
        text,
        vm.trigger_block(len(all_points), reveal=True, iron_curtain=True,
                         hunt=True, newline="\r\n"),
    )

    assert_ice120(src, text, all_points, ground, region)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    vm.write_text(args.out, text)
    print("written %s (%d starts: player %s upper-right, %d computers lower-left "
          "on %d ground cells, %d bytes)"
          % (args.out, len(all_points), player, len(picks), len(region), len(text)))


def assert_ice120(src, text, waypoints, ground, region):
    """Refuse to write anything but "the same map with a new start list"."""
    for section in ("IsoMapPack5", "Terrain", "Structures", "OverlayPack",
                    "OverlayDataPack"):
        if vm.has_section(src, section) != vm.has_section(text, section):
            raise SystemExit("[%s] appeared or disappeared" % section)
        if vm.has_section(src, section) and \
                vm.section_body(src, section) != vm.section_body(text, section):
            raise SystemExit("[%s] changed; only the start list may move" % section)

    for key in ("Size", "LocalSize", "Theater"):
        if vm.get_value(src, key) != vm.get_value(text, key):
            raise SystemExit("%s changed: %r -> %r"
                             % (key, vm.get_value(src, key), vm.get_value(text, key)))

    if len(waypoints) != 120:
        raise SystemExit("%d waypoints, expected 120" % len(waypoints))
    if vm.count_waypoints(text) != len(waypoints):
        raise SystemExit("waypoint count mismatch")
    player = waypoints[0]
    if player != read_waypoints(src)[0]:
        raise SystemExit("player start moved")

    ground_set, region_set = set(ground), set(region)
    for index, cell in enumerate(waypoints[1:], start=1):
        if cell not in ground_set:
            raise SystemExit("computer start %d is not on proven ground" % index)
        if cell not in region_set:
            raise SystemExit("computer start %d is not in the lower-left region" % index)
    for i in range(1, len(waypoints)):
        for j in range(i + 1, len(waypoints)):
            hi, vi = vm.cell_to_hv(*waypoints[i])
            hj, vj = vm.cell_to_hv(*waypoints[j])
            if max(abs(hi - hj), abs(vi - vj)) < ICE120_MIN_SPACING:
                raise SystemExit("starts %d and %d are closer than %d cells"
                                 % (i, j, ICE120_MIN_SPACING))

    header = vm.section_body(text, "Header")
    listed = len(re.findall(r"(?m)^Waypoint\d+=", header))
    declared = vm.get_value(header, "NumberStartingPoints")
    if listed != len(waypoints) or declared != str(len(waypoints)):
        raise SystemExit("header lists %s starts, declares %s, expected %d"
                         % (listed, declared, len(waypoints)))


def nearest_neighbour_gaps(points):
    """Chebyshev nearest-neighbour distance for each point, sorted."""
    hv = [vm.cell_to_hv(*c) for c in points]
    gaps = []
    for i, (h, v) in enumerate(hv):
        best = None
        for j, (h2, v2) in enumerate(hv):
            if i == j:
                continue
            distance = max(abs(h - h2), abs(v - v2))
            if best is None or distance < best:
                best = distance
        gaps.append(best if best is not None else 0)
    return sorted(gaps)


def spread_points(cells, player, wanted):
    """Farthest-point sampling: even coverage of every cell, player excluded.

    Deterministic: the seed is the cell furthest from the player (ties broken by
    cell order) and every later pick scans ``cells`` in its given order, so a
    rebuild of the same source produces the same list.
    """
    if wanted <= 0:
        return []
    available = [c for c in cells if c != player]
    if len(available) < wanted:
        raise SystemExit("only %d cells for %d computers" % (len(available), wanted))
    hv = {c: vm.cell_to_hv(*c) for c in available}
    ph, pv = vm.cell_to_hv(*player)
    seed = max(available, key=lambda c: (max(abs(hv[c][0] - ph), abs(hv[c][1] - pv)), c))
    picks = [seed]
    chosen = {seed}
    nearest = {c: max(abs(hv[c][0] - hv[seed][0]), abs(hv[c][1] - hv[seed][1]))
               for c in available}
    while len(picks) < wanted:
        candidate, best = None, -1
        for c in available:
            if c in chosen:
                continue
            if nearest[c] > best:
                candidate, best = c, nearest[c]
        if candidate is None:
            break
        picks.append(candidate)
        chosen.add(candidate)
        ch, cv = hv[candidate]
        for c in available:
            distance = max(abs(hv[c][0] - ch), abs(hv[c][1] - cv))
            if distance < nearest[c]:
                nearest[c] = distance
    picks.sort(key=lambda c: (hv[c][1], hv[c][0]))
    return picks


def assert_flat120(src, text, points, tile, sub, height, min_gap=8):
    """Refuse to write anything but "one flat tile, nothing on it, even starts".

    The interesting failure modes are silent: a leftover overlay keeps its ore on
    a "flat" map, one terrain record left at another height pokes a cliff through
    it, and a start list the header disagrees with shows up as fewer players in
    the lobby.  Check all three instead of trusting the pipeline.
    """
    problems = []

    source_cells = len(vm.decode_terrain(src))
    records = vm.decode_terrain(text)
    if len(records) != source_cells:
        problems.append("%d terrain cells, source had %d" % (len(records), source_cells))
    wrong = [(r[0], r[1], r[2], r[3], r[4]) for r in records
             if (r[2], r[3], r[4]) != (tile, sub, height)]
    if wrong:
        problems.append("%d cells are not tile %d/%d at height %d (first: %s)"
                        % (len(wrong), tile, sub, height, wrong[0]))

    leftovers = [name for name in vm.OBJECT_SECTIONS if vm.has_section(text, name)]
    if leftovers:
        problems.append("object sections survived: " + ", ".join(leftovers))

    if vm.count_waypoints(text) != len(points):
        problems.append("%d waypoints for %d starts"
                        % (vm.count_waypoints(text), len(points)))
    declared = vm.get_value(vm.section_body(text, "Header"), "NumberStartingPoints")
    if str(declared) != str(len(points)):
        problems.append("header declares %s starting points, waypoints say %d"
                        % (declared, len(points)))

    cells = {(x, y) for x, y, _t, _s, _z, _l in records}
    outside = [c for c in points if c not in cells]
    if outside:
        problems.append("%d starts sit on cells the map does not have" % len(outside))

    gaps = nearest_neighbour_gaps(points[1:])
    if gaps and gaps[0] < min_gap:
        problems.append("computer starts only %d cells apart (floor %d)"
                        % (gaps[0], min_gap))

    triggers = vm.section_body(text, "Triggers") if vm.has_section(text, "Triggers") else ""
    for needed in ("IronCurtainStart", "IronCurtain"):
        if needed not in triggers:
            problems.append("no %s trigger (the player would stand unprotected)" % needed)
    if "RevealAll" not in triggers:
        problems.append("no RevealAll trigger")
    if triggers.count("AIHunt") < 1:
        problems.append("no AIHunt triggers")

    if problems:
        raise SystemExit("flat map check failed: " + "; ".join(problems[:4]))
    return gaps


def cmd_flat(args):
    text = vm.read_text(args.src)
    text = vm.drop_sections(text, vm.OBJECT_SECTIONS)
    newline = "\r\n" if args.terrain_newline == "crlf" else "\n"
    text, records = vm.uniform_terrain(text, args.tile, args.sub, args.height, newline)
    text = vm.set_name(text, args.name, free_radar=True)
    text = vm.ensure_value(text, "FreeRadar", "yes")

    players = args.players or vm.count_waypoints(text)

    if args.player_center or args.spread:
        # Every cell of the source map is now the same flat tile, so the whole
        # terrain is buildable and the starts can use all of it.  The player goes
        # to the centre of the terrain (the Iron Curtain trigger casts at
        # waypoint 0, so "covered" means "standing there"), and the computers are
        # spread with farthest-point sampling.
        cells = [(x, y) for x, y, _t, _s, _z, _l in vm.decode_terrain(text)]
        if not cells:
            raise SystemExit("map has no terrain cells")
        xs = [x for x, _y in cells]
        ys = [y for _x, y in cells]
        if args.player_center:
            x, y = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
            if (x, y) not in set(cells):
                # The diamond has no cell exactly at the rectangle's centre on
                # odd sizes; take the nearest cell that exists.
                x, y = min(cells, key=lambda c: (abs(c[0] - x) + abs(c[1] - y), c))
            text = vm.set_waypoint(text, 0, vm.pack_cell(x, y))
            text = vm.ensure_value(text, "HomeCell", str(vm.pack_cell(x, y)))
            print("player start -> terrain centre (%d, %d)" % (x, y))

        if args.spread:
            player = read_waypoints(text)[0]
            points = spread_points(cells, player, args.spread)
            all_points = [player] + points
            if len(all_points) != players:
                raise SystemExit("%d waypoints for %d slots" % (len(all_points), players))
            text = vm.replace_waypoints(text, all_points, newline="\r\n")
            text = rebuild_header(text, all_points)
            gaps = nearest_neighbour_gaps(all_points[1:])
            print("computers: %d spread over %d cells, nearest-neighbour min %d "
                  "median %d max %d"
                  % (len(points), len(cells), gaps[0], gaps[len(gaps) // 2], gaps[-1]))

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
    # The source may already carry a trigger block (the Ice Lake maps do); drop it
    # so the generated one is the only one, exactly as `ice120` does.
    if vm.has_section(text, "Triggers"):
        text = vm.drop_sections(text, vm.TRIGGER_SECTIONS, separator="\r\n")
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

    if args.player_center or args.spread:
        gaps = assert_flat120(vm.read_text(args.src), text, read_waypoints(text),
                              args.tile, args.sub, args.height)
        print("checked: every cell is %d/%d at height %d, no objects left, "
              "starts %d cells apart at worst"
              % (args.tile, args.sub, args.height, gaps[0] if gaps else 0))

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
        "ice120", help="120-slot Ice Lake: player keeps the upper-right, "
                       "the computers fill the lower-left; terrain untouched")
    ice120.add_argument("--src", required=True,
                        help="the 1v7 no-ore map (left untouched)")
    ice120.add_argument("--out", required=True, help="output .yrm")
    ice120.add_argument("--players", type=int, default=120)
    ice120.add_argument("--ai", type=int, default=119, help="computer slots")
    ice120.add_argument("--spacing", type=int, default=0,
                        help="minimum cells between computer starts (0 = pack "
                             "as evenly as the ground allows)")
    ice120.add_argument("--name", default="Super AI Ice Lake 120 No Ore",
                        help="map display name")
    ice120.add_argument("--verbose", action="store_true")
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
    flat.add_argument("--player-center", action="store_true",
                      help="put waypoint 0 on the centre cell of the terrain")
    flat.add_argument("--spread", type=int, default=0, metavar="N",
                      help="spread N computer starts evenly over the whole terrain "
                           "with farthest-point sampling (implies a rebuilt [Header])")
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
