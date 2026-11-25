# -*- coding: utf-8 -*-
"""Read and write Westwood ``.csf`` string tables.

Why this exists: a unit's or superweapon's ``UIName=`` is a CSF *label*, not free
text.  ``[ZAINukeGunshipDrop] UIName=Name:Nuke`` shows the retail "Nuke Attack"
because ``Name:Nuke`` is a row in the game's ``ra2md.csf``; a label that is not
in the table is drawn as ``MISSING:'NAME:...'`` (the engine's ``CsfFile::text``
returns exactly that, and its unit test pins it).  A mod that wants its own
names therefore has to ship the labels.

A mod may ship ``ares.csf`` beside ``rulesmd.ini``.  On an Ares game (this mod
declares ``[Extensions] Ares=yes``) the engine loads ``ra2md.csf`` and then
appends ``ares.csf`` (language-agnostic), ``ares_<language>.csf`` and
``stringtable00.csf`` .. ``stringtable99.csf`` in that order, later rows
overriding earlier ones with the same label
(``tools/rules_oracle/ares_csf.md`` in the engine source).  The startup log line
``Loaded CSF string table: ra2md.csf; supplements=["ares.csf"]`` is the hard
evidence that it was read.

Why the **language-agnostic** ``ares.csf`` and not ``ares_ch.csf``: a
language-suffixed table is admitted only when its language dword equals the base
table's (``9`` = "ch" for the retail Chinese ``ra2md.csf``, ``0xFFFFFFFF`` also
accepted), and a mismatch is dropped silently.  This project's game is played
with the Chinese interface, so ``ares.csf`` -- which ignores the language -- is
the one file that is right on every install.

Format written here, matching the engine's parser
(``assets::csf_file::{parse_label_header, parse_value, decode_csf_string}``) and
its own test fixture ``build_test_csf``:

    header          24 bytes: " FSC" | version (3) | label count | string
                    count | reserved | language
    per string      " LBL" | pairs in this label (1) | label length | label
                    " RTS" | character count | UTF-16-LE code units, each byte
                    XOR 0xFF

Lengths do **not** include a terminating NUL: that is what the engine's fixture
writes, and the engine's decoder keeps every code unit it is given.
"""
from __future__ import annotations

import struct
import sys

#: " FSC" -- the file header, little-endian as the engine reads it.
HEADER_MAGIC = 0x43534620
#: " LBL" -- one label record.
LABEL_MAGIC = 0x4C424C20
#: " RTS" -- one value (the engine also knows "WRTS" with an audio extra).
STRING_MAGIC = 0x53545220
#: Version the engine accepts (`version as i32 >= 2`).
VERSION = 3
#: The header is fixed at 24 bytes.
HEADER_SIZE = 24
#: Non-zero and never used by the engine; kept the same as its test fixture.
RESERVED = 0xAABBCCDD
#: 0 = US English.  A generic `ares.csf` is admitted whatever this says; 9 is
#: "ch" (the retail Chinese table) and would also be honoured.  0 is the
#: neutral choice for a game whose base table may be any language.
LANGUAGE = 0


def _encode(text):
    """UTF-16-LE bytes with every byte complemented, as CSF stores values."""
    return bytes(byte ^ 0xFF for byte in text.encode("utf-16-le"))


def _decode(data):
    """Undo :func:`_encode`; a trailing NUL is tolerated and dropped."""
    return bytes(byte ^ 0xFF for byte in data).decode("utf-16-le").rstrip("\x00")


def build(entries):
    """Return the bytes of a CSF file holding ``entries``.

    ``entries`` is a mapping or an iterable of ``(label, text)`` pairs.  Rows
    are sorted by label so the output is byte-for-byte reproducible, and a
    duplicate label is an error instead of a silent last-one-wins.
    """
    pairs = sorted(dict(entries).items(), key=lambda pair: pair[0]) \
        if isinstance(entries, dict) else sorted(entries, key=lambda pair: pair[0])
    labels = [label for label, _text in pairs]
    if len(set(labels)) != len(labels):
        raise SystemExit("duplicate CSF label in %r" % (labels,))
    if not pairs:
        raise SystemExit("refusing to write an empty ares.csf")

    out = bytearray()
    out += struct.pack("<6I", HEADER_MAGIC, VERSION, len(pairs), len(pairs),
                       RESERVED, LANGUAGE)
    for label, text in pairs:
        name = label.encode("ascii")
        value = text.encode("utf-16-le")
        out += struct.pack("<3I", LABEL_MAGIC, 1, len(name))
        out += name
        out += struct.pack("<2I", STRING_MAGIC, len(value) // 2)
        out += _encode(text)
    return bytes(out)


def write(path, entries):
    """Write ``entries`` to ``path`` and return the number of labels."""
    data = build(entries)
    with open(path, "wb") as handle:
        handle.write(data)
    return len(dict(entries))


def read(path):
    """Parse a CSF file into ``{label: text}``.

    Deliberately strict about the magic numbers and the declared lengths: a
    truncated or hand-edited table must fail here, not as an empty name in the
    game.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) < HEADER_SIZE:
        raise ValueError("%s: %d bytes is smaller than the CSF header"
                         % (path, len(data)))
    magic, _version, _label_count, _string_count, _reserved, _language = \
        struct.unpack("<6I", data[:HEADER_SIZE])
    if magic != HEADER_MAGIC:
        raise ValueError("%s: bad header magic 0x%08X" % (path, magic))
    entries = {}
    offset = HEADER_SIZE
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("%s: truncated label header at %d" % (path, offset))
        label_magic, pair_count, name_len = struct.unpack("<3I", data[offset:offset + 12])
        if label_magic != LABEL_MAGIC:
            raise ValueError("%s: bad label magic 0x%08X at %d"
                             % (path, label_magic, offset))
        offset += 12
        label = data[offset:offset + name_len].decode("ascii")
        offset += name_len
        for _ in range(pair_count):
            if offset + 8 > len(data):
                raise ValueError("%s: truncated value header at %d" % (path, offset))
            string_magic, char_count = struct.unpack("<2I", data[offset:offset + 8])
            if string_magic != STRING_MAGIC:
                raise ValueError("%s: bad value magic 0x%08X at %d "
                                 "(only ' RTS' values are written here)"
                                 % (path, string_magic, offset))
            offset += 8
            byte_count = char_count * 2
            entries[label] = _decode(data[offset:offset + byte_count])
            offset += byte_count
    return entries


def main(argv):
    if len(argv) != 2:
        print("usage: python tools/csf.py <file.csf>", file=sys.stderr)
        return 2
    for label, text in read(argv[1]).items():
        print("%s=%s" % (label, text))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
