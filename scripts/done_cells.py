#!/usr/bin/env python3
"""Print completed EAB cells (task|model|harness|condition) for a run stamp.

Resume helper for scripts/eab-full-run.sh: only cells whose result.json was
written at or after RUN_START (and that actually completed a trial) are skipped,
so a cell killed mid-flight re-runs. Job names are parsed via runs.parse_job_dir.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

EAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EAB / "src"))
from earth_agent_bench.runs import parse_job_dir  # noqa: E402

RUNS = EAB / "runs" / "harbor"


def main() -> int:
    """Print ``task|model|harness|condition`` for each completed cell, one per line."""
    start = sys.argv[1] if len(sys.argv) > 1 else ""
    done: set[str] = set()
    for r in glob.glob(str(RUNS / "eab-*" / "result.json")):
        ref = parse_job_dir(Path(r).parent.name)
        if start and (not ref.stamp or ref.stamp < start):
            continue
        try:
            j = json.loads(Path(r).read_text())
        except Exception:
            continue
        if j.get("stats", {}).get("n_completed_trials", 0) == 0:
            continue
        if ref.task and ref.model:
            done.add(f"{ref.task}|{ref.model}|{ref.harness}|{ref.condition}")
    print("\n".join(sorted(done)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
