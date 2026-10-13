"""Score access-pattern selection from the deliverable the agent produced.

v2 contract: the deliverable is ``access.py`` (the access code), run at a demo
scope. The verifier:

  1. finds ``access.py`` and runs it under the executor (``ok|error|timeout|oom``);
  2. reads the observed access events written by ``eab_instrument``;
  3. applies a code check (sanctioned: uses earthaccess, not raw CMR/URL fetches);
  4. scores the components and writes ``/logs/verifier/{reward,details}.json``.

Falls back to the agent's ``output/access_summary.json`` when no events exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from earth_agent_bench.harbor_verify import find, read_events, roots, summarize_events
from earth_agent_bench.schemas import RunObservation
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


def run_deliverable(script: Path, timeout: float, mem_mb: int) -> str:
    """Run ``access.py`` under the executor; return the exec status."""
    try:
        from earth_agent_bench.executor import run_script
    except ImportError:  # local dev
        sys.path.insert(0, str(HERE.parents[3]))
        from earth_agent_bench.harbor.runtime.executor import run_script
    result = run_script(script, workdir=script.parent, timeout_s=timeout,
                        mem_mb=mem_mb or None)
    return result.status


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

    # 1) run the agent's deliverable (demo scope) under the executor
    script = find(roots_list, "access.py", "work/access.py", "output/access.py")
    check: dict = {}
    exec_status = "missing"
    if script is not None:
        check = code_check(script)
        exec_status = run_deliverable(script, args.run_timeout, args.run_mem_mb)

    # 2) observed access events (from the run above, or the agent's own run)
    events = read_events(
        find(
            roots_list,
            "access_events.jsonl",
            "output/access_events.jsonl",
            "agent/access_events.jsonl",
        )
    )
    observed = summarize_events(events)
    obs_path = find(roots_list, "observation.json", "output/observation.json")
    summary_path = find(roots_list, "output/access_summary.json")

    if obs_path is not None:
        observation = RunObservation.model_validate(json.loads(obs_path.read_text()))
    else:
        summary = json.loads(summary_path.read_text()) if summary_path else {}
        declared_services = summary.get("access_services_used", [])
        candidate_patterns = observed["patterns"] or classify(declared_services)
        dominant = dominant_pattern(candidate_patterns, task.pattern_tiers)
        patterns = [dominant] if dominant else []
        services = list(dict.fromkeys([*observed["services"], *declared_services]))
        collections = list(
            dict.fromkeys([*observed["short_names"], *summary.get("collections", [])])
        )
        representation = observed["representation"]
        if representation == "unknown" and any(p[0] in "CT" for p in patterns):
            representation = "lazy"
        output_dir = (
            summary_path.parent if summary_path else Path(args.workspace) / "output"
        )
        artifacts = (
            [
                path for path in output_dir.glob("*")
                if path.is_file() and path.name != "access_summary.json"
            ]
            if output_dir.exists()
            else []
        )
        observation = RunObservation(
            task_id=task.task_id,
            observed_patterns=patterns,
            collection_short_names=collections,
            discovered_services=services,
            representation=representation,
            validation_passed=observed["data_access"] or bool(artifacts),
            metrics={
                "bytes_read": int(summary.get("bytes_read_estimate", 0) or 0),
                "objects_read": int(observed["objects_read"]),
                "runtime_seconds": observed["runtime_s"],
            },
        )

    result = score_run(task, observation)
    reward = result.reward
    # Code check: an unsanctioned deliverable (raw CMR, no earthaccess) is penalised.
    if check and not check.get("sanctioned"):
        reward = round(reward * 0.5, 4)

    details = result.model_dump()
    details.update({
        "reward": reward,
        "exec_status": exec_status,
        "code_check": check,
        "script": str(script) if script else None,
    })
    # Harbor's reward.json must be flat and numeric; keep diagnostics separate.
    rewards = {
        key: value
        for key, value in details.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }

    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.json").write_text(json.dumps(rewards))
    (logs / "reward.txt").write_text(f"{reward}\n")
    (logs / "details.json").write_text(json.dumps(details, indent=2))

    print(json.dumps(details, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
