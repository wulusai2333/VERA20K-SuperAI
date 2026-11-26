# -*- coding: utf-8 -*-
"""Aimd transforms for the Mass Skirmish prototype.

This module is deliberately independent of ``build_mod.py``: the new branch
starts from the retail ``aimd.ini`` and only applies the transforms below.
"""
from __future__ import annotations

import re
from collections import OrderedDict

HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*(?:;.*)?$")
UNIT_LINE_RE = re.compile(r"^(\d+)\s*=\s*(\d+)\s*,\s*([^,\s;]+)")
TRIGGER_ID_RE = re.compile(r"^([^=\s]+)\s*=")

#: The only mixed TaskForce allowed to remain: a Blackhawk transport plus its
#: passengers.  Splitting it would remove the transport semantics.
TRANSPORT_TF = "0617909C-G"
TRANSPORT_TEAMS = {"0AD4D7BC-G", "06178A4C-G", "08DA125C-G", "0A6E513C-G"}

#: 46 = attack enemy building, high word 2 = nearest target.
#: The low word is the *dense* [BuildingTypes] index.  Retail has a duplicate
#: NAPSYA, so the dense indexes are GACNST=2, NACNST=25, YACNST=300.
DECAP_ACTIONS = (
    ("53", "0"),
    ("46", "131074"),  # 0x20000 | GACNST 2
    ("46", "131097"),  # 0x20000 | NACNST 25
    ("46", "131372"),  # 0x20000 | YACNST 300
    ("0", "6"),
    ("0", "2"),
    ("0", "1"),
    ("0", "5"),
    ("49", "0"),
)
DECAP_SCRIPT = "ZAIATK-CY"
DECAP_NAME = "Mass Skirmish Decap"

#: Retail national signature triggers: (id, owner, side, difficulty bits, weight).
NATION_TRIGGERS = (
    ("0CE44D0C-G", "British", "1", "100", 500.0),
    ("0CA5945C-G", "British", "1", "010", 500.0),
    ("0CAD2C3C-G", "British", "1", "001", 500.0),
    ("0D535EDC-G", "Germans", "1", "111", 500.0),
    ("0C8C645C-G", "Alliance", "1", "011", 1500.0),
    ("0C96F5AC-G", "Confederation", "2", "011", 500.0),
    ("0C96F45C-G", "Confederation", "2", "011", 500.0),
    ("0CB2CEDC-G", "Arabs", "2", "111", 500.0),
    ("0C91D45C-G", "Africans", "2", "011", 500.0),
    ("0CB29EDC-G", "Russians", "2", "011", 500.0),
)

ALWAYS_MASK = "0000000003000000" + "0" * 48
ALWAYS_WEIGHTS = ("40.000000", "40.000000", "40.000000")
ALWAYS_SPEC = (
    ("ZAIALW01-G", "ZAI Always Attack - Allied", "0CA0486C-G", "1"),
    ("ZAIALW02-G", "ZAI Always Attack - Soviet", "09B58D0C-G", "2"),
    ("ZAIALW03-G", "ZAI Always Attack - Yuri", "08B9108C-G", "3"),
    ("ZAIALW04-G", "ZAI Always Attack II - Allied", "0CA0486C-G", "1"),
    ("ZAIALW05-G", "ZAI Always Attack II - Soviet", "09B58D0C-G", "2"),
    ("ZAIALW06-G", "ZAI Always Attack II - Yuri", "08B9108C-G", "3"),
)

COUNTER_SPEC = (
    ("ZAICNT01-G", "ZAI Counter Air - Allied", "0CA0486C-G", "1", "ORCA"),
    ("ZAICNT02-G", "ZAI Counter Armor - Allied", "0CA0486C-G", "1", "APOC"),
    ("ZAICNT03-G", "ZAI Counter Air - Soviet", "09B58D0C-G", "2", "ORCA"),
    ("ZAICNT04-G", "ZAI Counter Armor - Soviet", "09B58D0C-G", "2", "APOC"),
    ("ZAICNT05-G", "ZAI Counter Air - Yuri", "08B9108C-G", "3", "ORCA"),
    ("ZAICNT06-G", "ZAI Counter Armor - Yuri", "08B9108C-G", "3", "APOC"),
)
COUNTER_MASK = "0600000003000000" + "0" * 48
COUNTER_WEIGHTS = ("100.000000", "20.000000", "120.000000")

#: Scripts that must keep their retail structure.
MCV_SCRIPT = "043F23CC-G"
SPY_UNITS = {"SPY", "SENGINEER", "ENGINEER"}
AIRPORT_AIRCRAFT = {"ORCA", "BEAG"}

#: Ground formations carry twice their retail unit count (the mixed TaskForce
#: split kept only the retail ground half, which reads as "a handful of units").
GROUND_SCALE = 2
GROUND_CAP = 20


def _eol(line: str) -> str:
    return line[len(line.rstrip("\r\n")):]


class Aimd:
    """Small section-aware editor for aimd.ini."""

    def __init__(self, text: str):
        self.lines = text.splitlines(keepends=True)
        self.starts: dict[str, int] = {}
        self.reindex()

    def reindex(self) -> None:
        self.starts = {}
        for i, line in enumerate(self.lines):
            m = HEADER_RE.match(line)
            if m:
                self.starts[m.group(1).strip()] = i

    def bounds(self, name: str) -> tuple[int, int]:
        if name not in self.starts:
            raise KeyError("section [%s] not found" % name)
        start = self.starts[name]
        end = len(self.lines)
        for index in self.starts.values():
            if start < index < end:
                end = index
        return start + 1, end

    def section(self, name: str) -> list[str]:
        s, e = self.bounds(name)
        return self.lines[s:e]

    def values(self, name: str) -> dict[str, str]:
        out = {}
        for line in self.section(name):
            if "=" in line and not line.lstrip().startswith(";"):
                key, value = line.split("=", 1)
                out[key.strip().lower()] = value.strip()
        return out

    def get(self, name: str, key: str, default=None):
        return self.values(name).get(key.lower(), default)

    def set_value(self, name: str, key: str, value: str) -> None:
        s, e = self.bounds(name)
        for i in range(s, e):
            if re.match(r"^\s*%s\s*=" % re.escape(key), self.lines[i], re.I):
                self.lines[i] = "%s=%s\r\n" % (key, value)
                return
        self.lines.insert(s, "%s=%s\r\n" % (key, value))

    def insert_after_key(self, name: str, key: str, new_key: str, value: str) -> None:
        s, e = self.bounds(name)
        for i in range(s, e):
            if re.match(r"^\s*%s\s*=" % re.escape(key), self.lines[i], re.I):
                self.lines.insert(i + 1, "%s=%s\r\n" % (new_key, value))
                self.reindex()
                return
        self.set_value(name, new_key, value)

    def list_ids(self, name: str) -> list[str]:
        out = []
        for line in self.section(name):
            m = re.match(r"^\d+\s*=\s*(\S+)", line)
            if m:
                out.append(m.group(1).strip())
        return out

    def set_list_ids(self, name: str, ids: list[str]) -> None:
        s, e = self.bounds(name)
        self.lines[s:e] = ["%d=%s\r\n" % (i, item) for i, item in enumerate(ids)]
        self.reindex()

    def add_list_id(self, name: str, item: str) -> None:
        ids = self.list_ids(name)
        if item in ids:
            return
        ids.append(item)
        self.set_list_ids(name, ids)

    def clone_section(self, source: str, new_name: str) -> None:
        s, e = self.bounds(source)
        body = ["[%s]\r\n" % new_name] + self.lines[s:e]
        self.insert_before_digest(body)

    def add_section(self, name: str, body: list[str]) -> None:
        if not body or not body[0].startswith("["):
            body = ["[%s]\r\n" % name] + body
        self.insert_before_digest(body)

    def insert_before_digest(self, body: list[str]) -> None:
        if "Digest" in self.starts:
            at = self.starts["Digest"]
        else:
            at = len(self.lines)
        self.lines[at:at] = body
        self.reindex()

    def taskforce_units(self, tf: str) -> list[tuple[int, str]]:
        out = []
        for line in self.section(tf):
            m = UNIT_LINE_RE.match(line)
            if m:
                out.append((int(m.group(2)), m.group(3).strip().upper()))
        return out

    def set_taskforce_units(self, tf: str, units: list[tuple[int, str]]) -> None:
        s, e = self.bounds(tf)
        numbered = [i for i in range(s, e) if re.match(r"^\d+\s*=", self.lines[i])]
        if not numbered:
            self.lines.insert(s, "0=0,<none>\r\n")
            self.reindex()
            return
        at = numbered[0]
        self.lines[at:numbered[-1] + 1] = [
            "%d=%d,%s\r\n" % (i, count, unit) for i, (count, unit) in enumerate(units)
        ]
        self.reindex()

    def script_actions(self, script: str) -> list[int]:
        actions = []
        for line in self.section(script):
            m = re.match(r"^\d+\s*=\s*(\d+)\s*,", line)
            if m:
                actions.append(int(m.group(1)))
        return actions

    def triggers(self) -> list[dict]:
        out = []
        s, e = self.bounds("AITriggerTypes")
        for i in range(s, e):
            line = self.lines[i]
            if "=" not in line or line.lstrip().startswith(";"):
                continue
            key, value = line.split("=", 1)
            eol = _eol(line)
            tokens = value.rstrip("\r\n").split(",")
            out.append({"idx": i, "key": key.strip(), "tokens": tokens, "eol": eol})
        return out

    def set_trigger_tokens(self, idx: int, tokens: list[str]) -> None:
        key = self.lines[idx].split("=", 1)[0]
        self.lines[idx] = key + "=" + ",".join(tokens) + "\r\n"

    def add_trigger_line(self, line: str) -> None:
        s, e = self.bounds("AITriggerTypes")
        self.lines.insert(e, line.rstrip("\r\n") + "\r\n")
        self.reindex()

    def text(self) -> str:
        return "".join(self.lines)


def classify_units(rules_lines: list[str]) -> dict[str, bool]:
    """True for air units, using the same signals as the engine data."""
    sections: dict[str, tuple[int, int]] = {}
    for i, line in enumerate(rules_lines):
        m = HEADER_RE.match(line)
        if m:
            sections[m.group(1).strip()] = (i + 1, len(rules_lines))
    starts = sorted((s, name) for name, (s, _) in sections.items())
    for pos, (start, name) in enumerate(starts):
        end = starts[pos + 1][0] - 1 if pos + 1 < len(starts) else len(rules_lines)
        sections[name] = (start, end)

    def block(name: str) -> list[str]:
        b = sections.get(name)
        return rules_lines[b[0]:b[1]] if b else []

    def registry(name: str) -> list[str]:
        out = []
        for line in block(name):
            m = re.match(r"^\d+\s*=\s*([^\s;]+)", line)
            if m:
                out.append(m.group(1).strip().upper())
        return out

    aircraft = set(registry("AircraftTypes"))
    all_units = set(aircraft) | set(registry("VehicleTypes")) | set(registry("InfantryTypes"))
    air: dict[str, bool] = {}
    for unit in all_units:
        text = "\n".join(block(unit)).lower()
        air[unit] = (
            unit in aircraft
            or "category=airpower" in text
            or re.search(r"^jumpjet\s*=\s*yes", text, re.M) is not None
            or "92612c46-f71f-11d1-ac9f-006008055bb5" in text
        )
    return air


def _is_air(unit: str, air: dict[str, bool]) -> bool:
    return air.get(unit, False)


def _team_units(doc: Aimd, team: str) -> list[tuple[int, str]]:
    tf = doc.get(team, "TaskForce")
    if not tf:
        return []
    return doc.taskforce_units(tf)


def split_mixed_taskforces(doc: Aimd, air: dict[str, bool], log: list[str]) -> int:
    split = 0
    for tf in list(doc.list_ids("TaskForces")):
        units = doc.taskforce_units(tf)
        if not units:
            continue
        flags = {_is_air(unit, air) for _, unit in units}
        if len(flags) < 2:
            continue
        if tf == TRANSPORT_TF:
            log.append("keep transport TF %s (mixed by design)" % tf)
            continue
        air_units = [(c, u) for c, u in units if _is_air(u, air)]
        ground_units = [(c, u) for c, u in units if not _is_air(u, air)]
        if not air_units or not ground_units:
            continue
        name = doc.get(tf, "Name", tf)
        doc.set_value(tf, "Name", name + " (Ground)")
        doc.set_taskforce_units(tf, ground_units)
        air_tf = "ZAI-AIR-" + tf
        doc.add_section(air_tf, [
            "[%s]\r\n" % air_tf,
            "Name=%s (Air)\r\n" % name,
            *["%d=%d,%s\r\n" % (i, c, u) for i, (c, u) in enumerate(air_units)],
            "Group=-1\r\n",
        ])
        doc.add_list_id("TaskForces", air_tf)
        for team in list(doc.list_ids("TeamTypes")):
            if doc.get(team, "TaskForce") != tf:
                continue
            air_team = "ZAI-AIR-" + team
            doc.clone_section(team, air_team)
            doc.set_value(air_team, "TaskForce", air_tf)
            doc.set_value(air_team, "Name", doc.get(team, "Name", team) + " (Air)")
            doc.add_list_id("TeamTypes", air_team)
            _duplicate_team_triggers(doc, team, air_team)
        split += 1
        log.append("split TF %s -> %s + %s" % (tf, tf, air_tf))
    return split


def _duplicate_team_triggers(doc: Aimd, team: str, new_team: str) -> None:
    n = 0
    base = re.sub(r"[^A-Za-z0-9]", "", team)
    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) < 18 or tokens[1].strip() != team:
            continue
        orig = list(tokens)
        new = list(tokens)
        new[1] = new_team
        # Do not inherit a secondary Team2: retail has seven known
        # IsBaseDefense mismatches there, and a cloned trigger would inherit
        # the same "condition never holds" bug.
        new[14] = "<none>"
        try:
            weights = [float(orig[i]) for i in (7, 8, 9)]
        except ValueError:
            weights = [0.0, 0.0, 0.0]
        if max(weights) >= 5000.0:
            pass
        else:
            half = [max(1.0, w / 2.0) for w in weights]
            orig[7:10] = ["%.6f" % w for w in half]
            new[7:10] = ["%.6f" % w for w in half]
        doc.set_trigger_tokens(trig["idx"], orig)
        n += 1
        new_id = "ZAI-AIR-%s-%02d" % (base, n)
        doc.add_trigger_line(new_id + "=" + ",".join(new))
    if n:
        # New IDs are scoped by the original team id, so multiple split teams
        # cannot collide.
        pass


def boost_ground_teams(doc: Aimd, air: dict[str, bool], log: list[str]) -> int:
    """Double the unit count of every pure-ground TaskForce.

    The mass-skirmish prototype splits retail's mixed TaskForces into a pure
    ground and a pure air half but kept the ground half at its retail size, so a
    ground wave looks like a handful of units.  Doubling restores the mass the
    mixed formation used to carry; MCV, spy/engineer, superweapon and transport
    formations keep their retail shape.
    """
    protected = set()
    for team in doc.list_ids("TeamTypes"):
        tf = doc.get(team, "TaskForce", "")
        script = doc.get(team, "Script", "")
        names = {unit for _, unit in _team_units(doc, team)}
        if script == MCV_SCRIPT or names & SPY_UNITS or tf == TRANSPORT_TF:
            protected.add(tf)
        elif script and any(a in (55, 56, 57) for a in doc.script_actions(script)):
            protected.add(tf)
    scaled = 0
    for tf in doc.list_ids("TaskForces"):
        if tf in protected:
            continue
        units = doc.taskforce_units(tf)
        if not units or any(_is_air(unit, air) for _, unit in units):
            continue
        changed = [(min(count * GROUND_SCALE, GROUND_CAP), unit) for count, unit in units]
        if changed == units:
            continue
        doc.set_value(tf, "Name", doc.get(tf, "Name", tf) + " (x2)")
        doc.set_taskforce_units(tf, changed)
        scaled += 1
    log.append("doubled %d ground task forces (scale=%d, cap=%d)"
               % (scaled, GROUND_SCALE, GROUND_CAP))
    return scaled


def boost_air_teams(doc: Aimd, air: dict[str, bool], log: list[str]) -> int:
    """4-plane and 8-plane airport teams, split by difficulty.

    A house has ``_AIR_PADS`` pads (two airfields x four).  Eight aircraft fill
    them exactly, so the heavy team is the *only* airport team a Hard house may
    field; the retail four-plane team keeps the Normal/Easy rows.  Both team
    shapes therefore exist in one match without ever exceeding the pads.
    Korea's four Black Eagles would add four more aircraft on Hard, so that team
    stays parked this round.
    """
    boosted = 0
    orca_team = None
    for team in doc.list_ids("TeamTypes"):
        units = _team_units(doc, team)
        if not units or any(not _is_air(unit, air) for _, unit in units):
            continue
        names = [unit for _, unit in units]
        airport = set(names) & AIRPORT_AIRCRAFT
        if airport:
            if "BEAG" in airport:
                # Parked this round: Hard's 8-ship ORCA team already fills the
                # pads, and 8 + 4 would overflow them.
                doc.set_value(team, "Max", "0")
                doc.set_taskforce_units(doc.get(team, "TaskForce"),
                                        [(4 if unit in AIRPORT_AIRCRAFT else count, unit)
                                         for count, unit in units])
            elif orca_team is None and all(unit == "ORCA" for unit in names):
                orca_team = team
                doc.set_value(team, "Max", "1")
                doc.set_taskforce_units(doc.get(team, "TaskForce"),
                                        [(4, unit) for count, unit in units])
            else:
                doc.set_value(team, "Max", "0")
                doc.set_taskforce_units(doc.get(team, "TaskForce"),
                                        [(4 if unit in AIRPORT_AIRCRAFT else count, unit)
                                         for count, unit in units])
        else:
            doc.set_value(team, "Max", "3")
            changed = []
            for count, unit in units:
                if unit == "ZEP":
                    count = 8
                elif unit == "JUMPJET":
                    count = 10
                elif unit in ("V3ROCKET", "DISK", "SCHP"):
                    count = max(count, 6)
                changed.append((count, unit))
            doc.set_taskforce_units(doc.get(team, "TaskForce"), changed)
        boosted += 1

    heavy = None
    if orca_team is not None:
        heavy = _add_heavy_air_team(doc, orca_team, log)
        # The retail four-plane team keeps the Normal/Easy rows; the heavy one
        # takes Hard, so a house never fields both.
        _set_team_difficulty(doc, orca_team, (1, 1, 0))
        if heavy:
            _set_team_difficulty(doc, heavy, (0, 0, 1))
    log.append("boosted %d pure-air teams (orca=%r heavy=%r)" % (boosted, orca_team, heavy))
    return boosted


#: Aircraft capacity of one airfield (`NumberOfDocks=4`).
AIRFIELD_PADS = 4


def _add_heavy_air_team(doc: Aimd, base_team: str, log: list[str]) -> str | None:
    """Clone ``base_team`` as an eight-aircraft team with its own TaskForce."""
    base_tf = doc.get(base_team, "TaskForce")
    if not base_tf:
        return None
    name = doc.get(base_team, "Name", base_team)
    heavy_tf = "ZAI-HVY-" + base_tf
    if heavy_tf in doc.list_ids("TaskForces"):
        return None
    doc.add_section(heavy_tf, [
        "[%s]\r\n" % heavy_tf,
        "Name=%s (Heavy)\r\n" % name,
        "0=8,ORCA\r\n",
        "Group=-1\r\n",
    ])
    doc.add_list_id("TaskForces", heavy_tf)
    heavy_team = "ZAI-HVY-" + base_team
    doc.clone_section(base_team, heavy_team)
    doc.set_value(heavy_team, "Name", name + " (Heavy)")
    doc.set_value(heavy_team, "TaskForce", heavy_tf)
    doc.set_value(heavy_team, "Max", "1")
    doc.add_list_id("TeamTypes", heavy_team)
    count = 0
    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) < 18 or tokens[1].strip() != base_team:
            continue
        new = list(tokens)
        new[1] = heavy_team
        new[14] = "<none>"
        doc.add_trigger_line("ZAIHVY%02d-G" % count + "=" + ",".join(new))
        count += 1
    log.append("added heavy air team %s (8xORCA, %d triggers)" % (heavy_team, count))
    return heavy_team


def _set_team_difficulty(doc: Aimd, team: str, difficulty: tuple[int, int, int]) -> int:
    """Set the Easy/Normal/Hard bits of every AITrigger that names ``team``."""
    changed = 0
    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) < 18 or tokens[1].strip() != team:
            continue
        tokens = list(tokens)
        tokens[15], tokens[16], tokens[17] = (str(bit) for bit in difficulty)
        doc.set_trigger_tokens(trig["idx"], tokens)
        changed += 1
    return changed



def assign_attack_scripts(doc: Aimd, air: dict[str, bool], log: list[str]) -> int:
    assigned = 0
    kept_air = []
    for team in doc.list_ids("TeamTypes"):
        tf = doc.get(team, "TaskForce", "")
        script = doc.get(team, "Script", "")
        units = _team_units(doc, team)
        names = {u for _, u in units}
        if script == MCV_SCRIPT:
            continue
        if any(a in (55, 56, 57) for a in doc.script_actions(script)) if script else False:
            continue
        if tf == TRANSPORT_TF or team in TRANSPORT_TEAMS:
            continue
        if names & SPY_UNITS:
            continue
        # Airport-bound aircraft keep their retail script.  The decap script
        # opens with action 53 ("gather outside the enemy base"), whose move
        # never completes for aircraft: they hover on the gather cell, the team
        # stays on the action, and every member keeps falling back to Enter
        # (return to dock) and is dragged out again.  Observed in a headless
        # 1v7 capture: four ORCA hovered from step 1377 to 4531 with no target
        # and no shot until an emergency All-to-Hunt released them.  Retail's
        # aircraft scripts attack the house's quarry directly, so keep them.
        if names & AIRPORT_AIRCRAFT:
            kept_air.append(team)
            continue
        doc.set_value(team, "Script", DECAP_SCRIPT)
        doc.set_value(team, "Aggressive", "yes")
        doc.set_value(team, "Suicide", "no")
        doc.set_value(team, "IsBaseDefense", "no")
        assigned += 1
    if kept_air:
        log.append("kept retail scripts on %d airport-aircraft teams: %s"
                   % (len(kept_air), ", ".join(sorted(kept_air))))
    log.append("assigned %s to %d teams" % (DECAP_SCRIPT, assigned))
    return assigned


def add_decap_script(doc: Aimd) -> None:
    if DECAP_SCRIPT in doc.list_ids("ScriptTypes"):
        return
    doc.add_list_id("ScriptTypes", DECAP_SCRIPT)
    body = ["[%s]\r\n" % DECAP_SCRIPT, "Name=%s\r\n" % DECAP_NAME]
    body += ["%d=%s,%s\r\n" % (i, a, b) for i, (a, b) in enumerate(DECAP_ACTIONS)]
    doc.add_section(DECAP_SCRIPT, body)


def add_mcv_expand_triggers(doc: Aimd, base_target: int) -> int:
    """Three `< base_target` MCV triggers, mirroring the retail rescue rows."""
    mask = "%02x00000000000000" % base_target + "0" * 48
    wanted = (
        ("ZAIEXP01-G", "Allied MCV - Expand", "043F29AC-G", "GACNST", "1"),
        ("ZAIEXP02-G", "Soviet MCV - Expand", "043F83EC-G", "NACNST", "2"),
        ("ZAIEXP03-G", "Yuri MCV - Expand", "043F89AC-G", "YACNST", "3"),
    )
    added = 0
    existing = {t["key"] for t in doc.triggers()}
    for tid, name, team, yard, side in wanted:
        if tid in existing:
            continue
        line = "%s=%s,%s,<all>,10,1,%s,%s,5000.000000,5000.000000,5000.000000,1,0,%s,0,<none>,1,1,1" % (
            tid, name, team, yard, mask, side,
        )
        doc.add_trigger_line(line)
        added += 1
    return added


def pin_nation_triggers(doc: Aimd) -> int:
    wanted = {row[0]: row for row in NATION_TRIGGERS}
    pinned = 0
    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) < 18:
            continue
        row = wanted.get(trig["key"])
        if row is None:
            continue
        _id, owner, side, bits, floor = row
        assert tokens[2].strip() == owner, "%s owner changed" % _id
        assert tokens[12].strip() == side, "%s side changed" % _id
        assert "".join(tokens[15:18]) == bits, "%s difficulty changed" % _id
        current = [float(tokens[i]) for i in (7, 8, 9)]
        target = max(current + [floor])
        tokens[7:10] = ["%.6f" % target] * 3
        doc.set_trigger_tokens(trig["idx"], tokens)
        pinned += 1
    if pinned != len(NATION_TRIGGERS):
        raise SystemExit("national triggers: expected %d, matched %d" % (len(NATION_TRIGGERS), pinned))
    return pinned


def pin_condition4_floors(doc: Aimd) -> int:
    n = 0
    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) >= 18 and tokens[4].strip() == "4":
            tokens[8] = tokens[7]
            doc.set_trigger_tokens(trig["idx"], tokens)
            n += 1
    return n


def add_always_triggers(doc: Aimd) -> int:
    existing = {t["key"] for t in doc.triggers()}
    added = 0
    for tid, name, team, side in ALWAYS_SPEC:
        if tid in existing:
            continue
        line = "%s=%s,%s,<all>,1,-1,<none>,%s,%s,1,0,%s,0,<none>,1,1,1" % (
            tid, name, team, ALWAYS_MASK, ",".join(ALWAYS_WEIGHTS), side,
        )
        doc.add_trigger_line(line)
        added += 1
    return added


def add_counter_triggers(doc: Aimd) -> int:
    existing = {t["key"] for t in doc.triggers()}
    added = 0
    for tid, name, team, side, obj in COUNTER_SPEC:
        if tid in existing:
            continue
        line = "%s=%s,%s,<all>,1,0,%s,%s,%s,1,0,%s,0,<none>,1,1,1" % (
            tid, name, team, obj, COUNTER_MASK, ",".join(COUNTER_WEIGHTS), side,
        )
        doc.add_trigger_line(line)
        added += 1
    return added


def _aircraft_per_difficulty(doc: Aimd) -> list[int]:
    """Airport aircraft a house can field at Easy/Normal/Hard."""
    totals = [0, 0, 0]
    for team in doc.list_ids("TeamTypes"):
        units = _team_units(doc, team)
        if not units:
            continue
        planes = sum(count for count, unit in units if unit in AIRPORT_AIRCRAFT)
        try:
            max_teams = int(doc.get(team, "Max", "0") or 0)
        except ValueError:
            max_teams = 0
        if planes <= 0 or max_teams <= 0:
            continue
        enabled = [False, False, False]
        for trig in doc.triggers():
            tokens = trig["tokens"]
            if len(tokens) < 18 or tokens[1].strip() != team:
                continue
            for index in range(3):
                enabled[index] = enabled[index] or tokens[15 + index].strip() not in ("0", "")
        for index in range(3):
            if enabled[index]:
                totals[index] += planes * max_teams
    return totals


def assert_aimd(doc: Aimd, air: dict[str, bool], base_target: int) -> dict:
    problems = []
    tf_ids = set(doc.list_ids("TaskForces"))
    team_ids = set(doc.list_ids("TeamTypes"))
    script_ids = set(doc.list_ids("ScriptTypes"))

    for team in team_ids:
        tf = doc.get(team, "TaskForce")
        script = doc.get(team, "Script")
        if tf not in tf_ids:
            problems.append("%s references missing TaskForce %r" % (team, tf))
        if script not in script_ids:
            problems.append("%s references missing Script %r" % (team, script))
        if tf in tf_ids and not doc.taskforce_units(tf):
            problems.append("%s has an empty TaskForce %s" % (team, tf))

    mixed = []
    for tf in tf_ids:
        units = doc.taskforce_units(tf)
        flags = {_is_air(u, air) for _, u in units}
        if len(flags) > 1:
            mixed.append(tf)
    if mixed != [TRANSPORT_TF]:
        problems.append("mixed TaskForces: %r (only %s is allowed)" % (sorted(mixed), TRANSPORT_TF))

    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) < 18:
            problems.append("%s has %d tokens" % (trig["key"], len(tokens)))
            continue
        if tokens[1].strip() not in team_ids:
            problems.append("%s references missing Team1 %r" % (trig["key"], tokens[1]))
        if tokens[14].strip() not in ("<none>", "") and tokens[14].strip() not in team_ids:
            problems.append("%s references missing Team2 %r" % (trig["key"], tokens[14]))
        if trig["key"].startswith("ZAI-AIR-") and tokens[14].strip() != "<none>":
            problems.append("%s clone must not inherit Team2" % trig["key"])

    if DECAP_SCRIPT not in script_ids:
        problems.append("missing %s" % DECAP_SCRIPT)
    else:
        actions = doc.script_actions(DECAP_SCRIPT)
        if actions != [int(a) for a, _ in DECAP_ACTIONS]:
            problems.append("%s actions %r" % (DECAP_SCRIPT, actions))

    mcv = [t for t in team_ids if doc.get(t, "Script") == MCV_SCRIPT]
    if len(mcv) != 3:
        problems.append("expected 3 MCV teams, found %d" % len(mcv))
    for team in mcv:
        if doc.get(team, "Max") != "1":
            problems.append("%s MCV Max != 1" % team)

    sw = [t for t in team_ids if any(a in (55, 56, 57) for a in doc.script_actions(doc.get(t, "Script", "")))]
    if len(sw) < 9:
        problems.append("expected >=9 superweapon teams, found %d" % len(sw))

    # Airport aircraft must not run the decap script: its opening action 53
    # ("gather outside the enemy base") never completes for aircraft, so the
    # team hovers at the gather cell and never reaches the attack actions.
    # Headless 1v7 capture: four ORCA hovered from step 1377 to 4531 with no
    # target and no shot.  Retail aircraft scripts attack the house's quarry.
    air_decap = []
    for team in team_ids:
        names = {unit for _, unit in _team_units(doc, team)}
        if names & AIRPORT_AIRCRAFT and doc.get(team, "Script") == DECAP_SCRIPT:
            air_decap.append(team)
    if air_decap:
        problems.append("airport aircraft must keep retail scripts: %s"
                        % ", ".join(sorted(air_decap)[:5]))

    # Pads are a hard limit: an AirportBound aircraft with no pad crashes.
    # One house builds one airfield type (`GAAIRC` or `AMRADR`, both 4 pads) and
    # the AI planning count decides how many of it.
    if _AIR_PADS <= 0:
        problems.append("air pads not initialised")
    else:
        totals = _aircraft_per_difficulty(doc)
        for index, total in enumerate(totals):
            if total > _AIR_PADS:
                problems.append(
                    "difficulty %d fields %d airport aircraft over %d pads"
                    % (index, total, _AIR_PADS))
        shapes = sorted({
            sum(count for count, unit in _team_units(doc, team)
                if unit in AIRPORT_AIRCRAFT)
            for team in team_ids
            if doc.get(team, "Max") == "1"
            and {unit for _, unit in _team_units(doc, team)} & AIRPORT_AIRCRAFT
        })
        if 4 not in shapes or 8 not in shapes:
            problems.append("expected 4- and 8-aircraft teams at Max=1, got %r" % shapes)


    normal = 0
    for trig in doc.triggers():
        tokens = trig["tokens"]
        if len(tokens) >= 18 and tokens[4].strip() == "4" and tokens[8] != tokens[7]:
            problems.append("%s condition-4 floor not pinned" % trig["key"])
        if len(tokens) >= 18 and tokens[7] == "5000.000000":
            normal += 1

    if problems:
        raise SystemExit("aimd assertions failed:\n  " + "\n  ".join(problems[:20]))
    return {
        "taskforces": len(tf_ids),
        "teamtypes": len(team_ids),
        "scripttypes": len(script_ids),
        "aitriggers": len(doc.triggers()),
        "mixed_taskforces": mixed,
        "mcv_teams": len(mcv),
        "superweapon_teams": len(sw),
        "decap_actions": [int(a) for a, _ in DECAP_ACTIONS],
        "base_target": base_target,
        "5000_triggers": normal,
    }


def build_aimd(retail_text: str, base_target: int) -> tuple[str, dict, list[str]]:
    doc = Aimd(retail_text)
    log: list[str] = []
    # rulesmd is needed for the air/ground split; caller passes it via a
    # module-level hook to keep this function's signature small.
    air = _RULES_AIR
    if not air:
        raise SystemExit("rules air classification not initialised")
    add_decap_script(doc)
    split = split_mixed_taskforces(doc, air, log)
    ground = boost_ground_teams(doc, air, log)
    boost_air_teams(doc, air, log)
    assigned = assign_attack_scripts(doc, air, log)
    mcv_added = add_mcv_expand_triggers(doc, base_target)
    pinned = pin_nation_triggers(doc)
    floors = pin_condition4_floors(doc)
    always = add_always_triggers(doc)
    counters = add_counter_triggers(doc)
    log.append("split=%d ground=%d assigned=%d mcv=%d nation=%d cond4=%d always=%d counter=%d" % (
        split, ground, assigned, mcv_added, pinned, floors, always, counters))
    stats = assert_aimd(doc, air, base_target)
    stats["ground_scaled"] = ground
    stats["aircraft_per_difficulty"] = _aircraft_per_difficulty(doc)
    return doc.text(), stats, log


# Set by the rules builder before build_aimd() is called.  Keeping it a module
# global avoids threading a large rules parser through every helper.
_RULES_AIR: dict[str, bool] = {}

#: Airport aircraft a house can hold (airfields x 4 pads); set by the rules
#: builder, which knows `AIBuildCounts`.
_AIR_PADS = 0


def set_air_pads(pads: int) -> None:
    global _AIR_PADS
    _AIR_PADS = pads


def set_rules_air(air: dict[str, bool]) -> None:
    global _RULES_AIR
    _RULES_AIR = air
