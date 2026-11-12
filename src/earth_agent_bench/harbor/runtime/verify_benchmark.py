"""Score access-pattern selection from the deliverable the agent produced.

v3 contract: verification runs in its own container. The verifier:

  1. re-runs ``access.py`` under the executor with a *fresh* trusted access log
     (``ok|error|timeout|oom``), so the evidence is produced in a container the
     agent never touched;
  2. falls back to the agent's collected events (``/logs/agent``) only when the
     deliverable is missing or produced no events;
  3. never trusts the agent's self-reported ``access_summary.json``;
  4. writes ``/logs/verifier/{reward,details}.json`` with a ``pass`` (headline,
     all-or-nothing) and a ``score`` (weighted partial credit).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from earth_agent_bench.harbor_verify import (
    find,
    read_events,
    roots,
    summarize_events,
)
from earth_agent_bench.scoring import score_run
from earth_agent_bench.scoring.service_discovery import SERVICE_ALIASES
from earth_agent_bench.tasks import load_task

CANONICAL_TO_PATTERN = {
    "virtual_zarr": "C1", "native_zarr": "C2", "cog": "C3",
    "harmony": "S1", "opendap": "S2", "opendap_cloud": "S3",
    "appeears": "S4", "giovanni": "S5",
    "filtered_download": "F1", "full_download": "M1",
}


def canonical(service: str) -> str:
    token = str(service).strip().lower()
    for name, aliases in SERVICE_ALIASES.items():
        if token in aliases:
            return name
    return token


def classify(services) -> list[str]:
    patterns = []
    for service in services or []:
        pattern = CANONICAL_TO_PATTERN.get(canonical(service))
        if pattern and pattern not in patterns:
            patterns.append(pattern)
    return patterns


def dominant_pattern(patterns, tiers):
    for tier in ("best", "acceptable", "marginal"):
        for candidate in getattr(tiers, tier):
            if candidate in patterns:
                return candidate
    return patterns[0] if patterns else None


def code_check(script: Path) -> dict:
    """Static check: does the deliverable use the sanctioned access path?"""
    text = script.read_text(errors="replace")
    low = text.lower()
    check = {
        "uses_earthaccess": "earthaccess" in low,
        "uses_virtualize": "virtualize(" in low,
        "uses_open": "earthaccess.open(" in low,
        "raw_cmr": "cmr.earthdata.nasa.gov" in low,
        "raw_url_fetch": ("requests." in low or "urllib" in low or "curl " in low),
    }
    check["sanctioned"] = bool(check["uses_earthaccess"] and not check["raw_cmr"])
    return check


def run_deliverable(script: Path, timeout: float, mem_mb: int, log: Path) -> str:
    """Run ``access.py`` under the executor; return the exec status.

    ``EAB_ACCESS_LOG`` points at a verifier-owned file so the events we grade
    cannot be pre-seeded by the agent.
    """
    try:
        from earth_agent_bench.executor import run_script
    except ImportError:  # local dev
        sys.path.insert(0, str(HERE.parents[3]))
        from earth_agent_bench.harbor.runtime.executor import run_script
    log.parent.mkdir(parents=True, exist_ok=True)
    result = run_script(
        script,
        workdir=script.parent,
        timeout_s=timeout,
        mem_mb=mem_mb or None,
        env={"EAB_ACCESS_LOG": str(log)},
    )
    return result.status


def pass_gate(task, observation, exec_status: str, check: dict) -> tuple[float, dict]:
    """All-or-nothing pass: sanctioned code, good pattern, real access, exec ok."""
    accepted = set(task.pattern_tiers.best) | set(task.pattern_tiers.acceptable)
    sanctioned = bool(check.get("sanctioned"))
    pattern_ok = any(pattern in accepted for pattern in observation.observed_patterns)
    accessed = bool(observation.validation_passed)
    executed = exec_status == "ok"
    passed = executed and sanctioned and pattern_ok and accessed
    reasons = {
        "executed": executed,
        "sanctioned": sanctioned,
        "pattern_ok": pattern_ok,
        "accessed": accessed,
    }
    return (1.0 if passed else 0.0), reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="/app")
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--task", default=str(HERE / "task.yaml"))
    parser.add_argument("--logs", default="/logs/verifier")
    parser.add_argument("--run-timeout", type=float, default=300.0,
                        help="budget for running access.py at demo scope")
    parser.add_argument("--run-mem-mb", type=int, default=0)
    args = parser.parse_args()

    roots_list = roots(args.workspace, args.search_root)
    task = load_task(args.task)

    script = find(roots_list, "access.py", "work/access.py", "output/access.py")
    check: dict = {}
    exec_status = "missing"
    events: list[dict] = []
    events_source = "none"

    if script is not None:
        check = code_check(script)
        trusted_log = Path(args.logs) / "access_events.jsonl"
        exec_status = run_deliverable(
            script, args.run_timeout, args.run_mem_mb, trusted_log
        )
        events = read_events(trusted_log if trusted_log.exists() else None)
        events_source = "verifier-run"

    if not events:
        # Real instrumented events from the agent's own run (never its summary).
        agent_log = find(roots_list, "agent/access_events.jsonl", "access_events.jsonl")
        events = read_events(agent_log)
        if events:
            events_source = f"agent-run:{agent_log}"

    observed = summarize_events(events)

    output_dir = find(roots_list, "output")
    artifacts = (
        [path for path in output_dir.glob("*")
         if path.is_file() and path.name not in ("access_summary.json", "access_events.jsonl")]
        if output_dir is not None and output_dir.is_dir()
        else []
    )

    # Build the observation from evidence only: no self-reported patterns.
    from earth_agent_bench.schemas import RunObservation

    dominant = dominant_pattern(observed["patterns"], task.pattern_tiers)
    observation = RunObservation(
        task_id=task.task_id,
        observed_patterns=[dominant] if dominant else [],
        collection_short_names=observed["short_names"],
        discovered_services=observed["services"],
        representation=observed["representation"],
        validation_passed=bool(observed["data_access"]),
        metrics={
            "bytes_read": 0,
            "objects_read": int(observed["objects_read"]),
            "runtime_seconds": observed["runtime_s"],
        },
    )

    result = score_run(task, observation)
    score = result.reward
    passed, pass_reasons = pass_gate(task, observation, exec_status, check)
    if check and not check.get("sanctioned"):
        score = round(score * 0.5, 4)

    details = result.model_dump()
    details.update({
        "reward": passed,
        "pass": passed,
        "score": score,
        "pass_reasons": pass_reasons,
        "exec_status": exec_status,
        "code_check": check,
        "events_source": events_source,
        "uncovered": not observed["data_access"],
        "artifact_count": len(artifacts),
        "script": str(script) if script else None,
    })
    # Harbor's reward files must be flat and numeric; diagnostics stay separate.
    rewards = {
        key: value
        for key, value in details.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    rewards["pass"] = passed

    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.json").write_text(json.dumps(rewards))
    (logs / "reward.txt").write_text(f"{passed}\n")
    (logs / "details.json").write_text(json.dumps(details, indent=2))

    print(json.dumps(details, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
