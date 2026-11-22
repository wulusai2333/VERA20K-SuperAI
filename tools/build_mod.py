# -*- coding: utf-8 -*-
"""Build the SuperAI mod from a stock Yuri's Revenge rules folder.

The mod is a full replacement of ``rulesmd.ini`` / ``artmd.ini`` / ``aimd.ini``.
This script starts from the retail files, applies a fixed list of edits and
writes them next to the ``mod.ini`` that ships in this repository.

    python tools/build_mod.py --rules-dir "F:/Games/red2" --out mod/SuperAI

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
    "DissolveUnfilledTeamDelay": ("5000", "900"),
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
}

#: Comment written beside a rewritten key, replacing the retail one.  Retail's
#: note on these lines reads "taken out to remove useless building - DB",
#: which is exactly the trap this mod is fixing: leaving it in place makes the
#: next reader think the value is still ``no``.
SECTION_KEY_COMMENTS = {
    "AIBuildThis": ";SuperAI: enabled so the AI can build its MCV (see docs/ai-tuning-playbook.md)",
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
#: ``SW.AITargeting`` values are the vocabulary the binary accepts
#: (``offensive_cell_clear``, ``defensive_cell_clear``, ``offensive_cell_set``,
#: ``defensive_cell_set``, ``attacked``, ``lightningstorm_inactive``,
#: ``dominator_inactive``).  An unknown word is ignored silently, which is why
#: ``assert_superweapon_autofire`` checks every value against that list.
SUPERWEAPON_EDITS = {
    # Area-damage weapons: hit a clear cell inside the enemy base.
    "NukeSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "LightningStormSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "PsychicDominatorSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "GeneticConverterSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    "ChronoSphereSpecial": {"SW.AITargeting": "offensive_cell_clear"},
    # Iron Curtain is dropped on the house's OWN units, so it wants the
    # defensive target selector, not the offensive one.
    "IronCurtainSpecial": {"SW.AITargeting": "defensive_cell_clear"},
}

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


def build_aimd(source_dir, out_dir):
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
    """
    text = open(os.path.join(source_dir, "aimd.ini"), "rb").read().decode("latin-1")
    doc = Aimd(text)

    team_ids = doc.team_ids()

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

    # Every team charges except the three MCV teams, which deploy expansions.
    switched = 0
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
        if "script" in fields:
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

    open(os.path.join(out_dir, "aimd.ini"), "wb").write(doc.text().encode("latin-1"))
    return switched, recovered


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
        word = found.get("sw.aitargeting", "")
        if word.lower() not in ALLOWED_AITARGETING:
            raise SystemExit(
                "[%s] SW.AITargeting=%r is not a value this engine knows; it "
                "would be dropped silently. Known: %s"
                % (name, word, ", ".join(sorted(ALLOWED_AITARGETING))))

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", required=True,
                        help="folder containing retail rulesmd.ini / artmd.ini / aimd.ini")
    parser.add_argument("--out", required=True, help="output mod folder")
    parser.add_argument("--no-art", action="store_true",
                        help="do not copy artmd.ini (the mod does not change it)")
    args = parser.parse_args()

    for name in ("rulesmd.ini", "aimd.ini"):
        if not os.path.isfile(os.path.join(args.rules_dir, name)):
            raise SystemExit("missing %s in %s" % (name, args.rules_dir))

    os.makedirs(args.out, exist_ok=True)
    buildings = build_rules(args.rules_dir, args.out)
    switched, recovered = build_aimd(args.rules_dir, args.out)

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
    counts = assert_build_counts(rules_lines)
    assert_no_walls(rules_lines)
    superweapons = assert_superweapon_autofire(rules_lines)

    if not args.no_art:
        source = os.path.join(args.rules_dir, "artmd.ini")
        if not os.path.isfile(source):
            raise SystemExit("missing artmd.ini in %s" % args.rules_dir)
        shutil.copyfile(source, os.path.join(args.out, "artmd.ini"))

    print("rules: AIBuildCounts on %d building types (empty table = retail rhythm)"
          % buildings)
    print("aimd : %d team types charging, %d MCV triggers re-armed"
          % (switched, recovered))
    print("output:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
