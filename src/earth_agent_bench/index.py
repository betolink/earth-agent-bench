"""Rebuildable metadata index over the Harbor run tree.

The filesystem under ``runs/harbor/`` is the source of truth (Harbor owns it);
this module derives one flat record per trial for fast cross-cell queries. Delete
and rebuild anytime — nothing depends on it being authoritative.

Output is **JSONL** (one object per line) by default: lossless for nested fields
(per-component scores), append/stream friendly, and readable by ``jq``/DuckDB/
pandas. ``--format csv`` emits a flattened view for spreadsheets.

    eab index                 # -> runs/index.jsonl
    eab index --format csv    # -> runs/index.csv
"""

from __future__ import annotations

import csv
import glob
import json
from datetime import datetime
from pathlib import Path

from . import trajectory as tj
from .runs import parse_job_dir, read_json

COMPONENTS = ("access_pattern", "service_discovery", "representation",
              "efficiency", "validation")


def load_roster() -> dict[str, str]:
    """{litellm_model: roster_id}, to map a served model name back to its id."""
    try:
        import yaml
        data = yaml.safe_load((tj.REPO_ROOT / "experiments" / "models.yaml").read_text())
        return {spec["litellm_model"]: mid
                for mid, spec in (data.get("models") or {}).items()
                if spec and spec.get("litellm_model")}
    except Exception:
        return {}


def load_sampling() -> dict:
    """Sampling defaults from experiments/models.yaml."""
    try:
        import yaml
        data = yaml.safe_load((tj.REPO_ROOT / "experiments" / "models.yaml").read_text())
        return (data.get("defaults") or {}).get("sampling") or {}
    except Exception:
        return {}


def _served(model_name: str) -> str:
    """Strip the provider prefix from a served model name."""
    return model_name.split("/", 1)[-1] if model_name else ""


def _classify(reward: float | None, exc: str) -> str:
    """Map (reward, exception) to solved|partial|fail|timeout|error."""
    if exc:
        return "timeout" if "Timeout" in exc else "error"
    if reward is None:
        return "error"
    if reward >= 0.999:
        return "solved"
    if reward > 0:
        return "partial"
    return "fail"


def _rel(path: Path) -> str:
    """Path relative to the repo root (or absolute if outside)."""
    try:
        return str(path.relative_to(tj.REPO_ROOT))
    except ValueError:
        return str(path)


def _duration(start: str | None, end: str | None) -> float | None:
    """Seconds between two ISO timestamps (None if unparseable)."""
    try:
        s = datetime.fromisoformat((start or "").replace("Z", "+00:00"))
        e = datetime.fromisoformat((end or "").replace("Z", "+00:00"))
        return round((e - s).total_seconds(), 1)
    except Exception:
        return None


def index_records(runs_dir: Path | None = None) -> list[dict]:
    """Build one flat metadata record per trial from the run tree."""
    runs_dir = Path(runs_dir or tj.RUNS_DIR)
    roster = load_roster()
    try:
        from .runconfig import load_manifest_names, run_name_for_stamp
        names = load_manifest_names()
    except Exception:
        names = {}
    records: list[dict] = []
    for job in sorted(glob.glob(str(runs_dir / "eab-*"))):
        jd = Path(job)
        ref = parse_job_dir(jd.name)
        condition, stamp = ref.condition, ref.stamp
        for res in sorted(glob.glob(str(jd / "*" / "result.json"))):
            trial_dir = Path(res).parent
            j = read_json(Path(res))
            cfg = j.get("config", {})
            agent = cfg.get("agent", {})
            served = _served(agent.get("model_name", ""))
            model = roster.get(served, served)
            task = Path((cfg.get("task") or {}).get("path", "") or "").name
            harness = agent.get("name", "")
            exc = (j.get("exception_info") or {}).get("exception_type", "")
            reward = read_json(trial_dir / "verifier" / "reward.json")
            ar = j.get("agent_result") or {}
            traj = trial_dir / "agent" / "trajectory.json"
            fm = (read_json(traj).get("final_metrics") or {})
            r = reward.get("reward")
            records.append({
                "task": task, "model": model, "harness": harness,
                "condition": condition, "stamp": stamp,
                "run_name": run_name_for_stamp(stamp, names),
                "trial": trial_dir.name,
                "status": _classify(r, exc), "reward": r, "exception": exc,
                "components": {c: reward.get(c) for c in COMPONENTS},
                "n_input_tokens": ar.get("n_input_tokens"),
                "n_output_tokens": ar.get("n_output_tokens"),
                "n_cache_tokens": ar.get("n_cache_tokens"),
                "cost_usd": ar.get("cost_usd"),
                "steps": fm.get("total_steps"),
                "started_at": j.get("started_at"), "finished_at": j.get("finished_at"),
                "duration_sec": _duration(j.get("started_at"), j.get("finished_at")),
                "run_dir": _rel(trial_dir),
                "trajectory": _rel(traj) if traj.exists() else None,
                "reward_path": _rel(trial_dir / "verifier" / "reward.json"),
                "details_path": _rel(trial_dir / "verifier" / "details.json"),
                "result_path": _rel(trial_dir / "result.json"),
            })
    records.sort(key=lambda r: (r["stamp"], r["model"], r["condition"], r["task"]))
    return records


def write_index(records: list[dict], out: Path, fmt: str = "jsonl") -> Path:
    """Write records as jsonl (default), csv (flattened) or json."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        out.write_text(json.dumps(records, indent=2, default=str) + "\n")
    elif fmt == "csv":
        cols = ["task", "model", "harness", "condition", "stamp", "run_name", "trial",
                "status", "reward", *COMPONENTS, "n_input_tokens", "n_output_tokens",
                "n_cache_tokens", "cost_usd", "steps", "started_at", "finished_at",
                "duration_sec", "exception", "trajectory", "reward_path",
                "details_path", "result_path", "run_dir"]
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in records:
                w.writerow({**r, **(r.get("components") or {})})
    else:  # jsonl
        with out.open("w") as fh:
            for r in records:
                fh.write(json.dumps(r, default=str) + "\n")
    return out
