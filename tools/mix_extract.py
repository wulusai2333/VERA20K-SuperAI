"""Pull a file out of the retail MIX archives (bounded, no full-tree scan).

RA2 ships its voxels inside nested MIX archives: ``ra2md.mix`` contains further
``*.mix`` payloads, and the unit models live in one of those.  A naive recursive
walk over every archive in the data folder takes minutes, so the search here is
bounded:

* only the archives named on the command line are opened;
* a nested payload is descended into only if it parses as a MIX and is no larger
  than ``--max-entry``;
* the recursion depth is capped.

Two MIX layouts are supported because the shipped archives use the "count first"
one (count at offset 0, directory at 4) while older tools assume a 12-byte prefix.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys

_TABLE = []


def _build_table() -> None:
    for index in range(256):
        value = index
        for _ in range(8):
            value = (value >> 1) ^ 0xEDB88320 if value & 1 else value >> 1
        _TABLE.append(value)


_build_table()


def westwood_hash(name: str, seed: int = 0, invert: bool = False) -> int:
    crc = seed
    for byte in name.upper().encode("ascii", "replace"):
        crc = (crc >> 8) ^ _TABLE[(crc ^ byte) & 0xFF]
    return (~crc & 0xFFFFFFFF) if invert else (crc & 0xFFFFFFFF)


def candidate_hashes(name: str) -> tuple[int, ...]:
    """The archives here disagree on seed/xor, so accept all four variants."""
    return (westwood_hash(name),
            westwood_hash(name, 0xFFFFFFFF),
            westwood_hash(name, invert=True),
            westwood_hash(name, 0xFFFFFFFF, invert=True))


def _layout(data: bytes) -> tuple[int, int] | None:
    """(entry count, directory offset) if `data` looks like a MIX archive."""
    if len(data) < 16:
        return None
    header = struct.unpack("<I", data[:4])[0]
    if header & 0x80000000:
        return None  # encrypted body
    if 0 < header < 2_000_000 and 4 + header * 12 <= len(data):
        return header, 4
    count = struct.unpack("<I", data[12:16])[0]
    if 0 < count < 2_000_000 and 16 + count * 12 <= len(data):
        return count, 16
    return None


def _entries(data: bytes) -> dict[int, tuple[int, int]]:
    layout = _layout(data)
    if layout is None:
        return {}
    count, start = layout
    out = {}
    for i in range(count):
        base = start + i * 12
        name_hash, offset, size = struct.unpack("<III", data[base:base + 12])
        out[name_hash] = (offset, size)
    return out


def _find(data: bytes, wanted: tuple[int, ...], depth: int, max_depth: int,
          max_entry: int, trail: list[str]) -> bytes | None:
    entries = _entries(data)
    for index, cand in enumerate(wanted):
        entry = entries.get(cand)
        if entry is not None:
            offset, size = entry
            trail.append("hashvariant#%d" % index)
            return data[offset:offset + size]
    if depth >= max_depth:
        return None
    for offset, size in entries.values():
        if size > max_entry or size < 32:
            continue
        payload = data[offset:offset + size]
        if _layout(payload) is None:
            continue
        found = _find(payload, wanted, depth + 1, max_depth, max_entry, trail)
        if found is not None:
            return found
    return None


def extract(archive_path: str, wanted: str, max_depth: int, max_entry: int) -> bytes:
    with open(archive_path, "rb") as handle:
        data = handle.read()
    if _layout(data) is None:
        raise SystemExit("%s is not a MIX archive" % archive_path)
    trail: list[str] = []
    found = _find(data, candidate_hashes(wanted), 0, max_depth, max_entry, trail)
    if found is None:
        raise SystemExit("%s not found in %s (depth %d, entries <= %d bytes)"
                         % (wanted, os.path.basename(archive_path), max_depth, max_entry))
    print("found %s in %s at %s (%d bytes)"
          % (wanted, os.path.basename(archive_path), "/".join(trail), len(found)))
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", help="MIX file to search")
    parser.add_argument("--name", help="entry name, e.g. ZEP.VXL")
    parser.add_argument("--out", help="where to write the extracted payload")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-entry", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        assert westwood_hash("zep.vxl") == westwood_hash("ZEP.VXL")
        assert westwood_hash("ZEP.VXL") != westwood_hash("ZEP.HVA")
        assert len(set(candidate_hashes("ZEP.VXL"))) == 4
        print("selftest OK")
        return 0

    if not (args.archive and args.name and args.out):
        parser.error("--archive, --name and --out are required (or --selftest)")
    payload = extract(args.archive, args.name, args.max_depth, args.max_entry)
    with open(args.out, "wb") as handle:
        handle.write(payload)
    print("wrote %s (%d bytes)" % (args.out, len(payload)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
