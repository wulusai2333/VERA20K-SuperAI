# -*- coding: utf-8 -*-
"""Build the SuperAI mod from a stock Yuri's Revenge rules folder.

The mod is a full replacement of ``rulesmd.ini`` / ``artmd.ini`` / ``aimd.ini``.
This script starts from the retail files, applies a fixed list of edits and
writes them next to the ``mod.ini`` that ships in this repository.

    python tools/build_mod.py --rules-dir "<原版规则目录>" --out mod/SuperAI

``--rules-dir`` must contain the retail ``rulesmd.ini``, ``artmd.ini`` and
``aimd.ini`` (a YR install, or the extracted files next to the game).
"""
from __future__ import annotations

import argparse
import math
import os
import re
import shutil

# --------------------------------------------------------------- rules edits
# key: (retail value, mod value)
#
# Kept deliberately small.  The design is "vanilla three-difficulty AI + a few
# mechanisms", so everything that is not needed by one of those mechanisms
# stays at its retail value:
#
#   1. ATTACK HARD  -- teams never regroup at home, every team walks towards
#      the enemy base and charges, no team stays home (the team-type rewrite in
#      build_aimd), map All-to-Hunt clears the base.  Needs only `TeamDelays`
#      (retail 2000/2500/3500 = 133-233 s at 15 frames/s is far too slow to
#      "send units out as soon as they exist").
#   2. REBUILD ON LOSS -- a lost building's plan node is replanned immediately.
#      `AIRestrictReplaceTime=0` is the whole mechanism: 0 means "never
#      restrict", so an ordinary building is replannable the frame it dies,
#      the same way power plants and armed buildings already are.
#   3. NEAREST TARGET -- `TargetDistanceCoefficientDefault=-0.4` keeps the
#      threat score's distance term meaningful across a whole 500x500 map
#      (707-cell diagonal).  Retail's -10 clamps every enemy factory farther
#      than ~39 cells to one point, so "greatest threat" degenerates to the
#      oldest factory.  See the entry's comment below and `assert_attack_script`.
#
# Everything else (AIBuildCounts, the three *BaseDefenseCounts, AIHateDelays,
# the trigger weight deltas) is gone on purpose: the three retail difficulties
# decide the build rhythm, and expansion comes from mechanism 2, not from a
# oversized plan.
RULES_EDITS = {
    "TeamDelays": ("2000,2500,3500", "300,450,600"),
    "MultiplayerAICM": ("400,0,0", "100000,100000,100000"),
    "BuildSpeed": (".7", ".025"),
    # MECHANISM 2.  Retail 400 frames (~27 s) restricts replacement to walls,
    # base defences and power only, right after a building was attacked.  0
    # removes the restriction entirely: any lost building is replannable at
    # once, which is what "被打掉就造" means.  See `node_may_replan` in
    # ai_base_building.rs -- power plants and armed buildings were ALREADY
    # immediate; 0 brings barracks/war factory/lab/depot into line.
    "AIRestrictReplaceTime": ("400", "0"),
    # ZERO walls.  Walls are the single worst offender for "the AI stops
    # developing": every wall segment is a base-plan node taken from the defence
    # budget, and the ring around a `ProtectWithWall=` building also blocks its
    # own pathing.  This key is the ONLY wall entry point in the engine --
    # `choose_building` draws `RandomRanged(0, 99)` for a defence node and calls
    # `build_walls` only when `draw < AIPickWallDefensePercent` -- so 0 means no
    # house ever plans another wall, and every defence draw becomes a real gun.
    # (The other path, `scan_base_perimeter`, only runs when a `-3` control node
    # is consumed; skirmish plan generation never inserts one.)
    "AIPickWallDefensePercent": ("50,25,10", "0,0,0"),
    # Retail refineries duplicate themselves (`AIExtraRefineries=2,1,0`, see
    # `recalc_base_plan`) *on top of* Ares `AIBuildCounts`.  Yuri's 2x2
    # YAREFN, four copies, plus two random extra insertions, filled 56% of one
    # base plan.
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
    #   placements on (817,554) in 11 seconds.  (Since mechanism 2 sets
    #   AIRestrictReplaceTime=0 this matters less, but the duplication count
    #   still does.)
    #
    # 2 makes the gate satisfiable (2 refineries, not 4) and halves the
    # duplication.  The slaves (SLAV) are `Slaved=yes`, not `ResourceGatherer=`,
    # so they never count towards it.
    "AISlaveMinerNumber": ("4,3,2", "2,2,2"),
    "Paranoid": ("yes", "no"),
    # Ten teams per house.  Retail is 30; with charging teams and no regrouping
    # that is a thousand-strong army per house and the frame cost that comes
    # with it.  TEAM SIZE stays retail -- only the count of teams is capped.
    "TotalAITeamCap": ("30,30,30", "10,10,10"),
    # The defensive-team trio must be neutralised, and the reason is a trap
    # that cost a whole release:
    #
    # This mod rewrites EVERY non-MCV team type to `IsBaseDefense=no` (see
    # `build_aimd`), so a house can never own a base-defence team.  In
    # `ai_team_creation.rs`:
    #     base_defense  = <TeamType IsBaseDefense>            -> always false
    #     defense_teams = <teams whose type is base defence>  -> always 0
    #     needs_defense = !has_enemy
    #                     || (use_min_defense_rule && defense_teams < min_defensive)
    #     if needs_defense { base_defense && !defense_full } else { ... }
    # Retail values (UseMinDefenseRule=yes, MinimumAIDefensiveTeams=1) are only
    # self-consistent because retail ships 12 `IsBaseDefense=yes` team types.
    # Ours has none, so a house with an enemy gets `needs_defense = true`
    # forever and the gate admits ONLY base-defence triggers -- of which there
    # are none.  Every trigger fails, no team is ever created, the unit
    # choosers never get a "team still needs" list, and the AI builds no units
    # and never attacks while its base fills up perfectly.  That was 2.2.
    #
    # "Nobody stays home" also needs these at zero, not just for safety.
    "UseMinDefenseRule": ("yes", "no"),
    "MinimumAIDefensiveTeams": ("1,1,1", "0,0,0"),
    "MaximumAIDefensiveTeams": ("2,2,2", "0,0,0"),
    # A team that cannot be filled frees its slot instead of holding it.
    "DissolveUnfilledTeamDelay": ("5000", "2400"),
    # The AI never builds a second airfield at retail: `BuildRadar=` gives it
    # one (GAAIRC for the Allies) and `AirstripLimit=0` forbids any more, so a
    # house owns four pads.  Aircraft are `AirportBound=yes` with `Ammo=1`, so
    # every shot needs a landing, and they crash when there is no free pad --
    # which is exactly what an over-sized air team looks like in game.
    "AirstripLimit": ("0", "4"),
    "AirstripRatio": (".12", ".25"),
    # G1: make "nearest quarry" actually mean nearest.  The threat score adds
    # `E = max(0, distance - range) * TargetDistanceCoefficientDefault`.  An AI
    # team calls `Direct_Greatest_Threat` with its leader's COORDINATES, and in
    # that branch `greatest_threat` computes distance in LEPTONS while range is
    # in CELLS -- a retail mixing bug the engine keeps on purpose.  At retail
    # -10 the score reaches 0 at 100000/10 = 10000 leptons = 39 cells;
    # `finish_score` clamps every farther candidate to 1 and `keep` only
    # replaces on "strictly greater", so the first candidate in stable-id order
    # (the OLDEST enemy factory, i.e. wherever its base was founded) wins.
    # -0.4 moves the clamp point to 100000/0.4 = 250000 leptons = ~977 cells,
    # past the 707-cell maximum diagonal of the largest map: every candidate
    # stays positive, and each extra 10 cells costs 0.4*256*10 = 1024 points, so
    # the distance term strictly prefers the nearest factory (A-D still add on
    # top, so this is "distance matters", not "always the geometrically nearest
    # candidate").  `assert_attack_script` pins the value.
    "TargetDistanceCoefficientDefault": ("-10", "-0.4"),
    # Action 53 (`team_action_gather_at_enemy_base`) walks the team to the
    # passable cell `AISafeDistance` cells from the ENEMY base CENTRE, on the
    # side facing home.  Retail 20 is measured from the enemy centre, so on the
    # crowded maps this mod ships -- three yards per house, bases a few cells
    # apart -- that "staging point" lands inside our own base and the column
    # mills around at home instead of forming up outside the enemy (the
    # new-base congestion this build fixes).  8 then moved it too close: an
    # enemy with three yards has a base radius larger than 8 cells, so the team
    # staged inside the enemy wall; 12 sits outside that wall and still leaves
    # a drive.  `assert_attack_script` pins it.
    "AISafeDistance": ("20", "12"),
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
    # House base-defence response.  `TechnoClass::RespondToBaseAttack` pulls
    # nearby unteamed armed units onto `AreaGuard` + `ArchiveTarget` when a
    # building is hit; `ArchiveTarget` is the engine's escort/follow target, so
    # attacking a fresh expansion yard drags fighting units away from the front.
    # 0 zeroes the budget (`ThreatPosed * 0 = 0`), so the response never scans
    # and never rewrites a mission.  AITrigger teams are unaffected.
    "AI": {"ComputerBaseDefenseResponse": "0"},
    "GADEPT": {"AIBuildThis": "yes"},
    "NADEPT": {"AIBuildThis": "yes"},
    "YADEPT": {"AIBuildThis": "yes"},
    # --- anti-air defences -------------------------------------------------
    # 3.10.x gave NASAM/NAFLAK ground values so the AI would build AA at all;
    # 3.11.6 reverted that hack.  The defence picker chooses a CATEGORY first
    # (from the enemy's cost mix) and only then a building whose value for that
    # category is above zero, so retail's 0/0/25 keeps the two guns reachable
    # only through the air category -- which rarely wins between computer
    # houses.  See docs/ai-tuning-playbook.md §14 and
    # assert_aa_defenses_competitive (which now pins the retail values).
}

#: Comment written beside a rewritten key, replacing the retail one.  Retail's
#: note on these lines reads "taken out to remove useless building - DB",
#: which is exactly the trap this mod is fixing: leaving it in place makes the
#: next reader think the value is still ``no``.
SECTION_KEY_COMMENTS = {
    "AIBuildThis": ";SuperAI: enabled so the AI can build its MCV (see docs/ai-tuning-playbook.md)",
    "AntiInfantryValue": ";SuperAI: retail 0 made the AA gun air-only in the defence picker",
    "AntiArmorValue": ";SuperAI: retail 0 made the AA gun air-only in the defence picker",
}

#: Ares ``SW.*`` keys for the superweapons a computer can actually build.
#:
#: Why they are needed: the AI fires ForceShield (proved by
#: ``sim::superweapon::force_shield  ForceShield launched at ... by 'Computer2'``
#: in ra2.log) but never launches a targeted one -- the log contains no
#: ``SuperWeapon launch queued`` line at all, although that message exists in the
#: binary.  Retail's superweapon sections carry **none** of these keys (all 12
#: have zero ``SW.*`` lines), so the computers were left on whatever the default
#: targeting state is.
#:
#: The engine implements the Ares superweapon extension; the key names below come
#: from the binary (``SW.AllowPlayer SW.AllowAI SW.AutoFire SW.ManualFire
#: SW.AffectsHouse SW.UseAITargeting SW.AITargeting SW.RequiresTarget
#: SW.FireIntoShroud SW.Shots SW.AlwaysGranted``), and ``house_state.rs`` refers
#: to ``SW.AutoFire`` by name.
#:
#: Only the six offensive superweapons the AI can actually build are listed --
#: every one of them belongs to an ``AIBuildThis=yes`` building:
#:
#:   GAWEAT LightningStorm   NAMISL Nuke          YAPPET PsychicDominator
#:   YAGNTC GeneticConverter NAIRON IronCurtain   GACSPH ChronoSphere
#:
#: The support ones (ForceShield already works, ParaDrop, SpyPlane,
#: PsychicReveal) and the AI-unbuildable ChronoWarp (GADUMY has
#: ``AIBuildThis=no``) are deliberately left alone: changing something that
#: already behaves correctly would hide the effect of this change.
#:
#: ``SW.AITargeting`` values are the seven variants of ONE enum in the engine:
#:
#:   offensive_cell_clear   defensive_cell_clear   lightningstorm_inactive
#:   dominator_inactive     attacked               offensive_cell_set
#:   defensive_cell_set
#:
#: The pair that matters is ``*_cell_clear`` vs ``*_cell_set``: **clear** means
#: an empty cell, **set** means a cell that actually has something in it.  Get
#: that wrong and the weapon silently never fires -- which is exactly what
#: happened to the Iron Curtain and the Chrono Sphere in 2.7:
#:
#:   * Iron Curtain covers the house's OWN units, so it needs a *populated*
#:     friendly cell: ``defensive_cell_set``.  ``defensive_cell_clear`` made the
#:     AI look for an empty spot in its own base, and shielding nothing is
#:     pointless, so it never fired.
#:   * Chrono Sphere sends the house's own units somewhere enemy: the useful
#:     target is a *populated* enemy cell, ``offensive_cell_set``.
#:
#: The four damage weapons keep ``offensive_cell_clear``: they were verified in
#: game by the user (nuke and lightning storm both fire), so they are not touched.
SUPERWEAPON_EDITS = {
    # Area-damage weapons: hit a clear cell inside the enemy base.  VERIFIED.
    "NukeSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "LightningStormSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "PsychicDominatorSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "GeneticConverterSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    # The two weapons whose effect lands on the house's OWN units.  2.7 and 2.8
    # both failed to make these fire, and there is no way to test a key
    # headlessly (see the note below), so every plausible key is written with the
    # same intent: pick a cell in our own territory that has units in it.
    #
    # Ares splits the targeting rules into ``SW.AITargeting.Constraints`` and
    # ``SW.AITargeting.Preference`` (both key names are in the binary), while the
    # plain ``SW.AITargeting`` enum is what the working damage weapons use.  Set
    # all three: whichever the engine reads gets the right value, and the ones it
    # ignores cost nothing.
    "IronCurtainSpecial": {
        "SW.AITargeting": "defensive_cell_set",
        "SW.AITargeting.Constraints": "defensive_cell_set",
        "SW.AITargeting.Preference": "defensive_cell_set",
        "SW.AffectsHouse": "yes",
        "SW.AffectsTarget": "yes",
        "SW.AIRequiresTarget": "no",
    },
    "ChronoSphereSpecial": {
        "SW.AITargeting": "offensive_cell_set",
        "SW.AITargeting.Constraints": "offensive_cell_set",
        "SW.AITargeting.Preference": "offensive_cell_set",
        "SW.AffectsHouse": "yes",
        "SW.AffectsTarget": "yes",
        "SW.AIRequiresTarget": "no",
    },
}

#: Why the shot-gun above rather than one measured key: none of the three
#: headless oracles works.  All were tried in 2.9:
#:
#: 1. ``--probe``'s ``rules_digest`` looks like a parsed-rules digest, but it
#:    moves when only a COMMENT changes, so it hashes the file, not the rules
#:    (``tools/probe_rules.py --selftest`` proves this in one run).
#: 2. Invalid values are accepted in silence: ``[NukeSpecial] Type=BogusType``,
#:    ``SW.AutoFire=bogus`` and even a made-up ``SW.TotallyBogusKey=1`` all load
#:    without a warning, so "the engine rejected it" can never be observed.
#: 3. Replays only store the local player's commands (4-5 per match, no AI
#:    actions), and only ``superweapon::force_shield`` ever logs a launch.
#:
#: What IS known: the AI builds both buildings (the log has 912 ``placed
#: NAIRON`` and 121 ``placed GACSPH``), so this is purely about firing; and
#: ``HouseSuperWeaponTargets`` in house_state.rs only models ``nuke_target`` and
#: ``emp_target``, which hints the native AI targeting covers a fixed set of
#: weapons.  If this shot-gun still does not make them fire, the honest
#: conclusion is that the engine has no AI firing path for superweapons that
#: affect the caster's own units.

#: Keys written into every section of :data:`SUPERWEAPON_EDITS`.
SUPERWEAPON_SHARED_KEYS = {
    "SW.AllowPlayer": "yes",
    "SW.AllowAI": "yes",
    "SW.AutoFire": "yes",
    "SW.UseAITargeting": "yes",
    "SW.RequiresTarget": "yes",
}

#: The ``SW.AITargeting`` words this engine understands (from the binary).  A
#: misspelt word is dropped without a warning.
ALLOWED_AITARGETING = {
    "offensive_cell_clear",
    "defensive_cell_clear",
    "offensive_cell_set",
    "defensive_cell_set",
    "attacked",
    "lightningstorm_inactive",
    "dominator_inactive",
}

#: Ares ``AIBuildCounts`` per building type -- only the production buildings
#: that must exist in numbers, and only where the difficulty should differ.
#:
#: The value is either one int (all difficulties) or a 3-tuple ordered
#: ``(hard, normal, easy)`` -- that is the order the engine reads, because
#: ``difficulty_value``/``ai_extra_copies`` index by
#: ``HouseDifficulty::table_index()`` and ``Hard == 0``.  A shorter list is not
#: an error at load time: the missing difficulty simply gets no copies, i.e. one
#: node, which is why ``assert_build_counts`` insists on three entries.
#:
#: What the number means (``ai_extra_copies``): the type always gets its seed
#: node, then ``count - 1`` extra copies, each inserted at a RANDOM position
#: after that first node.  So this is "how many of these a computer base plans",
#: not "how many at the front of the queue" -- the seed node still decides when
#: the type first appears.
#:
#: 2.4 emptied this table to hand the build rhythm back to the retail
#: difficulties; 2.6 reintroduces exactly six entries because a hard computer is
#: supposed to field three barracks and five war factories.  Keep it at this
#: size: the 1.x setting of 60 per type scattered copies across the whole plan
#: and produced 403 power plants against 12 war factories.
BUILD_COUNTS = {
    # Hard computer: 3 barracks.  Normal/easy stay at the retail single node.
    "GAPILE": (3, 1, 1), "NAHAND": (3, 1, 1), "YABRCK": (3, 1, 1),
    # Hard computer: 5 war factories.
    "GAWEAP": (5, 1, 1), "NAWEAP": (5, 1, 1), "YAWEAP": (5, 1, 1),
}

CONSTRUCTION_YARDS = ("GACNST", "NACNST", "YACNST")
REFINERIES = ("GAREFN", "NAREFN", "YAREFN")

#: Retail script used by the three MCV teams: move to a clear spot and deploy.
MCV_DEPLOY_SCRIPT = "043F23CC-G"

#: Our no-assembly attack script.
#:
#: The first action is 53, gather at the enemy base: it walks the team to the
#: passable cell ``AISafeDistance=`` (12) cells from the enemy base centre, on
#: the side facing the team's own base.  Retail's 20 put that point inside our
#: own base whenever the two bases are close (three yards per house), so the
#: column staged at home; 8 staged inside an enemy three-yard base, so 12 is
#: the outside-wall compromise.  That leg is on
#: ``MissionType::Move``, the only mission on which an AI team with
#: ``Aggressive=yes`` / ``Suicide=no`` gets the passive target scan at all
#: (``target_scan.rs``), so the column fires at what it meets on the way in.
#: The scan radius is ``GuardRange=`` or, without it, the weapon range (a Rhino
#: has no GuardRange -> ~5.75 cells): that is "shoot what is on the road", not
#: a full map-wide attack-move.
#:
#: The remaining actions are the retail charge sequence: 0 = attack quarry
#: (6 = enemy factories, 2/1/5 = the other retail quarry classes), 49 = advance.
ATTACK_SCRIPT = "ZAIATK01-G"
ATTACK_SCRIPT_BODY = [
    "[%s]" % ATTACK_SCRIPT,
    "Name=SuperAI Charge",
    "0=53,0",
    "1=0,6",
    "2=49,0",
    "3=0,2",
    "4=0,1",
    "5=0,5",
    "",
]


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


def read_ini_value(lines, section, key):
    """The value of ``key`` inside ``section`` as written, comment stripped."""
    current = None
    for line in lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            continue
        if current != section:
            continue
        m = re.match(r"^" + re.escape(key) + r"=(.*?)(\s*;.*)?(\r?\n)?$", line)
        if m:
            return m.group(1).strip()
    return None


def assert_defense_gate_consistent(rules_lines, aimd_lines):
    """Refuse to ship a rules/AI pair that freezes every AI house.

    ``is_eligible`` gates every AI trigger on ``defense_gate``::

        needs_defense = !has_enemy
                        || (use_min_defense_rule && defense_teams < min_defensive)
        if needs_defense { base_defense && !defense_full } else { ... }

    ``base_defense`` and ``defense_teams`` both come from a TeamType's
    ``IsBaseDefense=``.  This mod rewrites every non-MCV team to
    ``IsBaseDefense=no``, so both are permanently false/zero; if
    ``UseMinDefenseRule`` is yes and ``MinimumAIDefensiveTeams`` is positive,
    ``needs_defense`` is then true whenever an enemy exists and NOTHING is ever
    eligible: no teams, no units, no attacks.  The AI looks brain-dead while its
    base builds perfectly -- a bug that already shipped once as 2.2.
    """
    base_defense_teams = []
    for line in aimd_lines:
        m = re.match(r"^IsBaseDefense=(\w+)", line.strip())
        if m and m.group(1).lower() == "yes":
            base_defense_teams.append(line)
    if base_defense_teams:
        return

    use_min = read_ini_value(rules_lines, "General", "UseMinDefenseRule")
    minimum = read_ini_value(rules_lines, "General", "MinimumAIDefensiveTeams")
    minimum_values = [v.strip() for v in (minimum or "").split(",") if v.strip()]
    if (use_min or "").lower() == "yes" or any(v not in ("0", "") for v in minimum_values):
        raise SystemExit(
            "no TeamType is IsBaseDefense=yes, so no house can ever own a "
            "defensive team; with UseMinDefenseRule=%r and "
            "MinimumAIDefensiveTeams=%r every AI trigger is refused and the AI "
            "never creates a team, never builds units and never attacks. "
            "Set UseMinDefenseRule=no and MinimumAIDefensiveTeams=0,0,0 (or "
            "stop rewriting IsBaseDefense in build_aimd)."
            % (use_min, minimum))


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
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
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


#: A second nuke, owned by the player only.
#:
#: ``RechargeTime`` and ``SW.AllowAI`` live on the superweapon TYPE, so giving
#: the player an instant, unlimited nuke by editing ``[NukeSpecial]`` would have
#: handed 119 computer houses the same thing -- they would launch on every AI
#: tick.  A separate type keeps the retail nuke (and the computer's behaviour)
#: exactly as it was: ``[NAMISL] SuperWeapon=NukeSpecial`` still grants the AI its
#: normal ten-minute nuke, while this one is granted to everyone, marked
#: AI-unusable, and recharges instantly for the human.
PLAYER_NUKE_SECTION = "ZAIUnlimitedNuke"
PLAYER_NUKE_FIELDS = (
    ("UIName", "Name:Nuke"),
    ("Name", "N U K E !!!"),
    ("Type", "MultiMissile"),
    ("WeaponType", "NukeCarrier"),
    ("Action", "Nuke"),
    ("SidebarImage", "NukeIcon"),
    ("Range", "7"),
    ("LineMultiplier", "2"),
    ("IsPowered", "true"),
    ("ShowTimer", "no"),
    # NOT 0: the engine's ReadDouble-shaped readers treat a zero as "keep the
    # current value" (see `read_double_with` in src/rules/ini_value.rs: "a zero
    # that keeps the field"), so RechargeTime=0 silently fell back to the ten
    # minute default.  RechargeTime is a float in minutes (retail uses 8.5 too),
    # so the shortest useful value is 0.01 = about 0.6 s.
    ("RechargeTime", "0.01"),
    # Belt and braces: one charge carries a thousand shots, so even a slow
    # recharge cannot gate the player.
    ("SW.Shots", "1000"),
    ("SW.AllowPlayer", "yes"),
    ("SW.AllowAI", "no"),
    ("SW.AlwaysGranted", "yes"),
    ("SW.RequiresTarget", "yes"),
    ("SW.FireIntoShroud", "yes"),
)
PLAYER_NUKE_COMMENT = (
    ";SuperAI: player-only unlimited nuke (zero cooldown, no silo needed). "
    "The AI keeps [NukeSpecial].")


def apply_player_nuke(lines, name=PLAYER_NUKE_SECTION, fields=None):
    """Append a player-only superweapon section and register it last.

    Idempotent: an existing section and an existing registry entry are replaced,
    not duplicated.  The registry entry is appended at the end on purpose --
    trigger actions index into ``[SuperWeaponTypes]``, so inserting in the middle
    would renumber every later superweapon.
    """
    if fields is None:
        fields = PLAYER_NUKE_FIELDS
        comment = PLAYER_NUKE_COMMENT
    else:
        comment = WORLD_NUKE_COMMENT
    body = ["[%s]\r\n" % name, "%s\r\n" % comment]
    body += ["%s=%s\r\n" % pair for pair in fields]

    # Drop an old copy of the section.
    out, skip = [], False
    for line in lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            skip = header.group(1).strip() == name
        if not skip:
            out.append(line)
    lines[:] = out

    # Drop an old registry entry, then append a fresh one at the end.
    registry = None
    for i, line in enumerate(lines):
        if re.match(r"^\[SuperWeaponTypes\]\s*$", line):
            registry = i
            break
    if registry is None:
        raise SystemExit("[SuperWeaponTypes] not found")
    end = len(lines)
    for i in range(registry + 1, len(lines)):
        if re.match(r"^\[[^\]]+\]\s*$", lines[i]):
            end = i
            break
    entries = {}
    tail = end
    for i in range(registry + 1, end):
        line = lines[i]
        m = re.match(r"^(\d+)\s*=\s*([^;\r\n]+)", line)
        if m:
            entries[int(m.group(1))] = m.group(2).strip()
    entries = {k: v for k, v in entries.items() if v != name}
    next_index = (max(entries) if entries else 0) + 1
    kept = []
    for i in range(registry + 1, end):
        line = lines[i]
        m = re.match(r"^(\d+)\s*=\s*([^;\r\n]+)", line)
        if m and m.group(2).strip() == name:
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    kept.append("%d=%s\r\n" % (next_index, name))
    kept.append("\r\n")
    lines[registry + 1:end] = kept

    # Insert the section right before [SuperWeaponTypes] so the file stays tidy.
    insert_at = registry
    lines[insert_at:insert_at] = body + ["\r\n"]
    return next_index


def assert_player_nuke_section(rules_lines):
    """The player's nuke must be its own type, and the AI's must be untouched."""
    sections, current = {}, None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    def values(name):
        out = {}
        for line in sections.get(name, []):
            m = re.match(r"^([A-Za-z.]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out

    player = values(PLAYER_NUKE_SECTION)
    if not player:
        raise SystemExit("no [%s] section" % PLAYER_NUKE_SECTION)
    wanted = {"sw.alwaysgranted": "yes", "sw.allowai": "no", "sw.allowplayer": "yes"}
    bad = ["%s=%s (want %s)" % (k, player.get(k, "<missing>"), v)
           for k, v in wanted.items() if player.get(k, "").lower() != v]
    try:
        recharge = float(player.get("rechargetime", "nan"))
    except ValueError:
        recharge = float("nan")
    if not (0.0 < recharge <= 0.05):
        bad.append("RechargeTime=%s (want >0 and <=0.05; 0 is read as 'keep "
                   "the default')" % player.get("rechargetime", "<missing>"))
    try:
        shots = int(float(player.get("sw.shots", "0")))
    except ValueError:
        shots = 0
    if shots < 100:
        bad.append("SW.Shots=%s (want >=100)" % player.get("sw.shots", "<missing>"))
    if bad:
        raise SystemExit("[%s] is not the player's unlimited nuke: %s"
                         % (PLAYER_NUKE_SECTION, "; ".join(bad)))
    if PLAYER_NUKE_SECTION not in " ".join(sections.get("SuperWeaponTypes", [])):
        raise SystemExit("[%s] is not registered in [SuperWeaponTypes]"
                         % PLAYER_NUKE_SECTION)

    ai = values("NukeSpecial")
    if ai.get("rechargetime", "").strip() != "10":
        raise SystemExit("[NukeSpecial] RechargeTime=%r; the computer's nuke must "
                         "stay at the retail 10" % ai.get("rechargetime", "<missing>"))
    if ai.get("sw.allowai", "").lower() != "yes":
        raise SystemExit("[NukeSpecial] SW.AllowAI=%r; the computer must keep its "
                         "nuke" % ai.get("sw.allowai", "<missing>"))
    if "sw.alwaysgranted" in ai:
        raise SystemExit("[NukeSpecial] has SW.AlwaysGranted; that belongs on the "
                         "player-only type")
    return True


#: The nuclear gunship: a Kirov-class airship firing homing missiles with nuke
#: warheads.  Everything here is OUR own type; no shared table is touched.
#:
#: 3.12.0 raised its reach to 200 cells, and its warhead is a RENAMED clone of
#: retail ``[NUKE]`` -- see :data:`GUNSHIP_WARHEAD` for why the name matters.
GUNSHIP_UNIT = "ZAINukeGunship"
GUNSHIP_WEAPON = "ZAINukeMissile"
GUNSHIP_PROJECTILE = "ZAINukeMissileProj"

#: The three gunships' `Cost=`.  Priced out of the factory on purpose: the mod's
#: `[General] BuildSpeed=.025` is global, so a build takes `Cost * .025 * .9`
#: frames -- 10k -> 15 s, 100k -> 150 s, 1M -> 25 min, 10M -> ~4.2 h at 15 fps.
#: The delivery superweapons ignore `Cost=`, so these arrive by button, not by
#: production line.  `Points=` (the kill score) is a separate key and stays 100.
GUNSHIP_COST = "1000000"
GUNSHIP2_COST = "100000"
GUNSHIP3_COST = "10000000"

#: The gunship's warhead: retail ``[NUKE]`` under a name of our own.
#:
#: Retail ``[NUKE]`` is not only a damage table -- the engine ALSO keys the
#: nuclear missile's whole impact sequence off the warhead's name:
#:
#:   ``BulletClass::AI``'s ``NUKE`` block (``0x00467E53..0x00467F99``) is entered
#:   by ``strcmpi(warhead, "NUKE")`` and then does three things a normal warhead
#:   never does: ``ScreenNukeFlash`` (a white screen flash plus a full lighting
#:   recalculation -- the whole map's light changes and `[AudioVisual]
#:   AmbientChangeRate/Step` fades it back), a type-13 radar event, and a wait on
#:   the ``NUKEBALL`` anim before the warhead detonates at all.
#:   Evidence: ``src/sim/projectile.rs::nuke_impact`` and
#:   ``src/sim/superweapon/nuke.rs::impact`` in the engine source.
#:
#: A gunship firing that warhead therefore strobes the screen and repaints the
#: map's lighting on every hit (``Burst=8``, eight times a volley).  The same
#: damage table under another section name is an ordinary warhead: it plays its
#: own ``AnimList`` and nothing else.  For retail ``[NUKE]`` that list is
#: ``NUKEANIM`` -- artmd.ini calls it "nuke mushroom cloud explosion" -- so the
#: explosion still looks like a nuke, without the flash and the global light
#: change.  Hence this clone: retail ``[NUKE]`` key for key, renamed.
GUNSHIP_WARHEAD = "ZAINukeMissileWH"
GUNSHIP_WARHEAD_FIELDS = (
    ("CellSpread", "10"),
    ("PercentAtMax", ".02"),
    ("WallAbsoluteDestroyer", "yes"),
    ("Wood", "yes"),
    ("Verses", "100%,100%,100%,200%,100%,100%,60%,100%,8%,100%,100%"),
    ("InfDeath", "7"),
    ("Sparky", "no"),
    ("Tiberium", "yes"),
    # The mushroom cloud.  `[NUKEBALL]` ("nuke explosion buildup") is what the
    # NUKE block spawns, so it is deliberately absent here.
    ("AnimList", "NUKEANIM"),
)
GUNSHIP_UNIT_FIELDS = (
    ("UIName", "Name:ZEP"),
    ("Name", "Nuclear Gunship"),
    # Rules-level Image= points the object at another art section; without it the
    # engine looks for a ZAINukeGunship.vxl that does not exist and draws nothing.
    ("Image", "ZEP"),
    ("Prerequisite", "GAWEAP"),
    ("TechLevel", "1"),
    ("Cost", GUNSHIP_COST),
    ("Strength", "100000"),
    ("Category", "AirPower"),
    ("Armor", "medium"),
    ("Sight", "20"),
    ("RadarInvisible", "no"),
    ("MoveToShroud", "yes"),
    ("BalloonHover", "yes"),
    ("Speed", "8"),
    ("JumpjetSpeed", "8"),
    ("JumpjetClimb", "6"),
    ("JumpjetCrash", "12"),
    ("JumpJetAccel", "10"),
    ("JumpJetTurnRate", "2"),
    ("JumpjetHeight", "750"),
    ("JumpjetNoWobbles", "yes"),
    ("Crashable", "yes"),
    ("PitchSpeed", ".9"),
    ("PitchAngle", "0"),
    ("Owner", "British,French,Germans,Americans,Alliance,Russians,Confederation,"
              "Africans,Arabs,Yuri"),
    ("Points", "100"),
    ("ROT", "10"),
    ("SpeedType", "Hover"),
    ("Crewed", "no"),
    ("ConsideredAircraft", "yes"),
    ("Insignificant", "yes"),
    ("Explosion", "TWLT070,S_BANG48,S_BRNL58,S_CLSN58,S_TUMU60"),
    ("MaxDebris", "14"),
    ("IsSelectableCombatant", "yes"),
    ("Locomotor", "{92612C46-F71F-11d1-AC9F-006008055BB5}"),
    ("MovementZone", "Fly"),
    ("ThreatPosed", "0"),
    ("DamageParticleSystems", "SparkSys,SmallGreySSys"),
    ("SelfHealing", "yes"),
    ("Parasiteable", "no"),
    ("Size", "50"),
    ("Bunkerable", "no"),
    # 3.12.0: 20 -> 200 cells, matching the second gunship.  `GuardRange` is the
    # only auto-acquire radius (a weapon's `Range` just says how far the shot
    # goes), and the build refuses the combination "guard further than the gun
    # reaches" -- the ship would chase targets it can never hit.  So the pair
    # moves together; see `assert_nuke_gunship`.
    ("GuardRange", "200"),
    ("CanPassiveAquire", "yes"),
    ("OpportunityFire", "yes"),
    ("CanRetaliate", "yes"),
    ("Primary", GUNSHIP_WEAPON),
    ("Ammo", "200"),
)
GUNSHIP_WEAPON_FIELDS = (
    ("Damage", "600"),
    ("ROF", "40"),
    ("Range", "200"),
    ("Burst", "8"),
    ("Speed", "120"),
    ("Projectile", GUNSHIP_PROJECTILE),
    ("Warhead", GUNSHIP_WARHEAD),
    ("OmniFire", "yes"),
    ("TurboBoost", "yes"),
    ("Report", "AegisAttack"),
)
GUNSHIP_PROJECTILE_FIELDS = (
    ("Arm", "2"),
    ("AA", "yes"),
    ("AG", "yes"),
    ("Image", "DRAGON"),
    ("ROT", "60"),
    ("Ranged", "yes"),
    ("Shadow", "no"),
    ("Proximity", "no"),
    ("SubjectToCliffs", "no"),
    ("SubjectToElevation", "no"),
    ("SubjectToWalls", "no"),
)


def _replace_section(lines, name, body):
    out, skip = [], False
    for line in lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            skip = header.group(1).strip() == name
        if not skip:
            out.append(line)
    lines[:] = out
    at = len(lines)
    for i, line in enumerate(lines):
        if re.match(r"^\[SuperWeaponTypes\]\s*$", line):
            at = i
            break
    lines[at:at] = body


def _append_registry(lines, section, name):
    reg = None
    for i, line in enumerate(lines):
        if re.match(r"^\[%s\]\s*$" % re.escape(section), line):
            reg = i
            break
    if reg is None:
        raise SystemExit("[%s] not found" % section)
    end = len(lines)
    for i in range(reg + 1, len(lines)):
        if re.match(r"^\[[^\]]+\]\s*(;.*)?$", lines[i]):
            end = i
            break
    kept, highest = [], 0
    for i in range(reg + 1, end):
        line = lines[i]
        m = re.match(r"^(\d+)\s*=\s*([^;\r\n]+)", line)
        if m:
            if m.group(2).strip() == name:
                continue
            highest = max(highest, int(m.group(1)))
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    kept.append("%d=%s\r\n" % (highest + 1, name))
    kept.append("\r\n")
    lines[reg + 1:end] = kept
    return highest + 1


#: Delivering the gunship itself.  The binary carries
#: src/sim/superweapon/unit_delivery.rs plus the UnitDeliveryRules and
#: DeliveryOwner structs, so `Type=UnitDelivery` is a real implementation and not
#: just an Ares key name.  It drops OUR OWN type, so no shared table is involved.
DROP_SW = "ZAINukeGunshipDrop"
DROP_SW2 = "ZAINukeGunship2Drop"
DROP_SW3 = "ZAINukeGunship3Drop"
DROP_SW_FIELDS = (
    ("Type", "UnitDelivery"),
    ("Action", "Nuke"),
    ("SidebarImage", "NukeIcon"),
    ("ShowTimer", "no"),
    ("RechargeTime", "0.01"),
    ("SW.Shots", "1000"),
    ("SW.AllowPlayer", "yes"),
    ("SW.AllowAI", "no"),
    ("SW.AlwaysGranted", "yes"),
    ("SW.InitialReady", "yes"),
    ("SW.RequiresTarget", "yes"),
    ("SW.FireIntoShroud", "yes"),
    # The engine reads the payload from `Deliver.Types`, NOT `UnitDelivery.Types`
    # (the binary's key table holds Deliver.Types / Deliver.BaseNormal /
    # Deliver.Owner, and world_spawn.rs names `Deliver.Buildups`).  With the wrong
    # prefix the superweapon loads and the click does nothing at all.
    ("Deliver.Types", "ZAINukeGunship"),
)

#: Sidebar name and internal name per delivery superweapon.
#:
#: `UIName` is a CSF label, not text: both delivery types used to point at the
#: retail `Name:Nuke`, so a Chinese game showed "核弹攻击" on all three buttons
#: (the unlimited nuke included, which stays that way).  They now get labels of
#: their own, and `UI_LABELS` supplies their text through the generated
#: `ares.csf` -- a label with no row is drawn as `MISSING:'NAME:...'` in game,
#: and `assert_ui_labels` refuses to build that.
DROP_SW_IDENTITY = {
    DROP_SW: ("Name:ZAINukeGunshipDrop", "Nuclear Gunship (drop)"),
    DROP_SW2: ("Name:ZAINukeGunship2Drop", "Aerial Gunship (drop)"),
    DROP_SW3: ("Name:ZAINukeGunship3Drop", "Cluster Gunship (drop)"),
}

#: Text for every `UIName` label this mod introduces, written to
#: `mod/SuperAI/ares.csf`.  Chinese on purpose: the mod's own name is Chinese and
#: its players run the Chinese interface.  The *generic* `ares.csf` is read by
#: every language's game (see tools/csf.py), so these names show up even in an
#: English install.
UI_LABELS = {
    "Name:ZAINukeGunshipDrop": "核弹炮艇",
    "Name:ZAINukeGunship2Drop": "空中炮艇",
    "Name:ZAINukeGunship3Drop": "集束炮艇",
}

#: Retail CSF labels the mod reuses on purpose.  `Name:Nuke` is the sidebar's
#: "核弹攻击"/"Nuke Attack" (kept for the unlimited nuke), `Name:ZEP` is the
#: Kirov's display name (used by both gunship units).  Everything else a mod
#: section writes in `UIName=` has to be one of `UI_LABELS`.
RETAIL_UI_LABELS = frozenset(("name:nuke", "name:zep"))


#: The second gunship reuses the deleted nuke trooper's weapon exactly as it was at
#: 3.10.6: a [MammothTusk] clone firing the ballistic [ZAINukeRifleProj] with the
#: 3-star Dreadnought warhead [ZAINukeWH].  Only per-unit sections are restored --
#: the global [CombatDamage] scatter that version also relied on stays reverted, so
#: this one has to get its spread from the projectile and the warhead alone.
GUNSHIP2_UNIT = "ZAINukeGunship2"
GUNSHIP2_WEAPON = "ZAINukeRifle"
GUNSHIP2_PROJECTILE = "ZAINukeRifleProj"
GUNSHIP2_WARHEAD = "ZAINukeWH"
GUNSHIP2_UNIT_FIELDS = (
    ("UIName", "Name:ZEP"),
    ("Name", "Aerial Gunship"),
    ("Image", "ZEP"),
    ("Prerequisite", "GAWEAP"),
    ("TechLevel", "1"),
    ("Cost", GUNSHIP2_COST),
    ("Strength", "100000"),
    ("Category", "AirPower"),
    ("Armor", "medium"),
    ("Sight", "20"),
    ("RadarInvisible", "no"),
    ("MoveToShroud", "yes"),
    ("BalloonHover", "yes"),
    ("Speed", "8"),
    ("JumpjetSpeed", "8"),
    ("JumpjetClimb", "6"),
    ("JumpjetCrash", "12"),
    ("JumpJetAccel", "10"),
    ("JumpJetTurnRate", "2"),
    ("JumpjetHeight", "750"),
    ("JumpjetNoWobbles", "yes"),
    ("Crashable", "yes"),
    ("PitchSpeed", ".9"),
    ("PitchAngle", "0"),
    ("Owner", "British,French,Germans,Americans,Alliance,Russians,Confederation,"
              "Africans,Arabs,Yuri"),
    ("Points", "100"),
    ("ROT", "10"),
    ("SpeedType", "Hover"),
    ("Crewed", "no"),
    ("ConsideredAircraft", "yes"),
    ("Insignificant", "yes"),
    ("Explosion", "TWLT070,S_BANG48,S_BRNL58,S_CLSN58,S_TUMU60"),
    ("MaxDebris", "14"),
    ("IsSelectableCombatant", "yes"),
    ("Locomotor", "{92612C46-F71F-11d1-AC9F-006008055BB5}"),
    ("MovementZone", "Fly"),
    ("ThreatPosed", "0"),
    ("DamageParticleSystems", "SparkSys,SmallGreySSys"),
    ("SelfHealing", "yes"),
    ("Parasiteable", "no"),
    ("Size", "50"),
    ("Bunkerable", "no"),
    ("GuardRange", "200"),
    ("CanPassiveAquire", "yes"),
    ("OpportunityFire", "yes"),
    ("CanRetaliate", "yes"),
    ("Primary", GUNSHIP2_WEAPON),
    ("Ammo", "200"),
)
GUNSHIP2_WEAPON_FIELDS = (
    ("Damage", "600"),
    ("ROF", "9"),
    ("Range", "200"),
    ("Burst", "1"),
    ("Speed", "20"),
    ("Projectile", GUNSHIP2_PROJECTILE),
    ("Warhead", GUNSHIP2_WARHEAD),
    ("OmniFire", "yes"),
    ("Report", "ApocalypseAttackAir"),
)
GUNSHIP2_PROJECTILE_FIELDS = (
    ("Image", "DRAGON"),
    ("Arcing", "true"),
    ("Inviso", "no"),
    ("AA", "yes"),
    ("AG", "yes"),
    ("Shadow", "no"),
    ("Ranged", "yes"),
    ("Inaccurate", "yes"),
    ("FlakScatter", "yes"),
    # Experiment: the binary carries BallisticScatter.Min/Max tokens next to the
    # global scatter keys.  If a projectile section honours them, the wide spread
    # belongs to this weapon alone and no shared table needs touching.
    ("BallisticScatter.Min", "50"),
    ("BallisticScatter.Max", "200"),
    ("SubjectToCliffs", "no"),
    ("SubjectToElevation", "yes"),
    ("SubjectToWalls", "no"),
)
GUNSHIP2_WARHEAD_FIELDS = (
    ("CellSpread", "3"),
    ("PercentAtMax", ".5"),
    ("Wall", "yes"),
    ("Wood", "yes"),
    ("Verses", "100%,90%,80%,100%,80%,80%,85%,65%,28%,80%,0%"),
    ("Conventional", "yes"),
    ("Rocker", "no"),
    ("InfDeath", "2"),
    ("AnimList", "MININUKE"),
    ("Tiberium", "yes"),
    ("Sparky", "no"),
    ("Bright", "yes"),
    ("ProneDamage", "70%"),
    ("BallisticScatter", "200"),
)


def apply_nuke_gunship2(lines):
    """Write the missile-armed gunship plus the trooper's weapon set."""
    for name, fields in ((GUNSHIP2_UNIT, GUNSHIP2_UNIT_FIELDS),
                         (GUNSHIP2_WEAPON, GUNSHIP2_WEAPON_FIELDS),
                         (GUNSHIP2_PROJECTILE, GUNSHIP2_PROJECTILE_FIELDS),
                         (GUNSHIP2_WARHEAD, GUNSHIP2_WARHEAD_FIELDS)):
        body = ["[%s]\r\n" % name,
                ";SuperAI: second gunship, reusing the nuke trooper's weapon.\r\n"]
        body += ["%s=%s\r\n" % pair for pair in fields]
        _replace_section(lines, name, body)
    _append_registry(lines, "VehicleTypes", GUNSHIP2_UNIT)

    return True


#: The third gunship: the second one's airframe, firing a **four-shot salvo**;
#: every mother bomb lands 0..200 cells off the aim point (a full nuke crater of
#: its own) and then splits into one tracked child bomb that flies back to the
#: clicked cell and detonates inside a +-3-cell patch there.
#:
#: Why four and not eight (3.13.8): `Burst` is a one-shot-per-tick state machine
#: with a 3..5-frame default gap, and only four `BurstDelay0..3` slots exist, so
#: eight shots stretch over ~1.4-2.3 s and read as "one at a time".  Four shots
#: with every delay at zero fire inside ~0.27 s (the same trick the elite
#: Apocalypse uses with `Burst=4`), and `Cluster=2` brings the payload back to
#: eight warheads.  Each mother's pair lands within 3 cells of itself, so the
#: screen shows four clusters, not eight separate craters: the engine cannot do
#: "eight distinct cells spread over 0..100" (see playbook section 20.8).
GUNSHIP3_UNIT = "ZAINukeGunship3"
GUNSHIP3_WEAPON = "ZAINukeCluster"
GUNSHIP3_PROJECTILE = "ZAINukeClusterProj"
GUNSHIP3_CHILD_WEAPON = "ZAINukeClusterChild"
GUNSHIP3_CHILD_PROJECTILE = "ZAINukeClusterChildProj"

#: Launches per trigger.  Four is the largest number whose gaps are all covered
#: by the four `BurstDelay0..3` slots.
GUNSHIP3_BURST = 4
#: Child bombs per mother.  One child each: 4 mothers + 4 children = 8 warheads,
#: five landing points (four stray craters plus the hammered target).
GUNSHIP3_CLUSTER = 1
#: The cluster ship's `Sight=`.  Must be at least `GuardRange` (200), or the
#: 200-cell gun never gets a target a player can see.
GUNSHIP3_SIGHT = "200"
#: Per-shot scatter, in cells, uniform in distance.  0..200 is the support of
#: "mother 0..100 + child 0..100" -- the two independent offsets the design asks
#: for, folded into the one draw the engine gives.  Drop the max to 100 to keep
#: every mother inside 100 cells of the click instead.
GUNSHIP3_SCATTER_MIN = "0"
GUNSHIP3_SCATTER_MAX = "200"

#: Same airframe as the second gunship, plus two things of its own:
#: - four zero burst delays, so the four launches collapse into one ~0.27 s
#:   volley instead of trailing 3..5 frames apart (elite-Apocalypse cadence);
#: - a `Secondary=` slot for the child weapon.  The engine allocates a weapon
#:   named only by `AirburstWeapon=` during the *Bullet* sweep, which runs after
#:   the Weapon sweep, so that weapon's section is never read (`damage=0`,
#:   `projectile=None`) and the split spawns nothing.  Retail works around the
#:   same wall with `Secondary=V3Cluster ;gs Looks like hack is weapons must be
#:   represented once`.  The child carries `Range=0`, so the slot never fires.
GUNSHIP3_UNIT_FIELDS = tuple(
    (key, {"Name": "Cluster Gunship", "Primary": GUNSHIP3_WEAPON,
           "Cost": GUNSHIP3_COST, "Sight": GUNSHIP3_SIGHT}.get(key, value))
    for key, value in GUNSHIP2_UNIT_FIELDS) + (
    ("BurstDelay0", "0"),
    ("BurstDelay1", "0"),
    ("BurstDelay2", "0"),
    ("BurstDelay3", "0"),
    ("Secondary", GUNSHIP3_CHILD_WEAPON),
)
#: Four shots of the second gunship's cadence; every mother carries the SAME
#: nuke blast as its children (`ZAINukeMissileWH`, 10 cells, `NUKEANIM`).  The
#: mother is not a marker any more: it is one of the craters.
GUNSHIP3_WEAPON_FIELDS = (
    ("Damage", "600"),
    ("ROF", "9"),
    ("Range", "200"),
    ("Burst", str(GUNSHIP3_BURST)),
    ("Speed", "20"),
    ("Projectile", GUNSHIP3_PROJECTILE),
    ("Warhead", GUNSHIP_WARHEAD),
    ("OmniFire", "yes"),
    ("Report", "ApocalypseAttackAir"),
)
GUNSHIP3_PROJECTILE_FIELDS = (
    ("Image", "DRAGON"),
    ("Arcing", "true"),
    ("Ranged", "yes"),
    ("Inaccurate", "yes"),
    # ★ `FlakScatter=no` is what makes `BallisticScatter.Min/Max` mean cells at
    # every range.  The flak arm multiplies the draw by `distance / weapon range`,
    # so at half range a 0..200 draw lands 0..100 cells out; the plain arm (taken
    # when this key is false) uses the draw as-is.
    ("FlakScatter", "no"),
    ("BallisticScatter.Min", GUNSHIP3_SCATTER_MIN),
    ("BallisticScatter.Max", GUNSHIP3_SCATTER_MAX),
    ("Airburst", "yes"),
    ("AirburstWeapon", GUNSHIP3_CHILD_WEAPON),
    ("Splits", "yes"),
    ("Cluster", str(GUNSHIP3_CLUSTER)),
    # ★ `AroundTarget=yes` centres the split on the CLICKED CELL: the four
    # mothers fall wherever they like (0..200 cells out), but every pair of
    # children flies back and detonates around the aim point.  That is what makes
    # the shot read as "four stray craters + one hammered target".
    ("AroundTarget", "yes"),
    # Every child must take a different cell of the +-3 patch.
    ("RetargetAccuracy", "0"),
    ("RetargetSelf", "no"),
    ("AA", "no"),
    ("AG", "yes"),
    ("Shadow", "no"),
    ("SubjectToCliffs", "no"),
    ("SubjectToElevation", "yes"),
    ("SubjectToWalls", "no"),
)
#: A child bullet reads only Damage, Warhead, Projectile and Speed from the
#: weapon; ROF/Range describe a turret's cooldown and never apply here.  The
#: warhead is the FIRST gunship's nuke clone (`GUNSHIP_WARHEAD`): 10-cell blast,
#: `NUKEANIM`, and still no screen flash (that needs a warhead named `NUKE`).
GUNSHIP3_CHILD_WEAPON_FIELDS = (
    ("Damage", "200"),
    ("Projectile", GUNSHIP3_CHILD_PROJECTILE),
    # ★ Not the retail 20: a ROT>0 child launches at ONE lepton a frame and only
    # ramps up to this, so 800 is the ceiling, not the launch speed.
    ("Speed", "800"),
    ("Warhead", GUNSHIP_WARHEAD),
    # Registration-only slot: 0 cells keeps it out of targeting.
    ("Range", "0"),
)
#: The child bomb, retail `[ClusterBits]`'s shape.  `ROT=60` is load-bearing: the
#: split fan launches every child straight down, and only a `ROT>0` bullet is
#: re-aimed at its cell.  `Acceleration` must stay small -- the first guided step
#: sinks by `1 + Acceleration` and the terrain-follow block only lifts 18, so
#: anything above 17 buries the child on frame two (3.13.4/3.13.5's 250 did
#: exactly that).  No `Airburst`/`Splits`/`ShrapnelCount`: a child that spawns
#: children turns one shot into an exponential chain.
GUNSHIP3_CHILD_PROJECTILE_FIELDS = (
    ("Image", "DRAGON"),
    ("Arm", "120"),
    ("Proximity", "no"),
    ("Ranged", "yes"),
    ("ROT", "60"),
    ("Acceleration", "10"),
    ("AA", "no"),
    ("AG", "yes"),
    ("Shadow", "no"),
    ("SubjectToCliffs", "no"),
    ("SubjectToElevation", "no"),
    ("SubjectToWalls", "no"),
)


def apply_nuke_cluster(lines):
    """Write the cluster gunship: airframe, mother bomb, and its child."""
    unit = ["[%s]\r\n" % GUNSHIP3_UNIT,
            ";SuperAI: cluster gunship -- four-shot salvo (all BurstDelays 0),\r\n"
            ";  each mother lands 0-200 cells off the aim point and splits into\r\n"
            ";  two nukes inside a +-3-cell patch around that landing.\r\n"]
    unit += ["%s=%s\r\n" % pair for pair in GUNSHIP3_UNIT_FIELDS]
    _replace_section(lines, GUNSHIP3_UNIT, unit)

    for name, fields, comment in (
        (GUNSHIP3_WEAPON, GUNSHIP3_WEAPON_FIELDS,
         ";SuperAI: four shots a trigger (elite-Apocalypse cadence); the mother is\r\n"
         ";  the small pop, the children carry the nuke-sized blast."),
        (GUNSHIP3_PROJECTILE, GUNSHIP3_PROJECTILE_FIELDS,
         ";SuperAI: lands 0-200 cells off the aim point, then splits into Cluster=.\r\n"
         ";  AroundTarget=yes sends every child back to the clicked cell."),
        (GUNSHIP3_CHILD_WEAPON, GUNSHIP3_CHILD_WEAPON_FIELDS,
         ";SuperAI: what each split child is fired as.  Only Damage, Warhead,\r\n"
         ";  Projectile and Speed are read for a child bullet."),
        (GUNSHIP3_CHILD_PROJECTILE, GUNSHIP3_CHILD_PROJECTILE_FIELDS,
         ";SuperAI: retail [ClusterBits]'s shape (ROT=60 tracking child).\r\n"
         ";  Acceleration stays low: the first step sinks 1+Acceleration leptons\r\n"
         ";  and the terrain-follow block lifts only 18."),
    ):
        body = ["[%s]\r\n" % name, comment + "\r\n"]
        body += ["%s=%s\r\n" % pair for pair in fields]
        _replace_section(lines, name, body)

    _append_registry(lines, "VehicleTypes", GUNSHIP3_UNIT)
    return True


def assert_nuke_gunship3(rules_lines, aimd_lines):
    """The cluster gunship must volley, split, and keep its child chain intact."""
    sections, current = {}, None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    def values(name):
        out = {}
        for line in sections.get(name, []):
            m = re.match(r"^([A-Za-z0-9.]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out

    problems = []
    unit = values(GUNSHIP3_UNIT)
    if not unit:
        problems.append("no [%s] section" % GUNSHIP3_UNIT)
    else:
        if unit.get("image", "").strip().upper() != "ZEP":
            problems.append("%s Image=%r (want ZEP or it is invisible)"
                            % (GUNSHIP3_UNIT, unit.get("image")))
        if unit.get("primary", "").strip() != GUNSHIP3_WEAPON:
            problems.append("%s Primary=%r (want %s)"
                            % (GUNSHIP3_UNIT, unit.get("primary"), GUNSHIP3_WEAPON))
        for key, want in (("balloonhover", "yes"), ("insignificant", "yes"),
                          ("canpassiveaquire", "yes"), ("opportunityfire", "yes")):
            if unit.get(key, "").lower() != want:
                problems.append("%s %s=%r (want %s)"
                                % (GUNSHIP3_UNIT, key, unit.get(key), want))
        try:
            strength = int(float(unit.get("strength", "0")))
        except ValueError:
            strength = 0
        if strength < 10000:
            problems.append("%s Strength=%r; anti-air would shoot it down"
                            % (GUNSHIP3_UNIT, unit.get("strength")))
        if unit.get("cost", "").strip() != "10000000":
            problems.append("%s Cost=%r (want 10000000)"
                            % (GUNSHIP3_UNIT, unit.get("cost")))
        # The four zero gaps are what make the volley read as a volley.
        for index in range(4):
            key = "burstdelay%d" % index
            if (unit.get(key, "") or "").strip() != "0":
                problems.append("%s %s=%r (want 0: the stock 3..5-frame gap turns "
                                "the four shots into a queue)"
                                % (GUNSHIP3_UNIT, key.title(), unit.get(key)))
        # The child weapon must be named from a TechnoType slot, or the engine
        # allocates it too late to read its section and the split spawns nothing.
        if unit.get("secondary", "").strip() != GUNSHIP3_CHILD_WEAPON:
            problems.append("%s Secondary=%r (want %s): a weapon named only by "
                            "AirburstWeapon= is allocated during the Bullet sweep, "
                            "after the Weapon sweep, so its section is never read "
                            "(damage=0, projectile=None) and the split spawns "
                            "nothing"
                            % (GUNSHIP3_UNIT, unit.get("secondary"),
                               GUNSHIP3_CHILD_WEAPON))
        try:
            sight = int(float(unit.get("sight", "0")))
        except ValueError:
            sight = 0
        try:
            guard = int(float(unit.get("guardrange", "0")))
        except ValueError:
            guard = 0
        if sight < guard:
            problems.append("%s Sight=%r < GuardRange=%r: the unit cannot see what "
                            "it could shoot, so the range is decoration"
                            % (GUNSHIP3_UNIT, unit.get("sight"),
                               unit.get("guardrange")))

    weapon = values(GUNSHIP3_WEAPON)
    if not weapon:
        problems.append("no [%s] section" % GUNSHIP3_WEAPON)
    for key, want in (("rof", "9"), ("range", "200")):
        if weapon.get(key, "").strip() != want:
            problems.append("%s %s=%r (want %s)"
                            % (GUNSHIP3_WEAPON, key.upper(), weapon.get(key), want))
    # Literal, not `GUNSHIP3_BURST`: the same constant writes the section.
    if (weapon.get("burst", "") or "").strip() != "4":
        problems.append("%s Burst=%r (want 4: four launches whose gaps are all "
                        "covered by BurstDelay0..3)"
                        % (GUNSHIP3_WEAPON, weapon.get("burst")))
    warhead_name = weapon.get("warhead", "").strip()
    if warhead_name.upper() == "NUKE":
        problems.append("%s Warhead=NUKE would flash the screen and repaint the "
                        "map's lighting on every hit; use the renamed clone %s"
                        % (GUNSHIP3_WEAPON, GUNSHIP_WARHEAD))
    elif warhead_name != GUNSHIP_WARHEAD:
        problems.append("%s Warhead=%r (want %s: every mother is a full nuke "
                        "crater, exactly like its children)"
                        % (GUNSHIP3_WEAPON, warhead_name, GUNSHIP_WARHEAD))
    if weapon.get("projectile", "").strip() != GUNSHIP3_PROJECTILE:
        problems.append("%s Projectile=%r (want %s)"
                        % (GUNSHIP3_WEAPON, weapon.get("projectile"),
                           GUNSHIP3_PROJECTILE))
    if unit and weapon:
        try:
            guard = int(float(unit.get("guardrange", "0")))
        except ValueError:
            guard = 0
        try:
            reach = int(float(weapon.get("range", "0")))
        except ValueError:
            reach = 0
        if guard != reach:
            problems.append("GuardRange=%r (want %r: it must match the weapon range "
                            "or the ship locks on to targets it cannot reach)"
                            % (unit.get("guardrange"), reach))

    proj = values(GUNSHIP3_PROJECTILE)
    if not proj:
        problems.append("no [%s] section" % GUNSHIP3_PROJECTILE)
    else:
        if proj.get("airburst", "").lower() != "yes":
            problems.append("%s Airburst=%r (want yes: that is the split switch)"
                            % (GUNSHIP3_PROJECTILE, proj.get("airburst")))
        if proj.get("airburstweapon", "").strip() != GUNSHIP3_CHILD_WEAPON:
            problems.append("%s AirburstWeapon=%r (want %s; without it the engine "
                            "spawns nothing at all)"
                            % (GUNSHIP3_PROJECTILE, proj.get("airburstweapon"),
                               GUNSHIP3_CHILD_WEAPON))
        if proj.get("splits", "").lower() != "yes":
            problems.append("%s Splits=%r (want yes: Cluster= is only read by the "
                            "Splits= branch)"
                            % (GUNSHIP3_PROJECTILE, proj.get("splits")))
        try:
            cluster = int(float(proj.get("cluster", "0")))
        except ValueError:
            cluster = 0
        if cluster != GUNSHIP3_CLUSTER:
            problems.append("%s Cluster=%r (want %d: one child per mother, so a "
                            "trigger is 4 mothers + 4 children = 8 warheads)"
                            % (GUNSHIP3_PROJECTILE, proj.get("cluster"),
                               GUNSHIP3_CLUSTER))
        # The split must be centred on the clicked cell: four stray mothers plus
        # one hammered target is the whole shape of the shot.
        if proj.get("aroundtarget", "").lower() != "yes":
            problems.append("%s AroundTarget=%r (want yes: the four mothers fall "
                            "where they like, but every pair of children has to "
                            "fly back to the clicked cell)"
                            % (GUNSHIP3_PROJECTILE, proj.get("aroundtarget")))
        try:
            accuracy = float(proj.get("retargetaccuracy", "0"))
        except ValueError:
            accuracy = -1.0
        if accuracy != 0.0:
            problems.append("%s RetargetAccuracy=%r (want 0: each child picks a "
                            "different cell of the +-3 patch)"
                            % (GUNSHIP3_PROJECTILE, proj.get("retargetaccuracy")))
        if proj.get("retargetself", "").lower() != "no":
            problems.append("%s RetargetSelf=%r (want no: the gunship must not be "
                            "one of its own split targets)"
                            % (GUNSHIP3_PROJECTILE, proj.get("retargetself")))
        if proj.get("inaccurate", "").lower() != "yes":
            problems.append("%s must keep Inaccurate=yes so the bomb explodes where "
                            "it lands instead of snapping onto the aim cell"
                            % GUNSHIP3_PROJECTILE)
        if proj.get("flakscatter", "").lower() != "no":
            problems.append("%s FlakScatter=%r (want no: the flak arm multiplies "
                            "the BallisticScatter draw by distance/range, so the "
                            "mother would bunch up under maximum range)"
                            % (GUNSHIP3_PROJECTILE, proj.get("flakscatter")))
        if proj.get("arcing", "").lower() not in ("yes", "true"):
            problems.append("%s Arcing=%r (want true: only the arcing arm runs the "
                            "launch scatter)"
                            % (GUNSHIP3_PROJECTILE, proj.get("arcing")))
        if proj.get("ag", "").lower() != "yes":
            problems.append("%s AG=%r; without AG it cannot hit the ground"
                            % (GUNSHIP3_PROJECTILE, proj.get("ag")))
        for key, want in (("ballisticscatter.min", "0"),
                          ("ballisticscatter.max", "200")):
            if (proj.get(key, "") or "").strip() != want:
                problems.append("%s %s=%r (want %s: each mother lands 0..200 cells "
                                "from the aim point)"
                                % (GUNSHIP3_PROJECTILE, key.title(),
                                   proj.get(key), want))
        for homing in ("arm", "rot"):
            if proj.get(homing):
                problems.append("%s has %s=; a homing projectile never scatters"
                                % (GUNSHIP3_PROJECTILE, homing.upper()))

    child_weapon = values(GUNSHIP3_CHILD_WEAPON)
    if not child_weapon:
        problems.append("no [%s] section" % GUNSHIP3_CHILD_WEAPON)
    else:
        if child_weapon.get("projectile", "").strip() != GUNSHIP3_CHILD_PROJECTILE:
            problems.append("%s Projectile=%r (want %s; the engine drops the whole "
                            "split without it)"
                            % (GUNSHIP3_CHILD_WEAPON,
                               child_weapon.get("projectile"),
                               GUNSHIP3_CHILD_PROJECTILE))
        if child_weapon.get("warhead", "").strip() != GUNSHIP_WARHEAD:
            problems.append("%s Warhead=%r (want %s: each child carries the "
                            "nuke-sized blast)"
                            % (GUNSHIP3_CHILD_WEAPON,
                               child_weapon.get("warhead"), GUNSHIP_WARHEAD))
        if (child_weapon.get("speed", "") or "").strip() != "800":
            problems.append("%s Speed=%r (want 800: a ROT>0 child launches at 1 "
                            "lepton/frame and only ramps up to this)"
                            % (GUNSHIP3_CHILD_WEAPON, child_weapon.get("speed")))
        for key in ("spawns", "spawnsnumber"):
            if child_weapon.get(key):
                problems.append("%s has %s=; a split child must not spawn"
                                % (GUNSHIP3_CHILD_WEAPON, key.title()))
        try:
            child_range = float(child_weapon.get("range", "0"))
        except ValueError:
            child_range = -1.0
        if child_range != 0.0:
            problems.append("%s Range=%r (want 0: this weapon exists only so the "
                            "engine reads it during the Weapon sweep)"
                            % (GUNSHIP3_CHILD_WEAPON,
                               child_weapon.get("range")))
        try:
            child_damage = int(float(child_weapon.get("damage", "0")))
        except ValueError:
            child_damage = 0
        if child_damage <= 0:
            problems.append("%s Damage=%r (want >0)"
                            % (GUNSHIP3_CHILD_WEAPON,
                               child_weapon.get("damage")))

    # The load-order rule: whichever weapon `AirburstWeapon=` names must also be
    # named by a TechnoType weapon slot, or the engine allocates it too late.
    airburst_weapon = (proj.get("airburstweapon", "") or "").strip()
    if airburst_weapon:
        slot_keys = ("primary", "secondary", "eliteprimary", "elitesecondary",
                     "deathweapon")
        named_by = [name for name in sections
                    if any(values(name).get(key, "").strip() == airburst_weapon
                           for key in slot_keys)]
        if not named_by:
            problems.append("%s is named only by AirburstWeapon=; no TechnoType "
                            "weapon slot names it, so the engine allocates it after "
                            "the Weapon sweep and never reads its section (the split "
                            "then spawns nothing)" % airburst_weapon)

    child_proj = values(GUNSHIP3_CHILD_PROJECTILE)
    if not child_proj:
        problems.append("no [%s] section" % GUNSHIP3_CHILD_PROJECTILE)
    else:
        for key in ("airburst", "splits"):
            if child_proj.get(key):
                problems.append("%s has %s=; a child that spawns children turns "
                                "one shot into an exponential chain"
                                % (GUNSHIP3_CHILD_PROJECTILE, key))
        if child_proj.get("shrapnelcount"):
            problems.append("%s has ShrapnelCount=; a child that spawns children "
                            "turns one shot into an exponential chain"
                            % (GUNSHIP3_CHILD_PROJECTILE))
        try:
            child_rot = int(float(child_proj.get("rot", "0")))
        except ValueError:
            child_rot = 0
        if child_rot <= 0:
            problems.append("%s ROT=%r (want >0): the split launch velocity is "
                            "straight down and only a tracking bullet is re-aimed "
                            "at its cell, so a ROT=0 child detonates on the spot"
                            % (GUNSHIP3_CHILD_PROJECTILE, child_proj.get("rot")))
        if child_proj.get("arcing", "").lower() in ("yes", "true"):
            problems.append("%s Arcing=yes makes the child ballistic, so it follows "
                            "the straight-down launch velocity instead of its cell"
                            % GUNSHIP3_CHILD_PROJECTILE)
        try:
            child_arm = int(float(child_proj.get("arm", "0")))
        except ValueError:
            child_arm = 0
        if child_arm < 45:
            problems.append("%s Arm=%r (want >=45 frames: the proximity fuse is "
                            "forced on for a ROT>0 child, and only the Arm timer "
                            "keeps it from going off during the climb-out)"
                            % (GUNSHIP3_CHILD_PROJECTILE, child_proj.get("arm")))
        if child_proj.get("proximity", "yes").lower() != "no":
            problems.append("%s Proximity=%r (want no)"
                            % (GUNSHIP3_CHILD_PROJECTILE,
                               child_proj.get("proximity")))
        try:
            child_accel = int(float(child_proj.get("acceleration", "3")))
        except ValueError:
            child_accel = -1
        if not (1 <= child_accel <= 17):
            problems.append("%s Acceleration=%r (want 1..17: the first homing step "
                            "sinks 1+Acceleration leptons straight down, the "
                            "terrain-follow block lifts only 18, and a deeper first "
                            "step detonates the child on frame two)"
                            % (GUNSHIP3_CHILD_PROJECTILE,
                               child_proj.get("acceleration")))
        if child_proj.get("ag", "").lower() != "yes":
            problems.append("%s AG=%r; without AG it cannot hit the ground"
                            % (GUNSHIP3_CHILD_PROJECTILE, child_proj.get("ag")))

    child_wh = values(GUNSHIP_WARHEAD)
    if not child_wh:
        problems.append("no [%s] section (the children's warhead)" % GUNSHIP_WARHEAD)
    elif "nukeanim" not in child_wh.get("animlist", "").lower():
        problems.append("[%s] AnimList=%r (want NUKEANIM: the child carries the "
                        "retail nuke's mushroom cloud)"
                        % (GUNSHIP_WARHEAD, child_wh.get("animlist")))

    if GUNSHIP3_UNIT not in " ".join(sections.get("VehicleTypes", [])):
        problems.append("%s is not in [VehicleTypes]" % GUNSHIP3_UNIT)
    registry = set()
    for line in sections.get("SuperWeaponTypes", []):
        m = re.match(r"^\s*\d+\s*=\s*([^;\r\n]+)", line)
        if m:
            registry.add(m.group(1).strip())
    if GUNSHIP3_UNIT in registry:
        problems.append("%s leaked into [SuperWeaponTypes]" % GUNSHIP3_UNIT)
    in_teams = [line.strip() for line in aimd_lines
                if re.match(r"^\d+=\d+,%s\b" % GUNSHIP3_UNIT, line.strip())]
    if in_teams:
        problems.append("a TaskForce names %s" % GUNSHIP3_UNIT)

    if problems:
        raise SystemExit("cluster gunship check failed: "
                         + "; ".join(problems[:4]))
    return GUNSHIP3_BURST * (1 + GUNSHIP3_CLUSTER)


#: The engine's own code calls this feature "UnitDelivery payload (Ares
#: PlaceUnits)", so both Type values are shipped as two buttons: whichever one the
#: engine recognises is the real name, and the other does nothing.
DROP_SW_TYPES = ("UnitDelivery",)


#: New units need an artmd.ini section as well; without one the engine has no model
#: to draw and the unit is simply invisible until it fires.  Image=ZEP reuses the
#: Kirov's voxel and cameo, so no new art is needed.
#: [CombatDamage] is a single global section -- there is no per-unit copy -- so a
#: wide spread for the missile gunship has to be set there.  The retail flak
#: projectiles are the only other users of that value, and they get their scatter
#: switched off, so widening it does not blind the AI's anti-air.
COMBAT_SCATTER = "200"
FLAK_PROJECTILES = ("FlakProj", "FlakTProj")
FLAK_DAMPING = (("FlakScatter", "no"), ("Inaccurate", "no"))


def apply_unit_delivery(lines):
    """Register the delivery superweapons and point them at the gunships."""
    for name, unit in ((DROP_SW, GUNSHIP_UNIT), (DROP_SW2, GUNSHIP2_UNIT),
                       (DROP_SW3, GUNSHIP3_UNIT)):
        ui_name, display_name = DROP_SW_IDENTITY[name]
        body = ["[%s]\r\n" % name,
                ";SuperAI: click to have the gunship delivered. Player only.\r\n",
                "UIName=%s\r\n" % ui_name,
                "Name=%s\r\n" % display_name]
        for key, value in DROP_SW_FIELDS:
            if key == "Type":
                value = DROP_SW_TYPES[0]
            elif key == "Deliver.Types":
                value = unit
            body.append("%s=%s\r\n" % (key, value))
        _replace_section(lines, name, body)
        _append_registry(lines, "SuperWeaponTypes", name)
    return True


def assert_nuke_gunship2(rules_lines, aimd_lines):
    """The missile gunship must build on the trooper's weapon, and stay AI-free."""
    sections, current = {}, None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    def values(name):
        out = {}
        for line in sections.get(name, []):
            m = re.match(r"^([A-Za-z0-9.]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out

    problems = []
    unit = values(GUNSHIP2_UNIT)
    if not unit:
        problems.append("no [%s] section" % GUNSHIP2_UNIT)
    else:
        if unit.get("primary", "").strip() != GUNSHIP2_WEAPON:
            problems.append("%s Primary=%r (want %s, the trooper's weapon)"
                            % (GUNSHIP2_UNIT, unit.get("primary"), GUNSHIP2_WEAPON))
        if unit.get("image", "").strip().upper() != "ZEP":
            problems.append("%s Image=%r (want ZEP or it is invisible)"
                            % (GUNSHIP2_UNIT, unit.get("image")))
        if unit.get("balloonhover", "").lower() != "yes":
            problems.append("%s must stay BalloonHover=yes" % GUNSHIP2_UNIT)
        if unit.get("insignificant", "").lower() != "yes":
            problems.append("%s must stay Insignificant=yes" % GUNSHIP2_UNIT)
        try:
            hp = int(float(unit.get("strength", "0")))
        except ValueError:
            hp = 0
        if hp < 10000:
            problems.append("%s Strength=%r; anti-air would kill it"
                            % (GUNSHIP2_UNIT, unit.get("strength")))
        if unit.get("cost", "").strip() != "100000":
            problems.append("%s Cost=%r (want 100000)"
                            % (GUNSHIP2_UNIT, unit.get("cost")))
    weapon = values(GUNSHIP2_WEAPON)
    if weapon.get("projectile", "").strip() != GUNSHIP2_PROJECTILE:
        problems.append("%s Projectile=%r" % (GUNSHIP2_WEAPON, weapon.get("projectile")))
    if weapon.get("warhead", "").strip() != GUNSHIP2_WARHEAD:
        problems.append("%s Warhead=%r" % (GUNSHIP2_WEAPON, weapon.get("warhead")))
    proj = values(GUNSHIP2_PROJECTILE)
    if proj.get("ag", "").lower() != "yes":
        problems.append("%s AG=%r; it could not hit the ground"
                        % (GUNSHIP2_PROJECTILE, proj.get("ag")))
    for homing in ("arm", "rot"):
        if proj.get(homing):
            problems.append("%s has %s=; a homing projectile never scatters"
                            % (GUNSHIP2_PROJECTILE, homing.upper()))
    if proj.get("flakscatter", "").lower() != "yes":
        problems.append("%s must keep FlakScatter=yes" % GUNSHIP2_PROJECTILE)
    wh = values(GUNSHIP2_WARHEAD)
    if "mininuke" not in wh.get("animlist", "").lower():
        problems.append("%s AnimList=%r (want MININUKE)"
                        % (GUNSHIP2_WARHEAD, wh.get("animlist")))
    try:
        spread = float(wh.get("cellspread", "0"))
    except ValueError:
        spread = 0.0
    if spread < 2.5 or spread > 4:
        problems.append("%s CellSpread=%r (want 2.5..4)" % (GUNSHIP2_WARHEAD, spread))
    for key in ("ballisticscatter.min", "ballisticscatter.max"):
        try:
            value = float(proj.get(key, "0"))
        except ValueError:
            value = 0.0
        if value < 50:
            problems.append("%s %s=%r (want >=50: this is the weapon-scoped spread "
                            "attempt)" % (GUNSHIP2_PROJECTILE, key, proj.get(key)))
    if GUNSHIP2_UNIT not in " ".join(sections.get("VehicleTypes", [])):
        problems.append("%s is not in [VehicleTypes]" % GUNSHIP2_UNIT)
    registry = set()
    for line in sections.get("SuperWeaponTypes", []):
        m = re.match(r"^\s*\d+\s*=\s*([^;\r\n]+)", line)
        if m:
            registry.add(m.group(1).strip())
    if GUNSHIP2_UNIT in registry:
        problems.append("%s leaked into [SuperWeaponTypes]" % GUNSHIP2_UNIT)
    in_teams = [line.strip() for line in aimd_lines
                if re.match(r"^\d+=\d+,%s\b" % GUNSHIP2_UNIT, line.strip())]
    if in_teams:
        problems.append("a TaskForce names %s" % GUNSHIP2_UNIT)

    if problems:
        raise SystemExit("gunship2 check failed: " + "; ".join(problems[:4]))
    return True


def assert_unit_delivery(rules_lines, aimd_lines):
    """The delivery superweapon must be player-only and name our own unit."""
    sections, current = {}, None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    def values(name):
        out = {}
        for line in sections.get(name, []):
            m = re.match(r"^([A-Za-z.]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out

    problems = []
    # Every delivery type: Type, payload, player-only and instant.  The payload key
    # is `Deliver.Types` (the engine does not read `UnitDelivery.Types`), so each
    # type has to name OUR unit or the click does nothing.
    for name, unit in ((DROP_SW, GUNSHIP_UNIT), (DROP_SW2, GUNSHIP2_UNIT),
                       (DROP_SW3, GUNSHIP3_UNIT)):
        sw = values(name)
        if not sw:
            problems.append("no [%s] section" % name)
            continue
        if sw.get("type", "").strip() != DROP_SW_TYPES[0]:
            problems.append("[%s] Type=%r (want %s)"
                            % (name, sw.get("type"), DROP_SW_TYPES[0]))
        types = [p.strip() for p in sw.get("deliver.types", "").split(",") if p.strip()]
        if unit not in types:
            problems.append("[%s] Deliver.Types=%r does not name %s (the payload "
                            "key is Deliver.Types, not UnitDelivery.Types)"
                            % (name, sw.get("deliver.types"), unit))
        if sw.get("unitdelivery.types"):
            problems.append("[%s] still uses UnitDelivery.Types; the engine reads "
                            "Deliver.Types" % name)
        if sw.get("sw.allowai", "").lower() != "no":
            problems.append("[%s] SW.AllowAI=%r (the computer must not deliver it)"
                            % (name, sw.get("sw.allowai")))
        if sw.get("sw.alwaysgranted", "").lower() != "yes":
            problems.append("[%s] must stay SW.AlwaysGranted=yes" % name)
        try:
            recharge = float(sw.get("rechargetime", "nan"))
        except ValueError:
            recharge = float("nan")
        if not (0.0 < recharge <= 0.05):
            problems.append("[%s] RechargeTime=%r (want >0 and <=0.05; 0 means "
                            "'keep the default')" % (name, sw.get("rechargetime")))
        if name not in " ".join(sections.get("SuperWeaponTypes", [])):
            problems.append("[%s] is not in [SuperWeaponTypes]" % name)
    # Display names: one label of our own each, supplied by ares.csf.  They used
    # to share the retail Name:Nuke, which is why all three sidebar buttons read
    # 核弹攻击 in a Chinese game.
    seen_ui_names = {}
    for name in (DROP_SW, DROP_SW2, DROP_SW3):
        sw_fields = values(name)
        ui_name, display_name = DROP_SW_IDENTITY[name]
        if not sw_fields:
            problems.append("no [%s] section" % name)
            continue
        if sw_fields.get("uiname", "").strip() != ui_name:
            problems.append("[%s] UIName=%r (want %s)"
                            % (name, sw_fields.get("uiname"), ui_name))
        if sw_fields.get("name", "").strip() != display_name:
            problems.append("[%s] Name=%r (want %r)"
                            % (name, sw_fields.get("name"), display_name))
        seen_ui_names.setdefault(sw_fields.get("uiname", "").strip().lower(),
                                 []).append(name)
    for label, owners in sorted(seen_ui_names.items()):
        if len(owners) > 1:
            problems.append("%s share UIName=%r; the buttons would be "
                            "indistinguishable" % (" and ".join(owners), label))
    if DROP_SW + "2" in " ".join(sections.get("SuperWeaponTypes", [])):
        problems.append("[%s2] survived; the PlaceUnits candidate does not work and "
                        "must be gone" % DROP_SW)

    # No shared table may be touched: these are the ones an earlier attempt broke.
    general = values("General")
    if general.get("amerparadropinf", "").strip() != "E1":
        problems.append("[General] AmerParaDropInf=%r; the shared drop table must "
                        "stay at retail" % general.get("amerparadropinf", "<missing>"))
    # The shared tables must be exactly retail: the weapon-scoped scatter attempt
    # below is only worth keeping if it costs nothing globally.
    combat = values("CombatDamage")
    if combat.get("ballisticscatter", "").strip() != "1.0":
        problems.append("[CombatDamage] BallisticScatter=%r; it must stay at retail "
                        "1.0" % combat.get("ballisticscatter", "<missing>"))
    for flak in FLAK_PROJECTILES:
        restored = values(flak)
        for key, want in FLAK_DAMPING:
            if restored.get(key.lower(), "").lower() == want:
                problems.append("[%s] %s=%s; that is the value we damped it to "
                                "during the global experiment and it must be undone"
                                % (flak, key, want))
    for name in ("ParaDropSpecial", "AmericanParaDropSpecial"):
        extra = [k for k in values(name) if k.startswith("sw.")]
        if extra:
            problems.append("[%s] carries %s; the AI's paradrop must be untouched"
                            % (name, ", ".join(extra)))

    in_teams = [line.strip() for line in aimd_lines
                if re.match(r"^\d+=\d+,%s\b" % GUNSHIP_UNIT, line.strip())]
    if in_teams:
        problems.append("a TaskForce names %s: %s" % (GUNSHIP_UNIT, in_teams[0]))

    if problems:
        raise SystemExit("unit delivery check failed: " + "; ".join(problems[:4]))
    return True


def assert_nuke_warhead_clone(retail_rules, built_rules):
    """The gunship's warhead must be retail ``[NUKE]``, key for key -- renamed.

    The rename is what keeps the engine's ``NUKE`` block (screen flash, global
    lighting recalculation, radar event, ``NUKEBALL`` wait) from running, so the
    rest of the section has to stay exactly retail: same blast radius, same
    verses, same mushroom anim.  Compared against the RETAIL section rather than
    against our own previous build, so an edit on either side is caught.
    """
    retail = retail_rules.get("NUKE")
    if not retail:
        raise SystemExit("retail [NUKE] not found in the source rules")
    clone = built_rules.get(GUNSHIP_WARHEAD)
    if not clone:
        raise SystemExit("no [%s] in the built rules" % GUNSHIP_WARHEAD)
    problems = []
    for key, value in sorted(retail.items()):
        if key not in clone:
            problems.append("%s is missing retail [NUKE] %s=%s"
                            % (GUNSHIP_WARHEAD, key, value))
        elif clone[key] != value:
            problems.append("%s %s=%r, retail [NUKE] has %r"
                            % (GUNSHIP_WARHEAD, key, clone[key], value))
    for key in clone:
        if key not in retail:
            problems.append("%s adds %s=, which retail [NUKE] does not have; the "
                            "clone is meant to be the SAME blast under another name"
                            % (GUNSHIP_WARHEAD, key))
    if problems:
        raise SystemExit("nuke warhead clone check failed: "
                         + "; ".join(problems[:4]))
    return len(retail)


def assert_ui_labels(rules_lines, csf_labels):
    """Every ``UIName`` the mod writes must resolve to real text.

    ``UIName=`` is a CSF label, not free text: a label the table does not hold is
    drawn literally as ``MISSING:'NAME:X'`` (the engine's ``CsfFile::text``
    returns exactly that).  So each label of ours has to be a row in the
    `ares.csf` this build writes, and no mod section may point at a label that is
    neither a retail one nor ours.
    """
    problems = []
    for label, text in sorted(UI_LABELS.items()):
        have = csf_labels.get(label)
        if not have:
            problems.append("ares.csf has no %s (the game would draw "
                            "MISSING:'%s')" % (label, label.upper()))
        elif have != text:
            problems.append("ares.csf %s=%r, expected %r" % (label, have, text))

    sections, current = {}, None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, {})
            continue
        if current is not None:
            m = re.match(r"^([A-Za-z.]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if m:
                sections[current][m.group(1).strip().lower()] = m.group(2).strip()
    for section in sorted(sections):
        if not section.upper().startswith("ZAI"):
            continue
        ui_name = sections[section].get("uiname", "").strip()
        if not ui_name or ui_name.lower() in RETAIL_UI_LABELS:
            continue
        if ui_name in csf_labels:
            continue
        problems.append("[%s] UIName=%s is neither a retail label nor a row in "
                        "ares.csf (the game would draw MISSING:'%s')"
                        % (section, ui_name, ui_name.upper()))

    if problems:
        raise SystemExit("UI name check failed: " + "; ".join(problems[:4]))
    return len(UI_LABELS)


def apply_nuke_gunship(lines):
    """Write the gunship, its missile, its projectile and its warhead.

    Our types only: nothing here edits a retail section.
    """
    unit = ["[%s]\r\n" % GUNSHIP_UNIT,
            ";SuperAI: player-built nuclear gunship. The AI never gets it.\r\n"]
    unit += ["%s=%s\r\n" % pair for pair in GUNSHIP_UNIT_FIELDS]
    _replace_section(lines, GUNSHIP_UNIT, unit)

    weapon = ["[%s]\r\n" % GUNSHIP_WEAPON,
              ";SuperAI: homing missile with a nuke warhead.\r\n"]
    weapon += ["%s=%s\r\n" % pair for pair in GUNSHIP_WEAPON_FIELDS]
    _replace_section(lines, GUNSHIP_WEAPON, weapon)

    proj = ["[%s]\r\n" % GUNSHIP_PROJECTILE,
            ";SuperAI: AA+AG homing missile.\r\n"]
    proj += ["%s=%s\r\n" % pair for pair in GUNSHIP_PROJECTILE_FIELDS]
    _replace_section(lines, GUNSHIP_PROJECTILE, proj)

    warhead = ["[%s]\r\n" % GUNSHIP_WARHEAD,
               ";SuperAI: retail [NUKE] under another name, so the engine's NUKE\r\n"
               ";  special case (screen flash + global lighting recalculation +\r\n"
               ";  radar event + NUKEBALL wait) never runs.  The mushroom cloud\r\n"
               ";  comes from AnimList=NUKEANIM; the damage is retail's.\r\n"
               ";  Do NOT rename this to NUKE: strcmpi on the warhead name is\r\n"
               ";  what triggers the flash.\r\n"]
    warhead += ["%s=%s\r\n" % pair for pair in GUNSHIP_WARHEAD_FIELDS]
    _replace_section(lines, GUNSHIP_WARHEAD, warhead)

    _append_registry(lines, "VehicleTypes", GUNSHIP_UNIT)
    return True


def assert_nuke_gunship(rules_lines, aimd_lines):
    """The gunship must be buildable, unkillable, ground-capable and AI-free."""
    sections, current = {}, None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    def values(name):
        out = {}
        for line in sections.get(name, []):
            m = re.match(r"^([A-Za-z.]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out

    problems = []
    unit = values(GUNSHIP_UNIT)
    if not unit:
        problems.append("no [%s] section" % GUNSHIP_UNIT)
    else:
        try:
            tech = int(float(unit.get("techlevel", "-1")))
        except ValueError:
            tech = -1
        if tech < 1:
            problems.append("TechLevel=%r; it must be buildable" % unit.get("techlevel"))
        if not unit.get("prerequisite", "").strip():
            problems.append("no Prerequisite; nothing could build it")
        try:
            strength = int(float(unit.get("strength", "0")))
        except ValueError:
            strength = 0
        if strength < 10000:
            problems.append("Strength=%r; anti-air would shoot it down"
                            % unit.get("strength"))
        if unit.get("cost", "").strip() != "1000000":
            problems.append("Cost=%r (want 1000000)" % unit.get("cost"))
        if unit.get("insignificant", "").lower() != "yes":
            problems.append("must stay Insignificant=yes so AI defences ignore it")
        if unit.get("image", "").strip().upper() != "ZEP":
            problems.append("Image=%r (want ZEP so it borrows the Kirov art; with "
                            "no art of its own the unit is invisible)"
                            % unit.get("image"))
        if unit.get("primary", "").strip() != GUNSHIP_WEAPON:
            problems.append("Primary=%r" % unit.get("primary"))
        if unit.get("balloonhover", "").lower() != "yes":
            problems.append("BalloonHover=%r; it must never need a landing pad"
                            % unit.get("balloonhover"))
        if unit.get("canpassiveaquire", "").lower() != "yes":
            problems.append("CanPassiveAquire=%r; it must fire on its own"
                            % unit.get("canpassiveaquire"))
        if unit.get("opportunityfire", "").lower() != "yes":
            problems.append("OpportunityFire=%r; it must fire while moving"
                            % unit.get("opportunityfire"))
    weapon = values(GUNSHIP_WEAPON)
    warhead_name = weapon.get("warhead", "").strip()
    if warhead_name.upper() == "NUKE":
        problems.append("%s Warhead=NUKE: the retail warhead's NAME is what makes "
                        "the engine run the nuke impact (white screen flash + a "
                        "full global lighting recalculation) on every hit; it has "
                        "to be %s, a renamed clone"
                        % (GUNSHIP_WEAPON, GUNSHIP_WARHEAD))
    elif warhead_name != GUNSHIP_WARHEAD:
        problems.append("%s Warhead=%r (want %s)"
                        % (GUNSHIP_WEAPON, warhead_name, GUNSHIP_WARHEAD))
    try:
        reach = int(float(weapon.get("range", "0")))
    except ValueError:
        reach = 0
    if reach != 200:
        problems.append("%s Range=%r (want 200: same reach as the second gunship)"
                        % (GUNSHIP_WEAPON, weapon.get("range")))
    if unit:
        try:
            guard = int(float(unit.get("guardrange", "0")))
        except ValueError:
            guard = 0
        if guard != reach:
            problems.append("GuardRange=%r (want %r: it must match the weapon range "
                            "or the ship locks on to targets it cannot reach)"
                            % (unit.get("guardrange"), reach))
    warhead = values(GUNSHIP_WARHEAD)
    if not warhead:
        problems.append("no [%s] section" % GUNSHIP_WARHEAD)
    else:
        if "nukeanim" not in warhead.get("animlist", "").lower():
            problems.append("%s AnimList=%r (want NUKEANIM: that is the mushroom "
                            "cloud this clone exists to keep)"
                            % (GUNSHIP_WARHEAD, warhead.get("animlist")))
        try:
            spread = float(warhead.get("cellspread", "0"))
        except ValueError:
            spread = 0.0
        if spread != 10:
            problems.append("%s CellSpread=%r (want 10: retail [NUKE]'s blast)"
                            % (GUNSHIP_WARHEAD, warhead.get("cellspread")))
    if weapon.get("projectile", "").strip() != GUNSHIP_PROJECTILE:
        problems.append("%s Projectile=%r" % (GUNSHIP_WEAPON, weapon.get("projectile")))
    proj = values(GUNSHIP_PROJECTILE)
    if proj.get("ag", "").lower() != "yes":
        problems.append("%s AG=%r; without AG it cannot hit the ground"
                        % (GUNSHIP_PROJECTILE, proj.get("ag")))
    if GUNSHIP_UNIT not in " ".join(sections.get("VehicleTypes", [])):
        problems.append("%s is not in [VehicleTypes]" % GUNSHIP_UNIT)

    in_teams = [line.strip() for line in aimd_lines
                if re.match(r"^\d+=\d+,%s\b" % GUNSHIP_UNIT, line.strip())]
    if in_teams:
        problems.append("a TaskForce names %s: %s" % (GUNSHIP_UNIT, in_teams[0]))

    if problems:
        raise SystemExit("nuke gunship check failed: " + "; ".join(problems[:4]))
    return True


def apply_superweapon_edits(lines):
    """Write the ``SW.*`` auto-fire keys into the AI's superweapon sections.

    Retail has none of these keys, so the computers stay on the default
    targeting state and never launch a targeted superweapon.  Each section gets
    :data:`SUPERWEAPON_SHARED_KEYS` plus its own ``SW.AITargeting``.

    Idempotent on purpose: any existing line for one of these keys is dropped
    first, so re-running the build cannot accumulate duplicates (the INI reader
    would silently keep the last one).
    """
    for name, targeting in SUPERWEAPON_EDITS.items():
        wanted = dict(SUPERWEAPON_SHARED_KEYS)
        wanted.update(targeting)
        start = None
        for i, line in enumerate(lines):
            header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
            if header and header.group(1).strip() == name:
                start = i
                break
        if start is None:
            raise SystemExit("superweapon section [%s] not found" % name)
        end = len(lines)
        for i in range(start + 1, len(lines)):
            if re.match(r"^\[[^\]]+\]\s*$", lines[i]):
                end = i
                break
        # Drop any stale copies of the keys we are about to write.
        keys = {key.lower() for key in wanted}
        kept = []
        for i in range(start + 1, end):
            m = re.match(r"^([^=;\s]+)=", lines[i])
            if m and m.group(1).lower() in keys:
                continue
            kept.append(lines[i])
        new_lines = ["%s=%s\r\n" % (key, value) for key, value in wanted.items()]
        lines[start + 1:end] = new_lines + kept
    return len(SUPERWEAPON_EDITS)


def build_rules(source_dir, out_dir):
    text = open(os.path.join(source_dir, "rulesmd.ini"), "rb").read().decode("latin-1")
    lines = text.splitlines(keepends=True)

    apply_rules_edits(lines)
    apply_section_key_edits(lines)

    # Deployed construction yards reveal the map: no power, no radar needed.
    for yard in CONSTRUCTION_YARDS:
        insert_after_section_header(lines, yard, "SpySat=yes\r\n")

    # Action 54 (`team_action_gather_at_friendly_base`) is what the expansion
    # MCV runs (`043F23CC-G` 0=54,0): it returns to OUR base centre.  Ares reads
    # `AIFriendlyDistance=` for it and falls back to `AISafeDistance=` when the
    # key is absent, so without this line the 53 edit would also drag the MCV
    # deploy point down to 12 cells.  Keep 54 at retail 20.
    if not any(l.startswith("AIFriendlyDistance=") for l in lines):
        for i, line in enumerate(lines):
            if line.startswith("AISafeDistance="):
                lines.insert(i + 1, "AIFriendlyDistance=20\r\n")
                break
        else:
            raise SystemExit("AISafeDistance= not found")

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

    # Ares SW.* : make a charged superweapon actually get launched by the AI.
    apply_superweapon_edits(lines)
    player_nuke_index = apply_player_nuke(lines)
    apply_nuke_gunship(lines)
    apply_nuke_gunship2(lines)
    apply_nuke_cluster(lines)
    apply_unit_delivery(lines)

    # Ares AIBuildCounts: planned copies of the production buildings that must
    # exist in numbers, keyed by difficulty (hard, normal, easy).
    out = []
    inserted = set()
    for line in lines:
        out.append(line)
        m = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if m and m.group(1).strip() in BUILD_COUNTS and m.group(1).strip() not in inserted:
            name = m.group(1).strip()
            count = BUILD_COUNTS[name]
            vector = count if isinstance(count, tuple) else (count, count, count)
            out.append("AIBuildCounts=%d,%d,%d\r\n" % vector)
            inserted.add(name)
    missing = set(BUILD_COUNTS) - inserted
    if missing:
        raise SystemExit(
            "AIBuildCounts targets not found as sections: %r (a typo here is "
            "silently ignored by the engine)" % sorted(missing))
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
            m = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
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


#: Team-script actions that cast a superweapon on the team itself.
#: 53/54 are gather-at-enemy-base / regroup-at-base, 55 is the Iron Curtain,
#: 56/57 are the chronoshift variants (see team_script_vm/actions.rs).
SUPERWEAPON_SCRIPT_ACTIONS = ("55", "56", "57")

#: Units that fly.  A team whose task force holds one of these is an "air team":
#: its `Max=` caps how many such teams a house may have at once, and retail caps
#: every one of them at 1, which is why an AI never fields an air force worth
#: watching.  `SCHP` (Siege Chopper) is a vehicle and is deliberately absent.
#:
#: ``JUMPJET`` (the Allied Rocketeer) belongs here even though it is infantry:
#: it flies, so it is exactly the unit the air boost exists for.  It is also in
#: :data:`AA_UNITS` because it shoots aircraft, and the air/AA branch below
#: checks air first -- before this was spelled out, the Rocketeers fell through
#: to the AA branch and kept `Max=1`, five men and a decaying weight, which is
#: why Allied rocketeers stayed rare while Kirovs became common.
AIR_UNITS = {"ORCA", "BEAG", "ZEP", "BPLN", "HORNET", "ASW", "APACHE", "SPYP",
             "JUMPJET"}

#: Ground units that can shoot at aircraft.  Teams carrying one are "AA teams".
AA_UNITS = {"FV", "FLAKT", "YTNK", "APOC", "TELE", "HIND", "AEGIS", "JUMPJET", "GGI"}

#: Aircraft that must land on an airfield pad: ``AirportBound=yes`` and
#: ``Dock=GAAIRC`` in rulesmd.ini, with ``Ammo=1`` so every shot means a landing.
#: A house can only keep as many of these alive as it has pads --
#: ``[GAAIRC] NumberOfDocks=4`` -- and retail's own comment says it crashes when
#: it has nowhere to land.  These teams get a small size and a low cap instead of
#: the big numbers the free-flying units get.
AIRPORT_AIRCRAFT = {"ORCA", "BEAG"}
#: Aircraft per airport-bound team, and how many such teams may exist: 4 x 3 = 12
#: aircraft against 4 pads per airfield, so three airfields are exactly enough.
AIRPORT_TEAM_SIZE = 4
AIRPORT_TEAM_MAX = 3
#: The flying infantry fills slowly (one barracks, expensive men), so a team that
#: is too big is dissolved before it can form.  Six fits in one dissolve window.
AIR_INFANTRY_SIZE = 6

#: How many of a team type a house may have at once after the boost.
AIR_TEAM_MAX = 6
#: Weight multiplier for the triggers that form air / AA teams.  Weights are per
#: difficulty and stay proportional to each other.
AIR_WEIGHT_FACTOR = 3
AA_WEIGHT_FACTOR = 2
#: Ceiling for a rewritten weight, and the aircraft count per air task force:
#: at least AIR_UNIT_MIN (a one-Kirov team is not an air force), then scaled by
#: AIR_SIZE_FACTOR, never more than AIR_UNIT_CAP.
WEIGHT_CAP = 1500
AIR_UNIT_MIN = 3
AIR_SIZE_FACTOR = 2
AIR_UNIT_CAP = 16

#: The seven retail attack triggers that ship with every difficulty bit off
#: (`0,0,0` in tokens 15-17).  They can never be drawn on any difficulty, so
#: the unit composition and the team are pure dead data:
#:
#:   0C0C7AEC-G  Allied Bombard - E1           easy
#:   0C0D251C-G  Soviet Bombard Easy           easy
#:   0C9565AC-G  Allied Spy vs Allied Tech     normal + hard
#:   0AA846FC-G  Allied IFV Rush vs Ally Con   normal + hard
#:   0AA845AC-G  Allied IFV Rush vs Sov Con    normal + hard
#:   0616004C-G  Soviet Siege Bunker_1         normal + hard
#:   07C330CC-G  Soviet Siege Bunker_2         normal + hard
#:
#: Each is restored to the difficulty its own name advertises -- nothing is
#: opened on a difficulty it did not target.
DEAD_TRIGGER_DIFFICULTY = {
    "0C0C7AEC-G": "100",
    "0C0D251C-G": "100",
    "0C9565AC-G": "011",
    "0AA846FC-G": "011",
    "0AA845AC-G": "011",
    "0616004C-G": "011",
    "07C330CC-G": "011",
}

#: The condition-4 attack triggers are "the enemy's available money compares"
#: with amount 0 / `>=`, i.e. always true once an enemy exists; their problem
#: was never the condition but the decaying weight floor.
ATTACK_FLOOR_CONDITION = "4"
#: How many condition-4 triggers retail ships with `floor < ceiling` (and
#: therefore with a floor that sinks when teams die).  Asserted exactly.
ATTACK_FLOOR_EXPECTED = 46

#: Weight for the three "always eligible" attack triggers: the floor under the
#: three difficulties, not a replacement for them.  Far below the 5000 takeover
#: triggers (MCV/superweapon/anti-spy) and the 1000 AA triggers, so counter
#: teams are still drawn first.
ALWAYS_TRIGGER_WEIGHTS = ("30.000000", "30.000000", "30.000000")
#: 32-byte comparison mask.  `condition=-1` never reads it, but the reader
#: still needs exactly 64 hex characters or it drops the whole trigger.
ALWAYS_TRIGGER_MASK = "0000000003000000" + "0" * 48
#: (trigger id, display name, primary TeamType, side token).  The teams are
#: retail attack teams with `Max>=2` -- `at_max_teams` would otherwise keep the
#: trigger from ever firing while the first team is alive.
ALWAYS_TRIGGER_SPEC = (
    ("ZAIALW01-G", "ZAI Always Attack - Allied", "0CA0486C-G", "1"),
    ("ZAIALW02-G", "ZAI Always Attack - Soviet", "09B58D0C-G", "2"),
    ("ZAIALW03-G", "ZAI Always Attack - Yuri", "08B9108C-G", "3"),
)


def teams_using_superweapon_scripts(doc):
    """Team ids whose script contains an Iron Curtain / chronoshift action.

    ``[ScriptTypes]`` only lists script ids; the actions live in each script's
    own section (``[0C31EA4C-G]`` holds ``2=55,0``), so every section is scanned.
    """
    bodies = {}
    section = None
    for line in doc.lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            bodies.setdefault(section, [])
            continue
        if section is not None and stripped and not stripped.startswith(";"):
            bodies[section].append(stripped)

    scripts = set()
    for name, body in bodies.items():
        for entry in body:
            if "=" not in entry:
                continue
            value = entry.split("=", 1)[1]
            if value.split(",")[0].strip() in SUPERWEAPON_SCRIPT_ACTIONS:
                scripts.add(name)
                break
    if not scripts:
        return set()

    teams = set()
    for tid in doc.team_ids():
        fields = doc.values(tid)
        if "script" in fields and fields["script"][0].strip() in scripts:
            teams.add(tid)
    return teams


def build_aimd(source_dir, out_dir, assembly_teams=False):
    """Rewrite the AI teams for mechanism 1: charge, and nobody stays home.

    Deliberately minimal.  Retail's team types, task forces, trigger weights
    and per-difficulty trigger flags are all left alone -- the three retail
    difficulties are supposed to keep deciding how the AI fights.  Only two
    things change per TeamType:

    * ``Script`` becomes :data:`ATTACK_SCRIPT` (skip the regroup-at-home step,
      move towards the enemy base first, then charge), except the three MCV
      teams, which keep the retail move-and-deploy script;
    * ``Aggressive=yes`` and ``IsBaseDefense=no``.

    ``IsBaseDefense=no`` is what makes "nobody stays home" true: with no
    base-defence team types in the set, a house cannot own a defensive team.
    That is only safe because ``UseMinDefenseRule=no`` and the two
    ``*AIDefensiveTeams`` are zero -- see ``assert_defense_gate_consistent``.

    ``assembly_teams`` is a DIAGNOSTIC switch, not a gameplay option: it skips
    the script rewrite so the teams keep retail's "regroup at base, then attack"
    behaviour.  It exists to answer one question -- do the Iron Curtain and the
    Chrono Sphere only fail because this mod never leaves the AI with a cluster
    of units (the Iron Curtain covers a 3x3 cell patch, so it needs one)?  Build
    it into a separate mod folder and compare in game; the shipped mod keeps
    charging.

    A final pass, :func:`boost_attack_triggers`, deliberately departs from the
    2.4 "leave the trigger weights to the difficulties" decision by three
    narrow amounts: it revives the seven triggers retail ships on no
    difficulty at all, raises the weight floor of the 46 decaying condition-4
    attack triggers to their start weight (so losing teams no longer sink the
    attack rate), and appends three weight-30 always-eligible attack triggers.
    Nothing else in the trigger table is touched -- no difficulty bit is opened
    beyond the difficulty a trigger's own name declares, the 42 counter/task
    conditions stay as they are, and the 5000 takeover triggers keep their
    weights.  See ``docs/ai-design.md`` 3.3.1.
    """
    text = open(os.path.join(source_dir, "aimd.ini"), "rb").read().decode("latin-1")
    doc = Aimd(text)

    team_ids = doc.team_ids()

    # Scripts that cast a superweapon on the team itself.  Retail uses them to
    # make the AI actually fire the Iron Curtain and the Chrono Sphere:
    #
    #   0C31EA4C-G = 0=53,0  gather at the enemy base
    #                1=5,10  wait
    #                2=55,0  Iron Curtain on this team      <- action 55
    #                3=49,0  attack
    #   0CAC55CC-G = 0=54,0  regroup at base
    #                1=57,9  chronoshift this team          <- action 57
    #                2=5,10  wait, 3=49,0 attack
    #
    # and the matching AITriggerTypes use condition 5 (Iron Curtain nearly ready)
    # and 6 (Chrono Sphere nearly ready) at weight 5000.  Teams using these
    # scripts must keep them: replacing the script with the charge script throws
    # the superweapon action away, which is exactly what the 2.4 "one script for
    # every team" rewrite did -- the AI kept building the silos (the log has 912
    # `placed NAIRON`) and never cast anything, because the only code path that
    # casts them is this script action.
    super_script_teams = teams_using_superweapon_scripts(doc)

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

    # Every team charges except the three MCV teams, which deploy expansions,
    # and the teams whose retail script casts a superweapon.
    switched = 0
    preserved = 0
    for tid in team_ids:
        fields = doc.values(tid)
        name = fields.get("name", ("", 0))[0]
        if re.search(r"(^|\W)MCV(\W|$)", name, re.I):
            if "script" in fields:
                doc.replace_value(fields["script"][1], "Script", MCV_DEPLOY_SCRIPT)
            if "aggressive" in fields:
                doc.replace_value(fields["aggressive"][1], "Aggressive", "no")
            # `at_max_teams` blocks at `teams >= Max` per house.  Keep the
            # retail 1: two expansion MCVs on the road at once drive to the
            # same free patch and block each other's deploy (`MCV deploy
            # blocked`), which is exactly the new-base congestion this build
            # fixes.  Expansion still reaches three yards -- the `< 3` trigger
            # draws the next MCV once this one has deployed.
            if "max" in fields:
                doc.replace_value(fields["max"][1], "Max", "1")
            continue
        if tid in super_script_teams:
            preserved += 1
        elif "script" in fields and not assembly_teams:
            doc.replace_value(fields["script"][1], "Script", ATTACK_SCRIPT)
            switched += 1
        for key, wanted in (("Aggressive", "yes"), ("IsBaseDefense", "no")):
            if key.lower() in fields:
                doc.replace_value(fields[key.lower()][1], key, wanted)
            else:
                doc.insert_value(tid, key, wanted)

    # Base recovery.  The stock "this house owns zero Construction Yards"
    # triggers (condition 1 with GACNST/NACNST/YACNST) rebuild an MCV, but
    # retail enables them on hard only (`0,0,1`) with weight 70.
    #
    # Weight 5000 is `PRIORITY_WEIGHT` in `ai_team_creation.rs`: the first
    # eligible 5000 trigger CLEARS every other trigger out of that draw, so
    # while a house owns no construction yard it does one thing only -- rebuild
    # the MCV.  That is exactly the "yard destroyed -> new MCV now" behaviour,
    # and it is what the stock data intended with this trigger pair (three
    # GC-rebuild triggers + three Max=1 move-and-deploy MCV teams).
    #
    # This is only safe because the repair depots are AI-buildable (see
    # SECTION_KEY_EDITS): the MCV prerequisite needs one, so the team can
    # actually be filled.  With the depots still `AIBuildThis=no` -- retail's
    # state -- the team could NEVER fill and this weight would silence the
    # house permanently until DissolveUnfilledTeamDelay expired.  That trap
    # shipped once; `assert_mcv_recovery_fillable` now refuses to build the
    # combination.
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
        tokens[7], tokens[8], tokens[9] = "5000.000000", "5000.000000", "5000.000000"
        tokens[15], tokens[16], tokens[17] = "1", "1", "1"
        doc.lines[i] = key + "=" + ",".join(tokens) + eol
        recovered += 1

    # EXPANSION triggers: keep (construction yards) at 3, so the base keeps
    # spreading instead of sitting on the one yard the match starts with.
    #
    # An AI trigger can only compare the count of ONE object type
    # (`owned_count_holds`), so "yards + MCVs < 3" cannot be written directly.
    # The approximation: count the YARDS and require `< 3`, and cap the MCVs in
    # flight with the team's `Max=1` (above).  The sum therefore converges:
    # 1 yard -> build an MCV -> deploy -> 2 yards -> ... -> 3 yards, stop.
    # A destroyed yard drops the count and the chain restarts, which is what
    # keeps expansion alive for the whole match.
    #
    # Weight 5000 for the same reason as the recovery triggers: this has to
    # happen NOW, not "some draw soon".  The visible cost is that a house below
    # three yards stops forming attack teams while it expands (units already on
    # the map keep fighting); the window is bounded by how fast two MCVs can be
    # built and deployed, and the count self-clears at three.
    #
    # Comparison mask: 32 bytes, `compare` reads word(0) as the amount and
    # word(4) as the operator (0 `<`, 1 `<=`, 2 `==`, 3 `>=`, 4 `>`, 5 `!=`).
    # Retail's "owns zero" is amount 0 / op 2 -> `0000000002000000…`; this is
    # amount 3 / op 0 -> `0300000000000000…`.
    expansion_mask = "0300000000000000" + "0" * 48
    expansion_ids = {"GACNST": "ZAIEXP01-G", "NACNST": "ZAIEXP02-G",
                     "YACNST": "ZAIEXP03-G"}
    expansion_names = {"GACNST": "Allied MCV - Expand",
                       "NACNST": "Soviet MCV - Expand",
                       "YACNST": "Yuri MCV - Expand"}
    added = 0
    start, end = doc.bounds("AITriggerTypes")
    new_lines = []
    for i in range(start, end):
        line = doc.lines[i]
        if "=" not in line or line.lstrip().startswith(";"):
            continue
        tokens = line.split("=", 1)[1].rstrip("\r\n").split(",")
        if len(tokens) != 18 or "MCV" not in tokens[0].upper():
            continue
        yard = tokens[5].strip()
        if yard not in expansion_ids:
            continue
        tokens[0] = expansion_names[yard]
        tokens[6] = expansion_mask
        tokens[7], tokens[8], tokens[9] = "5000.000000", "5000.000000", "5000.000000"
        tokens[15], tokens[16], tokens[17] = "1", "1", "1"
        new_lines.append(expansion_ids[yard] + "=" + ",".join(tokens) + "\r\n")
        added += 1
    if added != 3:
        raise SystemExit(
            "expected one MCV trigger per construction yard (GACNST/NACNST/"
            "YACNST), matched %d" % added)
    # Append inside the section, before whatever follows it.
    start, end = doc.bounds("AITriggerTypes")
    for offset, line in enumerate(new_lines):
        doc.lines.insert(end + offset, line)
    doc.reindex()
    recovered += added

    boost = boost_air_and_aa(doc)
    attack = boost_attack_triggers(doc)
    open(os.path.join(out_dir, "aimd.ini"), "wb").write(doc.text().encode("latin-1"))
    return switched, recovered, preserved, boost, attack


def assert_mcv_recovery_fillable(rules_lines, aimd_lines):
    """A 5000-weight MCV trigger is only safe if the MCV can actually be built.

    ``PRIORITY_WEIGHT`` (5000) makes a trigger clear every other trigger out of
    the draw.  That is correct for "my construction yard is gone, rebuild the
    MCV now" -- but if the MCV team can never be filled, the house stops
    creating any team at all and goes silent (2.2's failure mode, in its other
    form).  The MCV prerequisite names a repair depot, so the depots must be
    AI-buildable for this to be sound:

        AMCV Prerequisite=GAWEAP,GADEPT    SMCV ...=NAWEAP,NADEPT
        PCV  Prerequisite=YAWEAP,YAGRND

    Retail ships all three depots with ``AIBuildThis=no``.
    """
    mcv_triggers = 0
    for line in aimd_lines:
        line = line.strip()
        if "=" not in line or line.startswith(";"):
            continue
        tokens = line.split("=", 1)[1].split(",")
        if len(tokens) != 18 or "MCV" not in tokens[0].upper():
            continue
        if any(float(tokens[n] or 0) >= 5000 for n in (7, 8, 9)):
            mcv_triggers += 1
    if not mcv_triggers:
        return

    unbuildable = [
        depot for depot in ("GADEPT", "NADEPT", "YADEPT")
        if (read_ini_value(rules_lines, depot, "AIBuildThis") or "").lower() != "yes"
    ]
    if unbuildable:
        raise SystemExit(
            "%d MCV trigger(s) carry the 5000 priority weight, which clears "
            "every other AI trigger for a yardless house, but %s still has "
            "AIBuildThis != yes -- the MCV team can never be filled, so the "
            "house would stop creating any team at all. Enable the depots "
            "(SECTION_KEY_EDITS) or drop the MCV weight."
            % (mcv_triggers, ", ".join(unbuildable)))


def assert_mcv_triggers_well_formed(aimd_lines):
    """The MCV trigger family must survive the INI reader intact.

    ``AITriggerTypeClass::Read_INI`` needs exactly 18 comma-separated fields and
    ``parse_ai_trigger_comparison`` needs a 64-character hex mask; anything else
    is dropped **silently** at load time, which would look exactly like "the AI
    never expands".  So verify the shape here, where a mistake is loud.
    """
    seen = set()
    mcv = []
    for line in aimd_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        tokens = value.split(",")
        if len(tokens) != 18 or "MCV" not in tokens[0].upper():
            continue
        if key in seen:
            raise SystemExit("duplicate AITriggerTypes id %s" % key)
        seen.add(key)
        mask = tokens[6]
        if len(mask) != 64 or any(c not in "0123456789abcdefABCDEF" for c in mask):
            raise SystemExit(
                "trigger %s has a malformed comparison mask %r (needs 64 hex "
                "chars; the reader drops the whole trigger otherwise)"
                % (key, mask))
        mcv.append((key, tokens[0].strip(), tokens[5].strip(), mask[:16]))
    if len(mcv) != 6:
        raise SystemExit(
            "expected 6 MCV triggers (3 recovery + 3 expansion), found %d: %s"
            % (len(mcv), ", ".join(entry[0] for entry in mcv)))
    return mcv


def assert_mcv_team_max(aimd_lines):
    """The three expansion MCVs must stay serialised and deploy-bound.

    ``at_max_teams`` blocks a team at ``teams >= Max`` per house, so ``Max=1``
    means one MCV on the road at a time.  Two at once drive to the same free
    patch and block each other's deploy (``MCV deploy blocked`` in the log) --
    the new-base congestion this build fixes.  Dropping the deploy script
    leaves the MCV parked forever.  Neither shows up at load time, so both are
    pinned here.
    """
    bodies = {}
    section = None
    for line in aimd_lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            bodies[section] = []
            continue
        if section is not None and stripped and not stripped.startswith(";"):
            bodies[section].append(stripped)

    def fields_of(tid):
        out = {}
        for entry in bodies.get(tid, []):
            if "=" in entry:
                key, value = entry.split("=", 1)
                out[key.strip().lower()] = value.strip()
        return out

    team_ids = [entry.split("=", 1)[1].strip()
                for entry in bodies.get("TeamTypes", []) if "=" in entry]
    mcv = [tid for tid in team_ids
           if re.search(r"(^|\W)MCV(\W|$)",
                        fields_of(tid).get("name", ""), re.I)]
    if len(mcv) != 3:
        raise SystemExit(
            "expected the 3 retail MCV teams (Allied/Soviet/Yuri), found %d: %s"
            % (len(mcv), ", ".join(sorted(mcv))))
    for tid in sorted(mcv):
        fields = fields_of(tid)
        if fields.get("max") != "1":
            raise SystemExit(
                "[%s] %s Max=%r, expected 1: two expansion MCVs in flight drive "
                "to the same free patch and block each other's deploy"
                % (tid, fields.get("name", "?"), fields.get("max")))
        if fields.get("script") != MCV_DEPLOY_SCRIPT:
            raise SystemExit(
                "[%s] %s Script=%r, expected the retail move-and-deploy %s; "
                "without it the expansion MCV never deploys"
                % (tid, fields.get("name", "?"), fields.get("script"),
                   MCV_DEPLOY_SCRIPT))
    return len(mcv)


def assert_attack_script(rules_lines, aimd_lines):
    """The charge script, its gather distance and the threat coefficient.

    Three silent regressions this refuses to ship:

    * **the coefficient** -- at retail ``-10`` the threat score reaches zero
      at ~39 cells and ``finish_score`` clamps every farther factory to 1
      point, while ``keep`` only replaces on "strictly greater": the winner is
      the oldest enemy factory again, not the nearest one.  The value is
      spelled out here instead of read back from :data:`RULES_EDITS`, so a
      wrong edit cannot validate itself;
    * **the gather distance** -- step 0 stages the team ``AISafeDistance``
      cells from the ENEMY base centre.  Retail 20 puts that point inside our
      own base whenever the two bases are close (three yards per house), so
      the column piles up at home; 8 then staged inside an enemy three-yard
      base, so 12 is the outside-the-wall compromise.  Action 54 (the
      expansion MCV's ``0=54,0``) reads ``AIFriendlyDistance=20`` instead, so
      the 53 distance no longer drags the deploy point in.  Pinned literally
      for the same reason as the coefficient;
    * **the script shape** -- dropping the opening ``53`` removes the only
      Move leg (and with it the passive scan that lets the column engage on
      the way in); adding or reordering a step changes how many quarries a
      team attacks before it dissolves.  Pinned to the exact shipped steps as
      a literal list, not derived from :data:`ATTACK_SCRIPT_BODY`, for the
      same reason: a five-step constant must fail the build, not pass it.

    See ``docs/ai-design.md`` section 3.2.
    """
    coefficient = read_ini_value(rules_lines, "General",
                                 "TargetDistanceCoefficientDefault")
    if coefficient != "-0.4":
        raise SystemExit(
            "[General] TargetDistanceCoefficientDefault=%r, expected '-0.4'. "
            "The threat score is base 100000 minus "
            "max(0, distance_leptons - range_cells) * |coefficient|: at -10 "
            "it clamps to 1 point beyond ~39 cells, so every distant factory "
            "ties and the oldest one wins (the far-side charge this mod is "
            "fixing). -0.4 keeps all candidates positive out to ~977 cells."
            % (coefficient,))

    gather = read_ini_value(rules_lines, "General", "AISafeDistance")
    if gather != "12":
        raise SystemExit(
            "[General] AISafeDistance=%r, expected '12'.  Step 0 of [%s] "
            "gathers at this distance from the ENEMY base centre; retail 20 "
            "lands inside our own base when the two bases are close, and 8 "
            "stages inside an enemy three-yard base.  12 is the outside-wall "
            "compromise." % (gather, ATTACK_SCRIPT))
    friendly = read_ini_value(rules_lines, "General", "AIFriendlyDistance")
    if friendly != "20":
        raise SystemExit(
            "[General] AIFriendlyDistance=%r, expected '20'.  Action 54 "
            "(the expansion MCV's 0=54,0) returns to OUR base centre; Ares "
            "falls back to AISafeDistance when this key is missing, which "
            "would plant the new yard 12 cells out instead of retail 20."
            % (friendly,))

    expected = ["0=53,0", "1=0,6", "2=49,0", "3=0,2", "4=0,1", "5=0,5"]
    actual = []
    section = None
    for line in aimd_lines:
        stripped = line.strip()
        header = re.match(r"^\[([^\]]+)\]", stripped)
        if header:
            section = header.group(1).strip()
            continue
        if section == ATTACK_SCRIPT and re.match(r"^\d+=", stripped):
            actual.append(stripped)
    if actual != expected:
        raise SystemExit(
            "[%s] is %r, expected exactly %r.  Step 0 must be 53,0: moving to "
            "the enemy base puts the team on Mission::Move, the only mission "
            "whose passive target scan runs for an aggressive, non-suicide AI "
            "team; the rest is the retail charge sequence."
            % (ATTACK_SCRIPT, actual, expected))


def assert_build_counts(rules_lines):
    """``AIBuildCounts`` must name existing sections with one entry per difficulty.

    Two silent failures this catches:

    * **a typo in the section name** -- the engine only reads the key inside a
      building section, so ``[GAPIL]`` looks fine and does nothing;
    * **a short list** -- ``ai_extra_copies`` indexes by
      ``HouseDifficulty::table_index()`` (Hard, Normal, Easy), and a missing
      index yields no copies, i.e. one node.  A two-entry list would therefore
      quietly give the easy computer the retail single building.
    """
    written = []
    section = None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            section = header.group(1).strip()
            continue
        m = re.match(r"^AIBuildCounts=(.*?)(\s*;.*)?$", line)
        if not m:
            continue
        values = [part.strip() for part in m.group(1).split(",")]
        if len(values) != 3 or any(not v.lstrip("-").isdigit() for v in values):
            raise SystemExit(
                "[%s] AIBuildCounts=%r must be three integers ordered "
                "hard,normal,easy; a short list silently degrades to one "
                "node per difficulty" % (section, m.group(1).strip()))
        written.append((section, [int(v) for v in values]))

    expected = set(BUILD_COUNTS)
    found = {name for name, _values in written}
    if found != expected:
        raise SystemExit(
            "AIBuildCounts sections mismatch: expected %r, wrote %r"
            % (sorted(expected), sorted(found)))
    for name, values in written:
        wanted = BUILD_COUNTS[name]
        wanted = wanted if isinstance(wanted, tuple) else (wanted,) * 3
        if tuple(values) != tuple(wanted):
            raise SystemExit("[%s] AIBuildCounts=%r, expected %r (hard,normal,easy)"
                             % (name, values, list(wanted)))
    return written


def assert_no_walls(rules_lines):
    """No wall may be plannable: ``AIPickWallDefensePercent`` must be all zero.

    ``choose_building`` draws ``RandomRanged(0, 99)`` for every defence node and
    only calls ``build_walls`` when ``draw < AIPickWallDefensePercent``.  Every
    wall segment costs a plan node from the defence budget and the ring around a
    ``ProtectWithWall=`` building blocks its own pathing, so non-zero values
    trade real defences -- and base growth -- for decoration.
    """
    raw = read_ini_value(rules_lines, "General", "AIPickWallDefensePercent")
    if raw is None:
        raise SystemExit("AIPickWallDefensePercent not found in [General]")
    values = [part.strip() for part in raw.split(",")]
    if any(not v.isdigit() or int(v) != 0 for v in values):
        raise SystemExit(
            "AIPickWallDefensePercent=%r: walls must stay disabled (all zeros). "
            "Every wall segment is a plan node taken from the defence budget and "
            "the ring blocks pathing; set non-zero only if walls are wanted "
            "back." % raw)
    return True


def assert_superweapon_autofire(rules_lines):
    """Every offensive superweapon must carry the auto-fire keys, correctly.

    Two silent failures this catches:

    * an unknown ``SW.AITargeting`` word -- the engine drops it without a word,
      which looks exactly like "the AI still does not fire";
    * a key that never made it into a section, e.g. because the section name
      changed or the insert landed in the wrong block.
    """
    for name, targeting in SUPERWEAPON_EDITS.items():
        wanted = dict(SUPERWEAPON_SHARED_KEYS)
        wanted.update(targeting)
        found = {}
        section = None
        for line in rules_lines:
            header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
            if header:
                section = header.group(1).strip()
                continue
            if section != name:
                continue
            m = re.match(r"^([^=;\s]+)=(.*?)(\s*;.*)?$", line.rstrip("\r\n"))
            if not m:
                continue
            key = m.group(1).strip()
            if key.lower() in {k.lower() for k in wanted}:
                found[key.lower()] = m.group(2).strip()
        for key, value in wanted.items():
            actual = found.get(key.lower())
            if actual is None:
                raise SystemExit("[%s] is missing %s=%s" % (name, key, value))
            if actual.lower() != value.lower():
                raise SystemExit("[%s] %s=%r, expected %r"
                                 % (name, key, actual, value))
        for targeting_key in ("sw.aitargeting", "sw.aitargeting.constraints",
                              "sw.aitargeting.preference"):
            raw = found.get(targeting_key, "")
            if not raw:
                continue
            words = [part.strip().lower() for part in raw.split(",") if part.strip()]
            unknown = [word for word in words if word not in ALLOWED_AITARGETING]
            if not words or unknown:
                raise SystemExit(
                    "[%s] %s=%r contains values this engine does not know; they "
                    "would be dropped silently. Known: %s"
                    % (name, targeting_key, raw,
                       ", ".join(sorted(ALLOWED_AITARGETING))))

    # Superweapons that already work (or are support type) must stay untouched.
    untouched = ("ForceShieldSpecial", "ParaDropSpecial",
                 "AmericanParaDropSpecial", "SpyPlaneSpecial",
                 "PsychicRevealSpecial", "ChronoWarpSpecial")
    # The two paradrop types are the one exception: their drop list is the shared
    # per-side [General] `*ParaDropInf` table, which now points at the nuke
    # trooper, so the computer would drop nuke troopers too.  SW.AllowAI=no is the
    # only way to keep the player's click working while the AI gets nothing.
    allowed = {
        "paradropspecial": {"sw.allowai=no"},
        "americanparadropspecial": {"sw.allowai=no"},
    }
    section = None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            section = header.group(1).strip()
            continue
        stripped = line.strip()
        if section in untouched and re.match(r"^SW\.", stripped, re.I):
            normalised = re.sub(r"\s+", "", stripped).lower()
            if normalised in allowed.get(section.lower(), set()):
                continue
            raise SystemExit(
                "[%s] must not carry %s -- it already behaves correctly and "
                "changing it would mask this fix" % (section, stripped))
    return len(SUPERWEAPON_EDITS)


def assert_superweapon_teams_intact(aimd_lines):
    """At least one team must still cast the Iron Curtain, and one the chrono.

    The AI has exactly one code path that fires these two superweapons: a team
    script action (55 = Iron Curtain, 56/57 = chronoshift).  Retail wires it up
    with `AITriggerTypes` condition 5/6 at weight 5000 -- "superweapon nearly
    ready" -- which draws a team that gathers at the enemy base and then casts.
    Rewriting those teams' scripts (as the 2.4 "one script for every team"
    change did) removes the whole mechanism in silence: the AI keeps building
    the silos and never casts anything, and nothing is logged.
    """
    bodies = {}
    section = None
    for line in aimd_lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            bodies.setdefault(section, [])
            continue
        if section is not None and stripped and not stripped.startswith(";"):
            bodies[section].append(stripped)

    def casts(actions):
        names = set()
        for name, body in bodies.items():
            for entry in body:
                if "=" in entry and entry.split("=", 1)[1].split(",")[0].strip() in actions:
                    names.add(name)
                    break
        return names

    iron = casts({"55"})
    chrono = casts({"56", "57"})
    if not iron or not chrono:
        raise SystemExit(
            "no team script casts a superweapon (%s); the AI's only path to the "
            "Iron Curtain and the Chrono Sphere is team-script action 55/56/57, "
            "so the build must keep the retail scripts that use them"
            % ", ".join(filter(None, ["IronCurtain" if not iron else "",
                                      "chrono" if not chrono else ""])))

    used = set()
    for line in aimd_lines:
        stripped = line.strip()
        if stripped.lower().startswith("script="):
            used.add(stripped.split("=", 1)[1].strip())
    if not (iron & used) or not (chrono & used):
        raise SystemExit(
            "the superweapon scripts exist but no TeamType uses them; the "
            "script rewrite must skip those teams (retail: 9 of them)")
    return len(iron & used), len(chrono & used)


def assert_aa_defenses_competitive(rules_lines):
    """Anti-air buildings must stay reachable, but on retail numbers.

    ``DefenseChoice::candidates`` only offers a building for a category whose value
    is above zero, and the category is picked before the building.  Retail's
    ``0/0/25`` shape therefore leaves the Allied and Soviet AA guns reachable only
    through the air category -- which rarely wins between computer houses, because
    the category is decided by the enemy's cost share per category (plus a 3000
    floor) against the AI's own coverage.

    That is engine behaviour, not a tuning knob: the earlier build faked it by
    giving the two guns ground values, which made the AI buy AA for ground threats.
    Since 3.11.6 the values are back to retail, and this check keeps them there
    while still asserting the one thing that has to hold -- ``AntiAirValue`` above
    zero, or the building could never be a candidate at all.
    """
    aa = ("NASAM", "NAFLAK", "YAGGUN")
    keys = ("AntiInfantryValue", "AntiArmorValue", "AntiAirValue")
    retail_ground = {"NASAM": (0, 0), "NAFLAK": (0, 0), "YAGGUN": (25, 10)}
    section = None
    found = {}
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            section = header.group(1).strip()
            continue
        if section not in aa:
            continue
        m = re.match(r"^(%s)=(.*?)(\s*;.*)?$" % "|".join(keys), line.rstrip("\r\n"))
        if m:
            try:
                found.setdefault(section, {})[m.group(1)] = int(m.group(2).strip())
            except ValueError:
                raise SystemExit("[%s] %s is not an integer" % (section, m.group(1)))
    for name in aa:
        values = found.get(name)
        if values is None:
            raise SystemExit("anti-air defence [%s] not found" % name)
        missing = [key for key in keys if key not in values]
        if missing:
            raise SystemExit("[%s] has no %s" % (name, ", ".join(missing)))
        if values["AntiAirValue"] <= 0:
            raise SystemExit(
                "[%s] AntiAirValue=%d; with zero the defence picker can never offer "
                "it for the air category, so the AI would never build it at all"
                % (name, values["AntiAirValue"]))
        want_inf, want_arm = retail_ground[name]
        if (values["AntiInfantryValue"], values["AntiArmorValue"]) != (want_inf, want_arm):
            raise SystemExit(
                "[%s] ground values are %d/%d, expected the retail %d/%d; giving an "
                "AA gun ground values makes the AI buy it for ground threats it "
                "cannot shoot"
                % (name, values["AntiInfantryValue"], values["AntiArmorValue"],
                   want_inf, want_arm))


def boost_air_and_aa(doc):
    """Give the AI an air force and a bigger AA share, without new team types.

    Two structural reasons the computer never looks like it owns either:

    * only 7 of retail's 132 task forces carry an aircraft, and every one of the
      11 team types that uses them is capped at ``Max=1`` -- a house may have
      exactly one air team alive at a time;
    * the triggers that form air and AA teams sit at ordinary weights (40-70),
      so they are drawn as rarely as any other attack team.

    So: raise the air team cap, add one aircraft per air task force, and scale
    the weights of the triggers that form air (x3) and AA (x2) teams.  Weights
    are per difficulty and are scaled together, so the difficulty mix is kept;
    a ceiling keeps them from swamping the 5000-weight takeover triggers.
    """
    team_air = set()
    team_aa = set()
    team_tf = {}
    for tid in doc.team_ids():
        fields = doc.values(tid)
        tf = fields.get("taskforce", ("", 0))[0].strip()
        team_tf[tid] = tf
        if not tf or tf not in doc.starts:
            continue
        units = {unit for _i, _idx, _count, unit, _rest, _eol in doc.members(tf)}
        if units & AIR_UNITS:
            team_air.add(tid)
        elif units & AA_UNITS:
            team_aa.add(tid)

    # Teams whose aircraft must land on a pad get the pad-safe cap instead.
    team_airport = set()
    for tid in team_air:
        tf = team_tf.get(tid)
        if tf in doc.starts:
            units = {unit for _i, _idx, _count, unit, _rest, _eol in doc.members(tf)}
            if units & AIRPORT_AIRCRAFT:
                team_airport.add(tid)

    # 1. A house may keep AIR_TEAM_MAX air teams alive at once.
    capped = 0
    for tid in sorted(team_air):
        fields = doc.values(tid)
        if "max" not in fields:
            continue
        current = fields["max"][0].strip()
        try:
            value = int(current)
        except ValueError:
            continue
        wanted = AIRPORT_TEAM_MAX if tid in team_airport else AIR_TEAM_MAX
        if value < wanted:
            doc.replace_value(fields["max"][1], "Max", str(wanted))
            capped += 1

    # 2. One more aircraft per air task force.
    grown = 0
    for tf in {team_tf[tid] for tid in team_air if team_tf.get(tid) in doc.starts}:
        for index, slot, count, unit, rest, eol in doc.members(tf):
            if unit not in AIR_UNITS or count >= AIR_UNIT_CAP:
                continue
            if unit in AIRPORT_AIRCRAFT:
                wanted = AIRPORT_TEAM_SIZE
            elif unit == "JUMPJET":
                wanted = AIR_INFANTRY_SIZE
            else:
                wanted = min(max(count + 1, AIR_UNIT_MIN) * AIR_SIZE_FACTOR,
                             AIR_UNIT_CAP)
            doc.lines[index] = "%d=%d,%s%s%s" % (slot, wanted, unit, rest, eol)
            grown += 1

    # 3. Weight the triggers that form those teams.
    air_triggers = aa_triggers = 0
    start, end = doc.bounds("AITriggerTypes")
    for i in range(start, end):
        line = doc.lines[i]
        if "=" not in line or line.lstrip().startswith(";"):
            continue
        key, value = line.split("=", 1)
        tokens = value.rstrip("\r\n").split(",")
        if len(tokens) != 18:
            continue
        team = tokens[1].strip()
        factor = AIR_WEIGHT_FACTOR if team in team_air else (
            AA_WEIGHT_FACTOR if team in team_aa else 0)
        if not factor:
            continue
        eol = line[len(line.rstrip("\r\n")):]
        boosted = []
        for slot in (7, 8, 9):
            try:
                weight = float(tokens[slot])
            except ValueError:
                boosted = []
                break
            boosted.append(min(weight * factor, WEIGHT_CAP))
        if not boosted:
            continue
        if team in team_air:
            # `AiTriggerTrackRecord::record` clamps the running weight to
            # `[weights[1], weights[2]]` and subtracts AITriggerFailureWeightDelta
            # (-50) every time a team dies without reaching script action 49.
            # Aircraft almost always die before that, so an air trigger sinks to
            # its floor within three losses and stops being drawn -- "the air
            # force never comes back".  Three equal slots make the clamp range a
            # single point, so the weight is constant however many teams are
            # lost.
            top = max(boosted)
            boosted = [top, top, top]
        for slot, weight in zip((7, 8, 9), boosted):
            tokens[slot] = "%.6f" % weight
        doc.lines[i] = key + "=" + ",".join(tokens) + eol
        if factor == AIR_WEIGHT_FACTOR:
            air_triggers += 1
        else:
            aa_triggers += 1

    return {"air_teams": len(team_air), "aa_teams": len(team_aa),
            "max_raised": capped, "aircraft_added": grown,
            "air_triggers": air_triggers, "aa_triggers": aa_triggers}


def boost_attack_triggers(doc):
    """Make the attack triggers reachable, and stop them sinking when they die.

    Three data problems press on the attack rate, and none of them is "the
    difficulty is too low":

    * **seven triggers can never be drawn** -- every difficulty bit is off
      (``d000``), so the team, its units and its name are dead data;
    * **46 condition-4 triggers decay to a floor of 10-60** -- condition 4 is
      "the enemy's money compares" with amount 0 / ``>=``, so it is always
      true; the weight is what limits the team, and
      ``AITriggerFailureWeightDelta`` (-50) walks it down to the floor every
      time a team dies before script action 49.  Against a player who kills the
      first wave, the AI's whole hand of attack triggers ends up at its floor:
      the longer the game runs, the softer it gets;
    * **no attack trigger is guaranteed to be drawable** -- each one waits on
      an owned building (condition 1) or on the enemy owning something
      (condition 0), so a house can be left with an empty draw.

    So: restore the seven to the difficulty their own name declares, raise the
    46 floors to their start weight (the ceiling and the +20 success feedback
    stay, so a trigger can still learn upwards), and append one weight-30
    ``condition=-1`` trigger per side as a floor under the whole table.

    Deliberately **not** done: decoupling the 42 counter/task conditions to
    ``-1`` (an AA team built with no enemy aircraft is wasted units), opening
    every difficulty bit (the 2.0-2.3 experiment 2.4 reverted), touching the
    5000 takeover triggers, or raising ordinary attack weights to 250.
    """
    dead_fixed = 0
    floors_matched = 0
    floors_raised = 0
    start, end = doc.bounds("AITriggerTypes")
    for i in range(start, end):
        line = doc.lines[i]
        if "=" not in line or line.lstrip().startswith(";"):
            continue
        key, value = line.split("=", 1)
        tokens = value.rstrip("\r\n").split(",")
        if len(tokens) != 18:
            continue
        eol = line[len(line.rstrip("\r\n")):]
        changed = False
        trigger_id = key.strip()

        bits = DEAD_TRIGGER_DIFFICULTY.get(trigger_id)
        if bits is not None:
            tokens[15], tokens[16], tokens[17] = bits[0], bits[1], bits[2]
            dead_fixed += 1
            changed = True

        if tokens[4].strip() == ATTACK_FLOOR_CONDITION:
            try:
                floor_weight = float(tokens[8])
                top_weight = float(tokens[9])
                start_weight = float(tokens[7])
            except ValueError:
                raise SystemExit(
                    "trigger %s has a non-numeric weight (%r/%r/%r)"
                    % (trigger_id, tokens[7], tokens[8], tokens[9]))
            if floor_weight < top_weight:
                floors_matched += 1
                if floor_weight != start_weight:
                    # `AiTriggerTrackRecord::record` clamps the running weight
                    # to [weights[1], weights[2]] and subtracts
                    # AITriggerFailureWeightDelta for each team that dies
                    # before script action 49.  With floor == start the clamp
                    # still allows a climb to the ceiling but can no longer
                    # push the weight below the retail starting weight.
                    tokens[8] = tokens[7]
                    floors_raised += 1
                changed = True

        if changed:
            doc.lines[i] = key + "=" + ",".join(tokens) + eol

    if dead_fixed != len(DEAD_TRIGGER_DIFFICULTY):
        raise SystemExit(
            "expected %d dead (d000) AITriggers, matched %d: the retail aimd "
            "does not match the ids in DEAD_TRIGGER_DIFFICULTY"
            % (len(DEAD_TRIGGER_DIFFICULTY), dead_fixed))
    if floors_matched != ATTACK_FLOOR_EXPECTED:
        raise SystemExit(
            "expected %d condition-4 attack triggers with a decaying floor, "
            "matched %d: the retail aimd changed shape"
            % (ATTACK_FLOOR_EXPECTED, floors_matched))

    # Append the always-eligible triggers before [Digest] -- the reader is
    # line-based, so the blank line before the existing ZAIEXP rows does not
    # end the section.
    start, end = doc.bounds("AITriggerTypes")
    for offset, spec in enumerate(ALWAYS_TRIGGER_SPEC):
        trigger_id, name, team, side = spec
        tokens = [name, team, "<all>", "1", "-1", "<none>",
                  ALWAYS_TRIGGER_MASK,
                  ALWAYS_TRIGGER_WEIGHTS[0], ALWAYS_TRIGGER_WEIGHTS[1],
                  ALWAYS_TRIGGER_WEIGHTS[2], "1", "0", side, "0", "<none>",
                  "1", "1", "1"]
        if len(tokens) != 18:
            raise SystemExit(
                "always-trigger %s would have %d tokens, not 18"
                % (trigger_id, len(tokens)))
        doc.lines.insert(end + offset,
                         "%s=%s\r\n" % (trigger_id, ",".join(tokens)))
    doc.reindex()

    return {"dead_fixed": dead_fixed, "floors_matched": floors_matched,
            "floors_raised": floors_raised, "added": len(ALWAYS_TRIGGER_SPEC)}


def assert_air_and_aa_boosted(aimd_lines):
    """The air / AA boost must actually be present in the built aimd."""
    text = "".join(aimd_lines)
    if not AIR_UNITS or not AA_UNITS:
        raise SystemExit("air/AA unit sets are empty")
    problems = []
    air_tfs = 0
    for line in aimd_lines:
        m = re.match(r"^(\d+)=(\d+),([A-Za-z][\w]*)", line)
        if not m or m.group(3) not in AIR_UNITS:
            continue
        unit, count = m.group(3), int(m.group(2))
        air_tfs += 1
        if unit in AIRPORT_AIRCRAFT:
            # These need a pad for every aircraft: 4 pads per airfield, and the
            # aircraft crashes when it cannot land, so never exceed one airfield's
            # worth in a single team.
            if count > 4:
                problems.append("%s team holds %d aircraft but an airfield has "
                                "only 4 pads" % (unit, count))
        elif unit == "JUMPJET":
            if not 4 <= count <= 8:
                problems.append("JUMPJET team holds %d men (want 4-8: big enough "
                                "to matter, small enough to fill)" % count)
        elif count < AIR_UNIT_MIN * AIR_SIZE_FACTOR:
            problems.append("air task force entry %s has only %s aircraft"
                            % (unit, count))
    if air_tfs < 5:
        problems.append("only %d air task-force entries" % air_tfs)

    # The flying infantry must be classified as air, not as AA: it is in both
    # sets, and a branch that checks AA first silently gives the Rocketeers
    # Max=1 and a decaying weight.
    flying_infantry = [line for line in aimd_lines
                       if re.match(r"^\d+=\d+,JUMPJET\b", line.strip())]
    if not flying_infantry:
        problems.append("no JUMPJET task-force entry; the Rocketeers are not "
                        "being treated as air units")
    elif any(int(re.match(r"^\d+=(\d+),JUMPJET\b", line.strip()).group(1))
             < AIR_UNIT_MIN * AIR_SIZE_FACTOR for line in flying_infantry):
        problems.append("a JUMPJET task-force entry is below %d men"
                        % (AIR_UNIT_MIN * AIR_SIZE_FACTOR))

    # The air triggers must stay pinned: `AiTriggerTrackRecord::record` clamps
    # the running weight to [weights[1], weights[2]] and takes
    # AITriggerFailureWeightDelta off it for every team that dies before
    # reaching script action 49, which is what aircraft do.  Unequal slots mean
    # the weight starts decaying again and the air force disappears for minutes
    # after every loss.
    sections, current = {}, None
    for line in aimd_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    team_tf = {}
    for line in sections.get("TeamTypes", []):
        entry = line.strip()
        if entry.lower().startswith("taskforce=") or not entry:
            continue
        m = re.match(r"^(\d+)=([^,\s]+)", entry)
        if m:
            team_tf.setdefault(m.group(1), m.group(2))
    team_taskforce = {}
    for name, body in sections.items():
        for line in body:
            if line.strip().lower().startswith("taskforce="):
                team_taskforce[name] = line.split("=", 1)[1].strip()
                break

    air_team_ids = set()
    for tid, tf in team_taskforce.items():
        units = {m.group(1) for m in
                 (re.match(r"^\d+=\d+,([A-Za-z][\w]*)", x.strip()) for x in sections.get(tf, []))
                 if m}
        if units & AIR_UNITS:
            air_team_ids.add(tid)

    unpinned = []
    for line in sections.get("AITriggerTypes", []):
        entry = line.strip()
        if "=" not in entry or entry.startswith(";"):
            continue
        key, value = entry.split("=", 1)
        tokens = value.split(",")
        if len(tokens) != 18 or tokens[1].strip() not in air_team_ids:
            continue
        try:
            weights = [float(tokens[slot]) for slot in (7, 8, 9)]
        except ValueError:
            continue
        if len(set(weights)) != 1:
            unpinned.append("%s=%s" % (key.strip(), "/".join("%.0f" % w for w in weights)))
    if unpinned:
        problems.append("air trigger weights are not pinned: " + ", ".join(unpinned[:3]))

    # Pad-safe team caps: AIRPORT_TEAM_SIZE x AIRPORT_TEAM_MAX aircraft per house
    # must fit in the pads the AI can build.
    for line in aimd_lines:
        m = re.match(r"^\d+=([0-9A-Fa-f]{8}-G)$", line.strip())
        if m:
            continue
    unpadded = []
    for name, body in sections.items():
        tf = next((l.split("=", 1)[1].strip() for l in body
                   if l.strip().lower().startswith("taskforce=")), None)
        if not tf:
            continue
        units = {m.group(1) for m in
                 (re.match(r"^\d+=\d+,([A-Za-z][\w]*)", x.strip())
                  for x in sections.get(tf, [])) if m}
        if not (units & AIRPORT_AIRCRAFT):
            continue
        for l in body:
            if l.strip().lower().startswith("max="):
                try:
                    cap = int(l.split("=", 1)[1].strip())
                except ValueError:
                    continue
                if cap > AIRPORT_TEAM_MAX:
                    unpadded.append("%s Max=%d" % (name, cap))
    if unpadded:
        problems.append("airport-bound teams may hold at most %d teams: %s"
                        % (AIRPORT_TEAM_MAX, ", ".join(unpadded[:3])))

    if problems:
        raise SystemExit("air/AA boost missing: " + "; ".join(problems[:4]))
    return air_tfs


#: 168 retail triggers + the 3 always-eligible ones.
EXPECTED_ATTACK_TRIGGER_COUNT = 171

#: The 46 condition-4 attack triggers whose retail weight floor sits below the
#: start weight, pinned by id (the 46 that used to decay).  Pinned literally
#: rather than derived from the transformation, so a different 46 -- a retail
#: change, or a bug that raises/skips the wrong rows -- fails the build.
ATTACK_FLOOR_TRIGGER_IDS = (
    "0CA6621C-G", "0CE26CAC-G", "0CE26B5C-G", "0CAD145C-G", "0CE2395C-G",
    "0D08461C-G", "0D0873DC-G", "0C8E2C3C-G", "0CAD25AC-G", "0D087D8C-G",
    "0CE44D0C-G", "0CA5945C-G", "0CAD2C3C-G", "0D535EDC-G", "0AD2BAEC-G",
    "0D2C448C-G", "0C8C56FC-G", "0D2C41EC-G", "0CA6AEDC-G", "0C8C51BC-G",
    "0C0D184C-G", "0ECCF68C-G", "0C8C430C-G", "0C87B99C-G", "0ECCF29C-G",
    "0ECCF14C-G", "0ECCB55C-G", "0ECCB40C-G", "0ECCB2BC-G", "0C87E5AC-G",
    "0612B11C-G", "06C551AC-G", "0612CD8C-G", "0ABC484C-G", "05FFB18C-G",
    "06002BFC-G", "07C04C7C-G", "05FC1A8C-G", "05FC50EC-G", "05FC3C9C-G",
    "05FC088C-G", "08B9154C-G", "08B911BC-G", "08B9213C-G", "08B9586C-G",
    "0612F46C-G",
)

#: Retail counter/task triggers that must keep their condition, object and
#: (where pinned) weight.  Turning any of these into `condition=-1` makes the
#: AI build counters with no threat on the map -- an AA team against no
#: aircraft, a refinery guard against no spy.  The four SPY rows also pin the
#: 5000 takeover weights: 5000 clears every other trigger out of that draw, so
#: it must stay exactly where retail put it.
COUNTER_TRIGGER_PINS = (
    # (id, display name, condition, object, weights or None)
    ("0CAD0DCC-G", "Allied Anti-Nuke 1", "0", "NAMISL", None),
    ("0CAD0C7C-G", "Allied Anti-Weather", "0", "GAWEAT", None),
    ("0CA2A04C-G", "Soviet Anti-Harrier Defense", "0", "ORCA", None),
    ("0C1246FC-G", "Allied Refinery Guard", "0", "SPY",
     ("5000.000000", "10.000000", "5000.000000")),
    ("0C1245AC-G", "Soviet Refinery Guard", "0", "SPY",
     ("5000.000000", "5000.000000", "5000.000000")),
    ("0A44F2CC-G", "Allied Dog Refinery Guards", "0", "SPY",
     ("5000.000000", "5000.000000", "5000.000000")),
    ("0A44F17C-G", "Soviet Dog Refinery Guards", "0", "SPY",
     ("5000.000000", "5000.000000", "5000.000000")),
)

#: Retail condition distribution plus the three new `-1` rows.  Any trigger
#: silently decoupled from 0/1 to -1 shows up here.
EXPECTED_TRIGGER_CONDITIONS = {-1: 3, 0: 50, 1: 52, 4: 53, 5: 2, 6: 3, 7: 8}


def assert_attack_triggers_boosted(aimd_lines):
    """The attack-trigger boost must be present, and only it must be present.

    Checks the shape the INI reader demands (18 tokens, 64-hex mask -- a
    malformed row is dropped **silently**, which looks like "the AI stopped
    attacking"), the three intended edits (7 dead rows revived, 46 floors at
    their start weight, 3 always-eligible rows), and the things that must NOT
    have moved: the condition histogram and the pinned counter rows.
    """
    sections, current = {}, None
    for line in aimd_lines:
        header = re.match(r"^\[([^\]]+)\]\s*(;.*)?$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    entries = []
    for line in sections.get("AITriggerTypes", []):
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        entries.append((key.strip(), value.split(",")))

    problems = []
    if len(entries) != EXPECTED_ATTACK_TRIGGER_COUNT:
        problems.append("%d AITriggers, expected %d"
                        % (len(entries), EXPECTED_ATTACK_TRIGGER_COUNT))
    if len({key for key, _tokens in entries}) != len(entries):
        problems.append("duplicate AITriggerTypes id")
    for key, tokens in entries:
        if len(tokens) != 18:
            problems.append("%s has %d tokens, not 18" % (key, len(tokens)))
            continue
        mask = tokens[6].strip()
        if len(mask) != 64 or any(c not in "0123456789abcdefABCDEF"
                                  for c in mask):
            problems.append("%s comparison mask is not 64 hex chars" % key)

    table = {key: tokens for key, tokens in entries}

    # 1. No trigger may ship with every difficulty bit off any more.
    d000 = [key for key, tokens in entries
            if len(tokens) == 18 and tokens[15:18] == ["0", "0", "0"]]
    if d000:
        problems.append("still d000: " + ", ".join(d000[:4]))
    for trigger_id, bits in DEAD_TRIGGER_DIFFICULTY.items():
        tokens = table.get(trigger_id)
        if tokens is None or len(tokens) != 18:
            problems.append("dead trigger %s is missing" % trigger_id)
            continue
        if "".join(tokens[15:18]) != bits:
            problems.append("%s difficulty %s, expected %s"
                            % (trigger_id, "".join(tokens[15:18]), bits))

    # 2. The 46 floors sit at the start weight; no condition-4 trigger may
    #    still decay below its start value.
    if len(ATTACK_FLOOR_TRIGGER_IDS) != ATTACK_FLOOR_EXPECTED:
        problems.append("%d pinned floor triggers, expected %d"
                        % (len(ATTACK_FLOOR_TRIGGER_IDS),
                           ATTACK_FLOOR_EXPECTED))
    for trigger_id in ATTACK_FLOOR_TRIGGER_IDS:
        tokens = table.get(trigger_id)
        if tokens is None or len(tokens) != 18:
            problems.append("floor trigger %s is missing" % trigger_id)
            continue
        try:
            condition = int(tokens[4])
            floor_weight = float(tokens[8])
            start_weight = float(tokens[7])
        except ValueError:
            problems.append("%s has non-numeric condition/weight" % trigger_id)
            continue
        if condition != 4:
            problems.append("%s condition %d, expected 4"
                            % (trigger_id, condition))
        if floor_weight != start_weight:
            problems.append("%s floor %s, expected the start weight %s"
                            % (trigger_id, tokens[8], tokens[7]))
    for key, tokens in entries:
        if len(tokens) != 18:
            continue
        try:
            condition = int(tokens[4])
            floor_weight = float(tokens[8])
            start_weight = float(tokens[7])
        except ValueError:
            continue
        if condition == 4 and floor_weight < start_weight:
            problems.append("%s still decays below its start weight" % key)

    # 3. The three always-eligible attack triggers.
    names = {}
    for key, tokens in entries:
        if len(tokens) == 18:
            names.setdefault(tokens[0].strip().lower(), []).append(key)
    for trigger_id, _name, team, side in ALWAYS_TRIGGER_SPEC:
        tokens = table.get(trigger_id)
        if tokens is None or len(tokens) != 18:
            problems.append("always-trigger %s is missing" % trigger_id)
            continue
        if tokens[0].strip() != _name:
            problems.append("%s name %r, expected %r"
                            % (trigger_id, tokens[0].strip(), _name))
        if len(names.get(_name.lower(), [])) != 1:
            problems.append("always-trigger name %r is not unique" % _name)
        if tokens[1].strip() != team:
            problems.append("%s team %r, expected %r"
                            % (trigger_id, tokens[1].strip(), team))
        if tokens[3].strip() != "1":
            problems.append("%s tech-level threshold %r, expected 1"
                            % (trigger_id, tokens[3].strip()))
        if tokens[4].strip() != "-1":
            problems.append("%s condition %r, expected -1"
                            % (trigger_id, tokens[4].strip()))
        if tokens[5].strip().lower() != "<none>":
            problems.append("%s object %r, expected <none>"
                            % (trigger_id, tokens[5].strip()))
        mask = tokens[6].strip()
        if len(mask) != 64 or any(c not in "0123456789abcdefABCDEF"
                                  for c in mask):
            problems.append("%s mask is not 64 hex chars" % trigger_id)
        if tuple(tokens[7:10]) != ALWAYS_TRIGGER_WEIGHTS:
            problems.append("%s weights %s, expected %s"
                            % (trigger_id, "/".join(tokens[7:10]),
                               "/".join(ALWAYS_TRIGGER_WEIGHTS)))
        if tokens[10].strip() != "1":
            problems.append("%s multiplayer %r, expected 1"
                            % (trigger_id, tokens[10].strip()))
        if tokens[12].strip() != side:
            problems.append("%s side %r, expected %s"
                            % (trigger_id, tokens[12].strip(), side))
        if tokens[14].strip().lower() != "<none>":
            problems.append("%s secondary team %r, expected <none>"
                            % (trigger_id, tokens[14].strip()))
        if "".join(tokens[15:18]) != "111":
            problems.append("%s difficulty %s, expected 111"
                            % (trigger_id, "".join(tokens[15:18])))
        team_fields = {}
        for entry in sections.get(team, []):
            entry = entry.strip()
            if "=" in entry:
                field, value = entry.split("=", 1)
                team_fields[field.strip().lower()] = value.strip()
        try:
            cap = int(team_fields.get("max", ""))
        except ValueError:
            cap = 0
        if cap < 2:
            problems.append(
                "%s reuses team %s with Max=%r; `at_max_teams` would keep the "
                "trigger from ever firing while the first team is alive"
                % (trigger_id, team, team_fields.get("max")))

    # 4. Nothing else moved: condition histogram and the counter rows.
    counts = {}
    for key, tokens in entries:
        if len(tokens) != 18:
            continue
        try:
            condition = int(tokens[4])
        except ValueError:
            problems.append("%s condition %r is not an integer"
                            % (key, tokens[4].strip()))
            continue
        counts[condition] = counts.get(condition, 0) + 1
    for condition, wanted in EXPECTED_TRIGGER_CONDITIONS.items():
        if counts.get(condition, 0) != wanted:
            problems.append("condition %d: %d triggers, expected %d"
                            % (condition, counts.get(condition, 0), wanted))
    for condition in counts:
        if condition not in EXPECTED_TRIGGER_CONDITIONS:
            problems.append("unexpected condition %d on %d triggers"
                            % (condition, counts[condition]))

    for trigger_id, _name, condition, obj, weights in COUNTER_TRIGGER_PINS:
        tokens = table.get(trigger_id)
        if tokens is None or len(tokens) != 18:
            problems.append("counter trigger %s is missing" % trigger_id)
            continue
        if tokens[0].strip() != _name:
            problems.append("%s name %r, expected %r"
                            % (trigger_id, tokens[0].strip(), _name))
        if tokens[4].strip() != condition:
            problems.append("%s condition %r, expected %s"
                            % (trigger_id, tokens[4].strip(), condition))
        if tokens[5].strip() != obj:
            problems.append("%s object %r, expected %s"
                            % (trigger_id, tokens[5].strip(), obj))
        if weights is not None and tuple(tokens[7:10]) != weights:
            problems.append("%s weights %s, expected %s"
                            % (trigger_id, "/".join(tokens[7:10]),
                               "/".join(weights)))

    if problems:
        raise SystemExit("attack trigger boost missing: "
                         + "; ".join(problems[:4]))
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", required=True,
                        help="folder containing retail rulesmd.ini / artmd.ini / aimd.ini")
    parser.add_argument("--out", required=True, help="output mod folder")
    parser.add_argument("--assembly-teams", action="store_true",
                        help="DIAGNOSTIC: keep retail's regroup-at-base team "
                             "script instead of the charge script (used to test "
                             "whether superweapons need a unit cluster)")
    parser.add_argument("--no-art", action="store_true",
                        help="do not copy artmd.ini (the mod does not change it)")
    args = parser.parse_args()

    for name in ("rulesmd.ini", "aimd.ini"):
        if not os.path.isfile(os.path.join(args.rules_dir, name)):
            raise SystemExit("missing %s in %s" % (name, args.rules_dir))

    os.makedirs(args.out, exist_ok=True)
    buildings = build_rules(args.rules_dir, args.out)
    switched, recovered, preserved, boost, attack = build_aimd(
        args.rules_dir, args.out, args.assembly_teams)

    # The mod's own CSF rows: `UIName=` is a label, so the two renamed delivery
    # superweapons need a table that holds their text.  A game in Ares form
    # appends `ares.csf` after `ra2md.csf` (startup log: "Loaded CSF string
    # table: ra2md.csf; supplements=[\"ares.csf\"]").
    import csf
    csf_path = os.path.join(args.out, "ares.csf")
    csf.write(csf_path, UI_LABELS)
    csf_labels = csf.read(csf_path)

    # Refuse to ship the "base builds, AI never moves" combination.
    with open(os.path.join(args.out, "rulesmd.ini"), "r",
              encoding="latin-1") as handle:
        rules_lines = handle.read().splitlines()
    with open(os.path.join(args.out, "aimd.ini"), "r",
              encoding="latin-1") as handle:
        aimd_lines = handle.read().splitlines()
    assert_defense_gate_consistent(rules_lines, aimd_lines)
    assert_mcv_recovery_fillable(rules_lines, aimd_lines)
    mcv_triggers = assert_mcv_triggers_well_formed(aimd_lines)
    assert_mcv_team_max(aimd_lines)
    assert_superweapon_teams_intact(aimd_lines)
    assert_attack_script(rules_lines, aimd_lines)
    assert_player_nuke_section(rules_lines)
    assert_nuke_gunship(rules_lines, aimd_lines)
    assert_nuke_gunship2(rules_lines, aimd_lines)
    assert_unit_delivery(rules_lines, aimd_lines)
    cluster_bombs = assert_nuke_gunship3(rules_lines, aimd_lines)
    assert_ui_labels(rules_lines, csf_labels)
    assert_air_and_aa_boosted(aimd_lines)
    assert_attack_triggers_boosted(aimd_lines)
    counts = assert_build_counts(rules_lines)
    assert_no_walls(rules_lines)
    aa_defences = assert_aa_defenses_competitive(rules_lines)
    superweapons = assert_superweapon_autofire(rules_lines)

    # The mod is additive against the RETAIL rules: anything else would silently
    # rewrite the game for every map.  Our own ZAI* sections are ours to change, so
    # the comparison is retail-vs-built, not against our previous version.
    import check_retail
    retail_rules = check_retail.parse_ini(os.path.join(args.rules_dir, "rulesmd.ini"))
    built_rules = check_retail.parse_ini(os.path.join(args.out, "rulesmd.ini"))
    retail_problems = check_retail.check(retail_rules, built_rules)
    if retail_problems:
        raise SystemExit(
            "retail guard: %d change(s) to the official rules are not registered in "
            "tools/check_retail.py:\n  %s"
            % (len(retail_problems), "\n  ".join(retail_problems[:10])))
    warhead_keys = assert_nuke_warhead_clone(retail_rules, built_rules)

    if not args.no_art:
        source = os.path.join(args.rules_dir, "artmd.ini")
        if not os.path.isfile(source):
            raise SystemExit("missing artmd.ini in %s" % args.rules_dir)
        art_out = os.path.join(args.out, "artmd.ini")
    shutil.copyfile(source, art_out)

    print("rules: AIBuildCounts on %d building types (empty table = retail rhythm)"
          % buildings)
    print("aimd : %d team types charging, %d kept their superweapon script, "
          "%d MCV triggers re-armed" % (switched, preserved, recovered))
    print("air  : %d air teams (Max<=%d, %d raised), +%d aircraft, "
          "%d air triggers weighted x%d"
          % (boost["air_teams"], AIR_TEAM_MAX, boost["max_raised"],
             boost["aircraft_added"], boost["air_triggers"], AIR_WEIGHT_FACTOR))
    print("aa   : %d AA teams, %d AA triggers weighted x%d"
          % (boost["aa_teams"], boost["aa_triggers"], AA_WEIGHT_FACTOR))
    print("atk  : %d dead triggers re-enabled on their named difficulty, "
          "%d condition-4 floors at the start weight (%d moved), "
          "%d always-eligible triggers at %s"
          % (attack["dead_fixed"], attack["floors_matched"],
             attack["floors_raised"], attack["added"],
             ALWAYS_TRIGGER_WEIGHTS[0]))
    print("nuke : [%s] is retail [NUKE]'s %d keys under another name, so the "
          "engine's NUKE block (screen flash + global relight) never runs"
          % (GUNSHIP_WARHEAD, warhead_keys))
    print("csf  : %d label(s) in %s (%s)"
          % (len(csf_labels), os.path.basename(csf_path),
             ", ".join(UI_LABELS[label] for label in sorted(UI_LABELS))))
    print("cluster: %d launches a trigger (all BurstDelays 0), each mother lands "
          "%s-%s cells off the aim point and splits into %d; %d nukes a shot; "
          "Sight=%s"
          % (GUNSHIP3_BURST, GUNSHIP3_SCATTER_MIN, GUNSHIP3_SCATTER_MAX,
             GUNSHIP3_CLUSTER, cluster_bombs, GUNSHIP3_SIGHT))
    print("output:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
