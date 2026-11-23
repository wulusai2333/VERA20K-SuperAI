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
import os
import re
import shutil

# --------------------------------------------------------------- rules edits
# key: (retail value, mod value)
#
# Kept deliberately small.  The design is "vanilla three-difficulty AI + two
# mechanisms", so everything that is not needed by one of those mechanisms
# stays at its retail value:
#
#   1. ATTACK HARD  -- teams never regroup, every team charges, no team stays
#      home (the team-type rewrite in build_aimd), map All-to-Hunt clears the
#      base.  Needs only `TeamDelays` (retail 2000/2500/3500 = 33-58 s is far
#      too slow to "send units out as soon as they exist").
#   2. REBUILD ON LOSS -- a lost building's plan node is replanned immediately.
#      `AIRestrictReplaceTime=0` is the whole mechanism: 0 means "never
#      restrict", so an ordinary building is replannable the frame it dies,
#      the same way power plants and armed buildings already are.
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
    "GADEPT": {"AIBuildThis": "yes"},
    "NADEPT": {"AIBuildThis": "yes"},
    "YADEPT": {"AIBuildThis": "yes"},
    # --- anti-air defences -------------------------------------------------
    # The defence picker chooses a CATEGORY first (air / armor / infantry) and
    # only then picks among that category's candidates; a building is a
    # candidate for a category when its value for that category is above zero
    # (`DefenseChoice::candidates`).  Retail gives the Allied and Soviet AA
    # buildings zero armor and zero infantry value, so they exist ONLY in the
    # air category -- which wins only when the enemy's air share beats the
    # house's own air coverage.  Between computer houses there is almost no air
    # force, so that category almost never wins and the AA guns are almost never
    # picked.  Yuri's Gattling Cannon has 25/10/25 and is therefore a candidate
    # in all three categories, which is why it is the AA building that actually
    # shows up (log counts: YAGGUN 62, NASAM 41, NAFLAK 29).
    #
    # Giving the two guns the same shape as Yuri's makes them compete in every
    # draw.  The number of defence nodes is untouched (*BaseDefenseCounts stays
    # at retail 25/20/6), so the build intensity the user asked to keep does not
    # change -- only which building gets chosen inside those nodes.
    "NASAM": {"AntiInfantryValue": "25", "AntiArmorValue": "10"},
    "NAFLAK": {"AntiInfantryValue": "25", "AntiArmorValue": "10"},
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
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
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
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
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
            header = re.match(r"^\[([^\]]+)\]\s*$", line)
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

    # Ares AIBuildCounts: planned copies of the production buildings that must
    # exist in numbers, keyed by difficulty (hard, normal, easy).
    out = []
    inserted = set()
    for line in lines:
        out.append(line)
        m = re.match(r"^\[([^\]]+)\]\s*$", line)
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

    * ``Script`` becomes :data:`ATTACK_SCRIPT` (skip "regroup at base"), except
      the three MCV teams, which keep the retail move-and-deploy script;
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
            # Two MCVs may be in flight at once, so the expansion triggers can
            # put up a second base while the first is still driving to its
            # spot.  `at_max_teams` blocks at `teams >= Max` per house, so the
            # retail 1 meant one MCV at a time, ever.
            if "max" in fields:
                doc.replace_value(fields["max"][1], "Max", "2")
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
    # flight with the team's `Max=2` (above).  The sum therefore converges:
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
    open(os.path.join(out_dir, "aimd.ini"), "wb").write(doc.text().encode("latin-1"))
    return switched, recovered, preserved, boost


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
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
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
            header = re.match(r"^\[([^\]]+)\]\s*$", line)
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
    section = None
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            section = header.group(1).strip()
            continue
        if section in untouched and re.match(r"^SW\.", line.strip()):
            raise SystemExit(
                "[%s] must not carry %s -- it already behaves correctly and "
                "changing it would mask this fix" % (section, line.strip()))
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
    """Every anti-air defence must be a candidate in all three categories.

    ``DefenseChoice::candidates`` only offers a building for a category when its
    value for that category is above zero, and the category is chosen before the
    building.  Retail's ``0/0/25`` shape therefore leaves the Allied and Soviet
    AA guns reachable only through the air category -- which almost never wins
    between computer houses.  The build would look perfectly healthy while the
    AI quietly stopped building AA, so check the shape explicitly.
    """
    aa = ("NASAM", "NAFLAK", "YAGGUN")
    keys = ("AntiInfantryValue", "AntiArmorValue", "AntiAirValue")
    section = None
    found = {}
    for line in rules_lines:
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
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
        zero = [key for key in keys if values[key] <= 0]
        if zero:
            raise SystemExit(
                "[%s] has %s at zero; the defence picker only offers a building "
                "for a category whose value is above zero, so this AA gun would "
                "be reachable only through the categories it scores in"
                % (name, ", ".join(zero)))
    return found


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
        if value < AIR_TEAM_MAX:
            doc.replace_value(fields["max"][1], "Max", str(AIR_TEAM_MAX))
            capped += 1

    # 2. One more aircraft per air task force.
    grown = 0
    for tf in {team_tf[tid] for tid in team_air if team_tf.get(tid) in doc.starts}:
        for index, slot, count, unit, rest, eol in doc.members(tf):
            if unit not in AIR_UNITS or count >= AIR_UNIT_CAP:
                continue
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


def assert_air_and_aa_boosted(aimd_lines):
    """The air / AA boost must actually be present in the built aimd."""
    text = "".join(aimd_lines)
    if not AIR_UNITS or not AA_UNITS:
        raise SystemExit("air/AA unit sets are empty")
    problems = []
    air_tfs = 0
    for line in aimd_lines:
        m = re.match(r"^(\d+)=(\d+),([A-Za-z][\w]*)", line)
        if m and m.group(3) in AIR_UNITS:
            air_tfs += 1
            if int(m.group(2)) < AIR_UNIT_MIN * AIR_SIZE_FACTOR:
                problems.append("air task force entry %s has only %s aircraft"
                                % (m.group(3), m.group(2)))
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
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
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

    if problems:
        raise SystemExit("air/AA boost missing: " + "; ".join(problems[:4]))
    return air_tfs


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
    switched, recovered, preserved, boost = build_aimd(
        args.rules_dir, args.out, args.assembly_teams)

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
    assert_superweapon_teams_intact(aimd_lines)
    assert_air_and_aa_boosted(aimd_lines)
    counts = assert_build_counts(rules_lines)
    assert_no_walls(rules_lines)
    aa_defences = assert_aa_defenses_competitive(rules_lines)
    superweapons = assert_superweapon_autofire(rules_lines)

    if not args.no_art:
        source = os.path.join(args.rules_dir, "artmd.ini")
        if not os.path.isfile(source):
            raise SystemExit("missing artmd.ini in %s" % args.rules_dir)
        shutil.copyfile(source, os.path.join(args.out, "artmd.ini"))

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
    print("output:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
