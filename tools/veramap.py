# -*- coding: utf-8 -*-
"""Low-level helpers for Yuri's Revenge / VERA20k map and rules files.

A .yrm/.mmx/.map file is a plain INI.  The only binary payload is
``[IsoMapPack5]``: every isometric cell is an 11-byte record, compressed with
LZO1X in 8 KiB chunks and stored as base64 lines.

Everything else here is text manipulation that keeps CRLF line endings intact.
"""
from __future__ import annotations

import base64
import re
import struct

import lzokay

BLOCK = 8192
RECORD_SIZE = 11
BASE64_LINE = 120

#: Sections that hold map-authored objects.  Removing them leaves pure terrain.
OBJECT_SECTIONS = (
    "OverlayPack",
    "OverlayDataPack",
    "Terrain",
    "Structures",
    "Units",
    "Infantry",
    "Aircraft",
    "Smudge",
    "CellTags",
    "Preview",
    "PreviewPack",
)


# --------------------------------------------------------------------- text
def read_text(path: str) -> str:
    return open(path, "rb").read().decode("latin-1")


def write_text(path: str, text: str) -> None:
    open(path, "wb").write(text.encode("latin-1"))


def section_span(text: str, name: str):
    """Return (header_start, section_end) for ``[name]`` or None."""
    m = re.search(r"(?mi)^\[%s\][ \t]*\r?\n" % re.escape(name), text)
    if not m:
        return None
    nxt = re.search(r"(?m)^\[[^\]]+\]", text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return m.start(), end


def has_section(text: str, name: str) -> bool:
    return section_span(text, name) is not None


def section_body(text: str, name: str) -> str:
    span = section_span(text, name)
    if not span:
        raise KeyError("missing section [%s]" % name)
    start, end = span
    header_end = text.find("\n", start) + 1
    return text[header_end:end]


def drop_sections(text: str, names, separator: str = "") -> str:
    """Remove whole sections.

    With ``separator=""`` the section body is cut out and the surrounding
    blank lines stay.  Passing a line ending also swallows the break before
    the header and writes ``separator`` there, which keeps CRLF files tidy.
    """
    for name in names:
        while True:
            span = section_span(text, name)
            if not span:
                break
            start, end = span
            if separator:
                if text[start - 2:start] == "\r\n":
                    start -= 2
                elif text[start - 1:start] == "\n":
                    start -= 1
            text = text[:start] + separator + text[end:]
    return text


def get_value(text: str, key: str, default=None):
    m = re.search(r"(?mi)^%s=(.*?)\s*$" % re.escape(key), text)
    return m.group(1) if m else default


def set_value(text: str, key: str, value: str) -> str:
    """Replace the first ``key=`` line, preserving its line ending."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            lines[i] = "%s=%s%s" % (key, value, eol)
            return "".join(lines)
    raise KeyError("missing key %s=" % key)


def set_name(text: str, name: str, free_radar: bool = False) -> str:
    """Set the map's display name; optionally force ``FreeRadar=yes``."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("Name="):
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            lines[i] = "Name=%s%s" % (name, eol)
            if free_radar and not any(l.startswith("FreeRadar=") for l in lines):
                lines.insert(i + 1, "FreeRadar=yes" + eol)
            return "".join(lines)
    raise KeyError("missing Name=")


def ensure_value(text: str, key: str, value: str) -> str:
    """Set ``key=value``; insert it after ``Name=`` when the key is absent."""
    if re.search(r"(?mi)^%s=" % re.escape(key), text):
        return set_value(text, key, value)
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("Name="):
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            lines.insert(i + 1, "%s=%s%s" % (key, value, eol))
            return "".join(lines)
    raise KeyError("missing Name= (cannot insert %s)" % key)


# ------------------------------------------------------------------ coords
def pack_cell(x: int, y: int) -> int:
    """Waypoint packing used by the map format (x must be < 1000)."""
    if not 0 <= x < 1000:
        raise ValueError("cell x out of range: %d" % x)
    return y * 1000 + x


def unpack_cell(packed: int):
    return packed % 1000, packed // 1000


def local_size(text: str):
    """Return (left, top, width, height) from ``LocalSize=``."""
    m = re.search(
        r"(?mi)^LocalSize=\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)",
        text,
    )
    if not m:
        raise ValueError("missing LocalSize=")
    return tuple(int(v) for v in m.groups())


def count_waypoints(text: str) -> int:
    body = section_body(text, "Waypoints")
    return len(re.findall(r"(?m)^\d+=", body))


def set_waypoint(text: str, index: int, packed: int) -> str:
    span = section_span(text, "Waypoints")
    if not span:
        raise KeyError("missing [Waypoints]")
    start, end = span
    header_end = text.find("\n", start) + 1
    body = text[header_end:end]
    new_body, count = re.subn(
        r"(?m)^%d=.*$" % index, "%d=%d" % (index, packed), body, count=1
    )
    if count != 1:
        raise KeyError("waypoint %d not found" % index)
    return text[:header_end] + new_body + text[end:]


# --------------------------------------------------------------- terrain
def decode_terrain(text: str):
    """Decode [IsoMapPack5] into a list of [x, y, tile, sub, z, legacy]."""
    body = section_body(text, "IsoMapPack5")
    parts = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if "=" in line:
            line = line.split("=", 1)[1].strip()
        if line:
            parts.append(line)
    data = base64.b64decode("".join(parts))

    raw = bytearray()
    pos = 0
    while pos + 4 <= len(data):
        src_len, dst_len = struct.unpack_from("<HH", data, pos)
        pos += 4
        if src_len == 0 and dst_len == 0:
            break
        raw.extend(lzokay.decompress(data[pos:pos + src_len], dst_len))
        pos += src_len

    records = []
    offset = 0
    while offset + RECORD_SIZE <= len(raw):
        x, y = struct.unpack_from("<hh", raw, offset)
        if x == 0 and y == 0:
            break
        tile, sub, z, legacy = struct.unpack_from("<iBBB", raw, offset + 4)
        records.append([x, y, tile, sub, z, legacy])
        offset += RECORD_SIZE
    return records


def encode_terrain(records, newline: str = "\n") -> str:
    raw = bytearray()
    for x, y, tile, sub, z, legacy in records:
        raw.extend(struct.pack("<hh iBBB", x, y, tile, sub, z, legacy))
    raw.extend(b"\x00\x00\x00\x00")

    packed = bytearray()
    for offset in range(0, len(raw), BLOCK):
        chunk = bytes(raw[offset:offset + BLOCK])
        compressed = lzokay.compress(chunk)
        if len(compressed) > 0xFFFF:
            raise ValueError("compressed block exceeds 64 KiB")
        packed.extend(struct.pack("<HH", len(compressed), len(chunk)))
        packed.extend(compressed)

    b64 = base64.b64encode(bytes(packed)).decode("ascii")
    lines = ["[IsoMapPack5]"]
    for offset in range(0, len(b64), BASE64_LINE):
        lines.append("%d=%s" % (offset // BASE64_LINE + 1, b64[offset:offset + BASE64_LINE]))
    return newline.join(lines) + newline


def uniform_terrain(text: str, tile: int = 418, sub: int = 0, z: int = 4,
                    newline: str = "\n"):
    """Rewrite every cell to one tile at one height.  Returns (text, count)."""
    records = decode_terrain(text)
    for record in records:
        record[2] = tile
        record[3] = sub
        record[4] = z
        record[5] = 0
    span = section_span(text, "IsoMapPack5")
    new_section = encode_terrain(records, newline)
    return text[:span[0]] + new_section + text[span[1]:], len(records)


# --------------------------------------------------------------- triggers
def trigger_block(
    player_count: int,
    reveal: bool = True,
    iron_curtain: bool = True,
    hunt: bool = True,
    hunt_chunk: int = 10,
    newline: str = "\n",
    hunt_prefix: str = "03",
    hunt_name: str = None,
) -> str:
    """Build a trigger block for a spectator map.

    * ``RevealAll``   - action 16, one second after start.
    * ``IronCurtain`` - action 109 at waypoint 0 every 10 s.
    * ``AIHuntNN``    - action 6 (All to Hunt) for slots 1..player_count-1,
      every 20 s.  Ares ``Player @ X`` selectors are ``0x117B + slot``.

    All triggers are logic tags (timer event 13), so they do not need to be
    attached to a house on the map.
    """
    slots = list(range(1, player_count))
    chunks = [slots[i:i + hunt_chunk] for i in range(0, len(slots), hunt_chunk)]
    if hunt_name is None and len(chunks) == 1:
        # Single-chunk maps (<= 11 players) use the compact 02xxxxxx block.
        hunt_prefix, hunt_name = "02", "AIHuntAll"

    triggers, events, actions, tags = [], [], [], []
    if reveal:
        triggers.append("01000000=Americans,<none>,RevealAll,0,1,1,1,0")
        events.append("01000000=1,13,0,1")
        actions.append("01000000=1,16,0,0,0,0,0,0,0")
        tags.append("01000001=0,RevealAll,01000000")
    if iron_curtain:
        triggers.append("01000010=Americans,<none>,IronCurtain,0,1,1,1,0")
        events.append("01000010=1,13,0,10")
        actions.append("01000010=1,109,0,0,0,0,0,0,A")
        tags.append("01000011=2,IronCurtain,01000010")
    if hunt:
        for index, chunk in enumerate(chunks):
            tid = hunt_prefix + "%06X" % (index * 0x10)
            label = hunt_name or ("AIHunt%02d" % index)
            triggers.append("%s=<none>,<none>,%s,0,1,1,1,0" % (tid, label))
            events.append("%s=1,13,0,20" % tid)
            body = ",".join("6,0,%d,0,0,0,0,A" % (0x117B + slot) for slot in chunk)
            actions.append("%s=%d,%s" % (tid, len(chunk), body))
            tags.append("%s=2,%s,%s" % (hunt_prefix + "%06X" % (index * 0x10 + 1), label, tid))

    lines = ["[Triggers]"] + triggers + [""]
    lines += ["[Events]"] + events + [""]
    lines += ["[Actions]"] + actions + [""]
    lines += ["[Tags]"] + tags + [""]
    return newline.join(lines) + newline


def add_triggers(text: str, block: str) -> str:
    """Insert a trigger block before [Waypoints].  Refuses to merge blocks."""
    if has_section(text, "Triggers"):
        raise ValueError("map already has a [Triggers] section")
    anchor = re.search(r"(?m)^\[Waypoints\]", text)
    position = anchor.start() if anchor else len(text)
    return text[:position] + block + text[position:]
