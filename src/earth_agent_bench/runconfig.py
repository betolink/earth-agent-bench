"""Resolve the benchmark run config (which models/harnesses/conditions/tasks).

Precedence: environment (EAB_MODELS, EAB_HARNESSES, EAB_CONDITIONS, EAB_TASKS,
EAB_TRIALS) overrides `experiments/run.yaml`, which overrides built-in defaults.
Model ids are validated against the roster in `experiments/models.yaml`.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_YAML = REPO_ROOT / "experiments" / "run.yaml"
MODELS_YAML = REPO_ROOT / "experiments" / "models.yaml"
CONDITIONS_YAML = REPO_ROOT / "experiments" / "conditions.yaml"
TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"


def _csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def load_run_config() -> dict:
    cfg = _load(RUN_YAML)
    roster = _load(MODELS_YAML).get("models", {})
    conditions_all = _load(CONDITIONS_YAML).get("order", [])
    name = os.environ.get("EAB_RUN_NAME") or cfg.get("name", "eab-full")
    models = _csv(os.environ.get("EAB_MODELS", "")) or list(cfg.get("models", []))
    harnesses = _csv(os.environ.get("EAB_HARNESSES", "")) or list(cfg.get("harnesses", []))
    conds = (_csv(os.environ.get("EAB_CONDITIONS", "")) or list(cfg.get("conditions", []))
             or list(conditions_all))
    tasks = os.environ.get("EAB_TASKS") or cfg.get("tasks", "all")
    trials = int(os.environ.get("EAB_TRIALS", cfg.get("trials", 1)))
    concurrency = int(os.environ.get("EAB_CONCURRENCY", cfg.get("concurrency", 1)))
    return {
        "name": name,
        "models": models,
        "harnesses": harnesses,
        "conditions": conds,
        "tasks": tasks,
        "trials": trials,
        "concurrency": concurrency,
        "roster": sorted(roster),
        "available_conditions": list(conditions_all),
        "unknown_models": [m for m in models if m not in roster],
    }


# --------------------------------------------------------------------------- #
# run manifest — a named record of an experiment (name -> stance -> config)

MANIFESTS_DIR = REPO_ROOT / "runs" / "manifests"


def write_manifest(cfg: dict, stamp: str, **extra) -> Path:
    """Write runs/manifests/<name>-<stamp>.json binding a run name to its config."""
    import datetime
    import json
    import subprocess
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    manifest = {
        "name": cfg.get("name"),
        "stamp": stamp,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": sha,
        "models": cfg.get("models"),
        "harnesses": cfg.get("harnesses"),
        "conditions": cfg.get("conditions"),
        "tasks": cfg.get("tasks"),
        "trials": cfg.get("trials"),
        "concurrency": cfg.get("concurrency"),
        **extra,
    }
    path = MANIFESTS_DIR / f"{cfg.get('name', 'eab-full')}-{stamp}.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def load_manifest_names() -> dict[str, str]:
    """{stamp: name} from all manifests (for attributing cells to an experiment)."""
    import glob
    import json
    out: dict[str, str] = {}
    for p in glob.glob(str(MANIFESTS_DIR / "*.json")):
        try:
            j = json.loads(Path(p).read_text())
            if j.get("stamp"):
                out[j["stamp"]] = j.get("name", "")
        except Exception:
            continue
    return out


def resolve_tasks(sel) -> list[Path]:
    all_tasks = sorted(TASKS_DIR.rglob("*.yaml"))
    if sel in ("all", None, ""):
        return all_tasks
    if isinstance(sel, str):
        wanted = _csv(sel)
    else:
        wanted = list(sel)
    if not wanted or "all" in wanted:
        return all_tasks
    out = [p for p in all_tasks if p.stem in wanted or any(w in str(p) for w in wanted)]
    return out
