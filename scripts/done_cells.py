#!/usr/bin/env python3
"""Print completed EAB cells (task|model|harness|condition) for a run stamp.

Resume helper for scripts/eab-full-run.sh: only cells whose result.json was
written at or after RUN_START (and that actually completed a trial) are skipped,
so a cell killed mid-flight re-runs. The matrix (models/harnesses/conditions) is
read from experiments/run.yaml, so it always matches the driver.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

EAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EAB / "src"))
from earth_agent_bench.runconfig import load_run_config  # noqa: E402

RUNS = EAB / "runs" / "harbor"
STAMP = re.compile(r"-(\d{8}-\d{6})$")


def main() -> int:
    start = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg = load_run_config()
    models, harnesses, conds = cfg["models"], cfg["harnesses"], cfg["conditions"]
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
        for mo in models:
            for h in harnesses:
                for c in conds:
                    mk = f"-{mo}-{h}-{c}-"
                    if mk in body:
                        done.add(f"{body[:body.index(mk)]}|{mo}|{h}|{c}")
    print("\n".join(sorted(done)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
