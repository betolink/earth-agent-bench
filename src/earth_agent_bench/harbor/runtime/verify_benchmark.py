"""Score access-pattern selection from the calls the agent actually made.

Runs in the agent environment. Prefers the observed access events written by
eab_instrument, falling back to the agent's output/access_summary.json. Writes
the component scores to /logs/verifier/reward.json and diagnostics to
/logs/verifier/details.json.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="/app")
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--task", default=str(HERE / "task.yaml"))
    parser.add_argument("--logs", default="/logs/verifier")
    args = parser.parse_args()

    roots_list = roots(args.workspace, args.search_root)
    task = load_task(args.task)

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
    details = result.model_dump()
    # Harbor's reward.json must be flat and numeric; keep diagnostics separate.
    rewards = {
        key: value
        for key, value in details.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }

    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.json").write_text(json.dumps(rewards))
    (logs / "reward.txt").write_text(f"{result.reward}\n")
    (logs / "details.json").write_text(json.dumps(details, indent=2))

    print(json.dumps(details, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
