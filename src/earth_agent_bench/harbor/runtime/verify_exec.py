"""Verifier: execute the agent's Python deliverable under a budget, then grade.

Outcomes are explicit — `ok | error | timeout | oom` from the executor, plus
`correct | incorrect` from a byte-compare (`--expected`) or a typed gold
(`--gold`). Emits Harbor reward files and a details.json carrying the execution
profile (wall time, peak RSS, and an optional scalene/memray artifact path).

Runs inside the sandbox. The vendored ``earth_agent_bench`` package provides
``executor``/``profiler``; locally we fall back to the repo ``src``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:  # vendored into /tests/earth_agent_bench (sandbox)
    from earth_agent_bench.executor import run_script
except ImportError:  # local dev
    sys.path.insert(0, str(HERE.parents[3]))
    from earth_agent_bench.harbor.runtime.executor import run_script


def _grade(gold_path: Path | None, expected: Path | None, artifact: Path | None) -> tuple[bool, str]:
    if artifact is None or not artifact.exists():
        return False, "artifact missing"
    produced = artifact.read_bytes()
    if expected is not None:
        return (produced == expected.read_bytes()), ("byte match" if produced == expected.read_bytes() else "byte mismatch")
    if gold_path is not None:
        try:
            from earth_agent_bench.evals import EvalGold, grade
        except ImportError:
            sys.path.insert(0, str(HERE.parents[3]))
            from earth_agent_bench.evals import EvalGold, grade
        gold = EvalGold.model_validate(json.loads(gold_path.read_text()))
        result = grade(gold, artifact.read_text().strip())
        return bool(result.reward >= 1.0), f"gold grade reward={result.reward}"
    return False, "no grader (pass --expected or --gold)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="deliverable to execute, e.g. /app/program.py")
    ap.add_argument("--workdir", default="/app")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--mem-mb", type=int, default=0)
    ap.add_argument("--cpu-s", type=int, default=0)
    ap.add_argument("--profile", default="none", help="none | scalene | memray")
    ap.add_argument("--profile-out", default="/logs/verifier/profile.json")
    ap.add_argument("--artifact", default=None, help="output file to grade")
    ap.add_argument("--expected", default=None, help="expected bytes for --artifact")
    ap.add_argument("--gold", default=None, help="typed gold json for --artifact")
    ap.add_argument("--logs", default="/logs/verifier")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    artifact = None
    if args.artifact:
        artifact = Path(args.artifact)
        if not artifact.is_absolute():
            artifact = workdir / artifact

    res = run_script(
        args.script, workdir=workdir, timeout_s=args.timeout,
        mem_mb=args.mem_mb or None, cpu_s=args.cpu_s or None,
        profile=None if args.profile == "none" else args.profile,
        profile_out=Path(args.profile_out),
    )

    correct = False
    note = f"execution {res.status}"
    if res.status == "ok":
        correct, note = _grade(Path(args.gold) if args.gold else None,
                               Path(args.expected) if args.expected else None, artifact)

    reward = 1.0 if correct else 0.0
    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    details = {
        "reward": reward,
        "correct": correct,
        "exec_status": res.status,          # ok | error | timeout | oom
        "returncode": res.returncode,
        "wall_s": res.wall_s,
        "peak_rss_mb": res.peak_rss_mb,
        "profile": res.profile,
        "note": note,
        "stderr_tail": res.stderr[-800:],
    }
    (logs / "reward.txt").write_text(f"{reward}\n")
    (logs / "reward.json").write_text(json.dumps({"reward": reward, "exec_status": res.status}))
    (logs / "details.json").write_text(json.dumps(details, indent=2))
    print(json.dumps(details, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
