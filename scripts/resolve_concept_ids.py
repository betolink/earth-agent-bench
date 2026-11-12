#!/usr/bin/env python3
"""Resolve CMR concept_ids for task collections and write them into the YAMLs.

Each task collection has a ``short_name``; the grounded agent should be told the
exact dataset to use, which is unambiguous by CMR ``concept_id``. This script
resolves ``short_name -> concept_id`` via CMR and inserts a ``concept_id:`` line
under each ``short_name:`` in ``benchmark/tasks/access-pattern/**/*.yaml`` (idempotent).

Usage::

    python scripts/resolve_concept_ids.py            # dry run (report only)
    python scripts/resolve_concept_ids.py --write     # edit the task YAMLs
    python scripts/resolve_concept_ids.py --write --cache concept_ids.yaml
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

EAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EAB / "src"))

from earth_agent_bench.oracles.cmr import find_collections  # noqa: E402

TASKS = EAB / "benchmark" / "tasks" / "access-pattern"
_SHORT = re.compile(r"^(\s*)(?:-\s+)?short_name:\s*(\S+)\s*$")
_CONCEPT = re.compile(r"^\s*concept_id:")


def resolve(short_name: str) -> str | None:
    """Return the cloud-hosted (else first) CMR concept_id for a short name."""
    try:
        entries = find_collections(short_name)
    except Exception as error:  # network/token
        print(f"  ! {short_name}: {error}", file=sys.stderr)
        return None
    cloud = [e for e in entries if e.get("cloud_hosted")]
    pick = (cloud or entries)
    return pick[0].get("id") if pick else None


def main() -> int:
    """Resolve concept_ids and (with --write) insert them into the task YAMLs."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="edit task YAMLs in place")
    ap.add_argument("--cache", type=Path, help="also write a short_name->id YAML map")
    args = ap.parse_args()

    cache: dict[str, str | None] = {}
    changed = 0
    for path in sorted(glob.glob(str(TASKS / "*" / "*.yaml"))):
        lines = Path(path).read_text().splitlines()
        out, inserted = [], []
        for i, line in enumerate(lines):
            out.append(line)
            match = _SHORT.match(line)
            if not match:
                continue
            short = match.group(2)
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if _CONCEPT.match(nxt):  # already has one
                continue
            if short not in cache:
                cache[short] = resolve(short)
            cid = cache[short]
            if cid:
                out.append(f"{match.group(1)}  concept_id: {cid}")
                inserted.append((short, cid))
            else:
                inserted.append((short, None))
        if any(cid for _, cid in inserted) and args.write:
            Path(path).write_text("\n".join(out) + "\n")
            changed += 1
        name = Path(path).stem
        resolved = [f"{s}->{c}" for s, c in inserted if c]
        missing = [s for s, c in inserted if not c]
        print(f"{name[:34]:34s} ok={len(resolved):2d} missing={missing or '-'}")

    if args.cache:
        import yaml
        args.cache.write_text(yaml.safe_dump({k: v for k, v in sorted(cache.items())}))
        print(f"cache -> {args.cache}")
    print(f"\n{'wrote' if args.write else 'dry run'}: {changed} files would change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
