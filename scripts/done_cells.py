#!/usr/bin/env python3
"""Print completed EAB cells (task|model|harness|condition) for a run stamp.

Used by scripts/eab-full-run.sh to resume: only cells whose result.json was
written at or after RUN_START (and actually completed a trial) are skipped.
Cells that failed for infra reasons should be removed first so they re-run.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

EAB = Path(__file__).resolve().parents[1]
RUNS = EAB / "runs" / "harbor"
MODELS = ["tiel-coder-35b", "ornith-1.5-9b"]
HARNESSES = ["pi", "opencode", "codex-cli"]
CONDITIONS = ["baseline", "improve", "mcp", "skills", "mcp-skills"]
STAMP = re.compile(r"-(\d{8}-\d{6})$")


def main() -> int:
    start = sys.argv[1] if len(sys.argv) > 1 else ""
    done: set[str] = set()
    for r in glob.glob(str(RUNS / "eab-*" / "result.json")):
        name = Path(r).parent.name
        m = STAMP.search(name)
        if start and (not m or m.group(1) < start):
            continue
        try:
            j = json.loads(Path(r).read_text())
        except Exception:
            continue
        if j.get("stats", {}).get("n_completed_trials", 0) == 0:
            continue
        body = name[len("eab-"):]
        for mo in MODELS:
            for h in HARNESSES:
                for c in CONDITIONS:
                    mk = f"-{mo}-{h}-{c}-"
                    if mk in body:
                        done.add(f"{body[:body.index(mk)]}|{mo}|{h}|{c}")
    print("\n".join(sorted(done)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
