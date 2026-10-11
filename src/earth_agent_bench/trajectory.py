"""Locate and dump a trial's trajectory/artifacts for one (model, harness, task).

Harbor records, per trial, everything needed to reconstruct what happened:

  agent/trajectory.json            the trajectory, ATIF v1.7 (steps[], final_metrics)
  agent/<harness>.txt              raw terminal transcript
  agent/<harness>/sessions/*.jsonl harness session log
  verifier/reward.json             score + per-component (access_pattern, ...)
  verifier/details.json            observed patterns / best-available / gap reason
  verifier/test-stdout.txt         verifier stdout (failure signatures)
  result.json                      full trial record (config, timings, step_results)

This module resolves those files from the ``runs/harbor/eab-<task>-<model>-
<harness>-<cond>-<stamp>/<trial>/`` tree so any cell can be inspected, e.g.::

    eab trajectory --task a3 --model tiel-coder-35b --harness pi > traj.json
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = Path(os.environ.get("EAB_RUNS_DIR", REPO_ROOT / "runs" / "harbor"))
TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"
_STAMP = re.compile(r"-(\d{8}-\d{6})$")

# named formats -> path relative to the trial dir
ARTIFACTS = {
    "atif": "agent/trajectory.json",
    "trajectory": "agent/trajectory.json",
    "result": "result.json",
    "reward": "verifier/reward.json",
    "details": "verifier/details.json",
    "stdout": "verifier/test-stdout.txt",
}
RAW = {"raw", "txt"}          # agent/<harness>.txt
SESSIONS = {"session", "jsonl"}  # agent/<harness>/sessions/*.jsonl


@dataclass
class Trial:
    job: str          # eab-<task>-<model>-<harness>-<cond>-<stamp>
    dir: Path         # .../<trial-name>
    condition: str
    stamp: str

    @property
    def name(self) -> str:
        return self.dir.name


def resolve_task_id(task: str) -> str:
    """Map a task id or unique prefix ('a3') to a full id ('a3-maiac-...')."""
    ids = sorted(p.stem for p in TASKS_DIR.rglob("*.yaml"))
    if task in ids:
        return task
    hits = [i for i in ids if i.startswith(task + "-") or i == task]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LookupError(f"no task matches {task!r}")
    raise LookupError(f"ambiguous task {task!r}: {', '.join(hits)}")


def _condition(job: str, task: str, model: str, harness: str) -> str:
    prefix = f"eab-{task}-{model}-{harness}-"
    tail = job[len(prefix):] if job.startswith(prefix) else job
    return _STAMP.sub("", tail)


def find_trials(task: str, model: str, harness: str,
                condition: str | None = None) -> list[Trial]:
    """Trials matching (task, model, harness[, condition]), oldest -> newest."""
    pat = f"eab-{task}-{model}-{harness}"
    if condition:
        pat += f"-{condition}"
    pat += "-*"
    trials: list[Trial] = []
    for job in sorted(glob.glob(str(RUNS_DIR / pat))):
        job_name = Path(job).name
        stamp = (_STAMP.search(job_name).group(1)
                 if _STAMP.search(job_name) else "")
        cond = _condition(job_name, task, model, harness)
        for result in sorted(glob.glob(str(Path(job) / "*" / "result.json"))):
            trials.append(Trial(job_name, Path(result).parent, cond, stamp))
    trials.sort(key=lambda t: (t.stamp, t.name))
    return trials


def artifact(trial: Trial, fmt: str, harness: str) -> Path | None:
    """Resolve the requested artifact file inside a trial dir."""
    if fmt in ARTIFACTS:
        p = trial.dir / ARTIFACTS[fmt]
        return p if p.exists() else None
    if fmt in RAW:
        p = trial.dir / "agent" / f"{harness}.txt"
        if p.exists():
            return p
        hits = sorted(glob.glob(str(trial.dir / "agent" / "*.txt")))
        return Path(hits[-1]) if hits else None
    if fmt in SESSIONS:
        hits = sorted(glob.glob(str(trial.dir / "agent" / harness / "sessions" / "*.jsonl")))
        return Path(hits[-1]) if hits else None
    raise ValueError(f"unknown format {fmt!r}; choose from "
                     f"{', '.join(sorted(ARTIFACTS))}, raw, session")


def read_artifact(path: Path) -> object:
    """JSON artifacts load parsed (for pretty-dumping); everything else is text."""
    if path.suffix == ".json":
        try:
            return json.loads(path.read_text())
        except Exception:
            return path.read_text(errors="replace")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(errors="replace").splitlines() if line.strip()]
    return path.read_text(errors="replace")


def reward_of(trial: Trial) -> float | None:
    p = trial.dir / "verifier" / "reward.json"
    try:
        return float(json.loads(p.read_text()).get("reward"))
    except Exception:
        return None


def exception_of(trial: Trial) -> str:
    try:
        info = json.loads((trial.dir / "result.json").read_text()).get("exception_info") or {}
        return info.get("exception_type") or ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# metadata bundle
# --------------------------------------------------------------------------- #

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_conditions() -> dict:
    """The condition semantics (mcp/skills/improvement + wiring) from conditions.yaml."""
    try:
        import yaml
        return yaml.safe_load((REPO_ROOT / "experiments" / "conditions.yaml").read_text())
    except Exception:
        return {}


def _task_toml(task_id: str) -> dict:
    p = REPO_ROOT / "harbor" / "generated" / task_id / "task.toml"
    if not p.exists():
        return {}
    try:
        import tomllib
        return tomllib.loads(p.read_text())
    except Exception:
        return {}


def build_bundle(trial: Trial, task_id: str, model: str, harness: str,
                 include_trajectory: bool = True) -> dict:
    """Everything about one cell: run id, agent + params, condition/environment,
    the task instruction, metrics, verifier detail, and the ATIF trajectory."""
    res = _read_json(trial.dir / "result.json")
    cfg = res.get("config", {})
    agent = cfg.get("agent", {})
    info = res.get("agent_info", {})
    agent_result = res.get("agent_result", {})
    reward = _read_json(trial.dir / "verifier" / "reward.json")

    conds = load_conditions()
    cond_all = conds.get("conditions", {})
    wiring = conds.get("wiring", {})
    cond = {"name": trial.condition, **{k: v for k, v in (cond_all.get(trial.condition) or {}).items()}}

    traj_path = trial.dir / "agent" / "trajectory.json"
    traj = _read_json(traj_path) if (include_trajectory and traj_path.exists()) else None

    instruction = ""
    if traj:
        for step in traj.get("steps", []):
            if step.get("source") == "user" and step.get("message"):
                instruction = step["message"]
                break
    if not instruction:
        ip = REPO_ROOT / "harbor" / "generated" / task_id / "instruction.md"
        if ip.exists():
            instruction = ip.read_text()

    toml = _task_toml(task_id)
    exception = res.get("exception_info") or {}
    return {
        "run": {
            "task": task_id, "model": model, "harness": harness,
            "condition": trial.condition, "trial": trial.name, "stamp": trial.stamp,
            "started_at": res.get("started_at"), "finished_at": res.get("finished_at"),
            "exception": exception.get("exception_type"),
            "exception_message": exception.get("exception_message"),
        },
        "agent": {
            "name": agent.get("name", harness),
            "version": info.get("version"),
            "model_name": agent.get("model_name"),
            "provider": (info.get("model_info") or {}).get("provider"),
            "params": agent.get("kwargs", {}),
            "env": agent.get("env", {}),
            "skills_dir": agent.get("skills", []),
        },
        "condition": cond,
        "environment": {
            "mcp": cond.get("mcp"),
            "skills": cond.get("skills"),
            "improvement": cond.get("improvement"),
            "mcp_servers": wiring.get("mcp_servers", {}).get(trial.condition, []),
            "skills_mounted": wiring.get("skills_mounted", {}).get(trial.condition),
            "improvement_mounted": wiring.get("improvement_mounted", {}).get(trial.condition),
            "agent_timeout_sec": (toml.get("agent") or {}).get("timeout_sec"),
            "env_vars": list(((toml.get("environment") or {}).get("env") or {}).keys()),
        },
        "task": {
            "id": task_id,
            "name": (toml.get("task") or {}).get("name"),
            "description": (toml.get("task") or {}).get("description"),
            "instruction": instruction,
        },
        "metrics": {
            "reward": reward.get("reward"),
            "components": {k: v for k, v in reward.items() if k != "reward"},
            "n_input_tokens": agent_result.get("n_input_tokens"),
            "n_output_tokens": agent_result.get("n_output_tokens"),
            "n_cache_tokens": agent_result.get("n_cache_tokens"),
            "cost_usd": agent_result.get("cost_usd"),
        },
        "verifier": _read_json(trial.dir / "verifier" / "details.json"),
        "trajectory": traj,
    }

