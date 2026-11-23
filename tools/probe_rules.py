# -*- coding: utf-8 -*-
"""Ask the engine which INI keys it actually parses.

    python tools/probe_rules.py --game-dir "F:/Games/VERA20K" --cases tools/sw-cases.txt

VERA20k's ``--probe`` prints a ``rules_digest``.  If that digest is a digest of
the *parsed* rules rather than of the file bytes, it is an oracle: change one
key and the digest changes only if the engine read that key.  ``selftest``
checks exactly that (a comment edit must not move it, a live key must, a known
dead key must not), and refuses to report anything if the digest turns out to be
content-based.

Each case is applied to a throwaway copy of the mod in ``Mods/_probe`` so the
shipped ``Mods/SuperAI`` is never touched; the copy is removed afterwards.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_MOD = "_probe"


def ra2_dir(game_dir):
    with open(os.path.join(game_dir, "config.toml"), "rb") as handle:
        return tomllib.load(handle)["paths"]["ra2_dir"]


def probe(game_dir, mod):
    result = subprocess.run(
        [os.path.join(game_dir, "vera20k.exe"), "--probe",
         "--ra2-dir", ra2_dir(game_dir), "--mod", mod],
        cwd=game_dir, capture_output=True, encoding="utf-8",
        errors="replace", timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def digest_of(report):
    return report.get("rules_digest") or report.get("rules_parts", {}).get("digest")


def with_edit(text, section, key, value, remove=False):
    """Set (or delete) ``key=`` inside ``section``; ``value`` may hold newlines."""
    lines = text.splitlines(keepends=True)
    out, current = [], None
    replaced = False
    for line in lines:
        header = line.strip()
        if header.startswith("[") and header.endswith("]"):
            current = header[1:-1].strip()
        if current == section and line.strip().lower().startswith(key.lower() + "="):
            if remove:
                replaced = True
                continue
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            out.append("%s=%s%s" % (key, value, eol))
            replaced = True
            continue
        out.append(line)
    if not replaced and not remove:
        # Insert right after the section header.
        out, current = [], None
        for line in lines:
            out.append(line)
            header = line.strip()
            if header.startswith("[") and header.endswith("]"):
                current = header[1:-1].strip()
                if current == section:
                    out.append("%s=%s\r\n" % (key, value))
        if current is None or not any(
                l.strip().startswith("[%s]" % section) for l in lines):
            raise SystemExit("section [%s] not found" % section)
    return "".join(out)


def run_case(game_dir, edits, label, base_mod="SuperAI"):
    """Copy the mod, apply ``edits``, probe it, return (digest, error)."""
    target = os.path.join(game_dir, "Mods", PROBE_MOD)
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(os.path.join(game_dir, "Mods", base_mod), target)
    try:
        if edits:
            path = os.path.join(target, "rulesmd.ini")
            text = open(path, "rb").read().decode("latin-1")
            for section, key, value, remove in edits:
                text = with_edit(text, section, key, value, remove)
            open(path, "wb").write(text.encode("latin-1"))
        try:
            return digest_of(probe(game_dir, PROBE_MOD)), None
        except RuntimeError as exc:
            return None, str(exc)[:200]
    finally:
        shutil.rmtree(target, ignore_errors=True)


def selftest(game_dir, base_mod):
    """Prove the digest tracks parsed rules, not file bytes."""
    baseline, error = run_case(game_dir, [], "baseline", base_mod)
    if error:
        raise SystemExit("baseline probe failed: %s" % error)
    print("baseline digest: %s" % baseline)

    comment = run_case(game_dir, [("General", ";probe comment", "x", False)], "comment", base_mod)
    live = run_case(game_dir, [("General", "TeamDelays", "111,222,333", False)], "live", base_mod)
    dead = run_case(game_dir, [("General", "WarRatio", "77", False)], "dead", base_mod)

    ok = True
    for label, (digest, err) in (("comment (must not move)", comment),
                                 ("live key TeamDelays (must move)", live),
                                 ("dead key WarRatio (must not move)", dead)):
        moved = digest is not None and digest != baseline
        print("  %-38s %s%s" % (label, "MOVED" if moved else "same",
                                "" if digest else "  (%s)" % err))
        expected = "must move" in label
        if moved != expected:
            ok = False
    if not ok:
        raise SystemExit(
            "the rules digest does not track parsed semantics; this oracle is "
            "unusable and the caller must fall back to shipping every candidate key")
    print("oracle OK: the digest tracks parsed rules")
    return baseline


def parse_cases(path):
    cases = []
    section = key = value = None
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif line.startswith("-"):
            cases.append((section, line[1:].strip(), "", True))
        elif "=" in line:
            key, value = line.split("=", 1)
            cases.append((section, key.strip(), value.strip(), False))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", required=True)
    parser.add_argument("--mod", default="SuperAI", help="mod to copy for each case")
    parser.add_argument("--cases", help="file of section/key=value cases")
    parser.add_argument("--selftest", action="store_true",
                        help="only prove the digest is a usable oracle")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    game_dir = os.path.abspath(args.game_dir)
    baseline = selftest(game_dir, args.mod)
    if args.selftest or not args.cases:
        return 0

    cases = parse_cases(args.cases)
    print("\n%-46s %s" % ("case", "engine parsed it?"))
    parsed = 0
    for section, key, value, remove in cases:
        digest, error = run_case(game_dir, [(section, key, value, remove)], key, args.mod)
        if error:
            print("  %-44s PROBE FAILED: %s" % ("[%s] %s" % (section, key), error))
            continue
        moved = digest != baseline
        parsed += 1 if moved else 0
        print("  %-44s %s" % ("[%s] %s%s" % (section, key,
                                            "" if remove else "=" + value),
                              "YES" if moved else "no"))
    print("\n%d of %d case(s) changed the parsed rules" % (parsed, len(cases)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
