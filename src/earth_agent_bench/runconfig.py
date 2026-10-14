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
HARNESSES_YAML = REPO_ROOT / "experiments" / "harnesses.yaml"
TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"


def _csv(value: str) -> list[str]:
    """Split a comma-separated string into a trimmed, non-empty list."""
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _load(path: Path) -> dict:
    """Load a YAML file; return ``{}`` when it is missing."""
    return yaml.safe_load(path.read_text()) if path.exists() else {}


# --- shared accessors: the single source of truth for the benchmark matrix ---

def harness_ids() -> list[str]:
    """Harness ids from experiments/harnesses.yaml."""
    return list((_load(HARNESSES_YAML).get("harnesses") or {}).keys())


def condition_ids() -> list[str]:
    """Condition ids (in order) from experiments/conditions.yaml."""
    return list(_load(CONDITIONS_YAML).get("order", []))


def roster_ids() -> list[str]:
    """Model ids from experiments/models.yaml (the roster)."""
    return list(_load(MODELS_YAML).get("models", {}).keys())


def restricted_models(harness: str) -> set[str]:
    """Models a restricted harness is limited to (harnesses.yaml crossing.restricted)."""
    crossing = _load(HARNESSES_YAML).get("crossing") or {}
    entry = (crossing.get("restricted") or {}).get(harness) or {}
    return set(entry.get("models", []))


def task_ids() -> list[str]:
    """Task ids (yaml stems) from benchmark/tasks/."""
    return sorted(p.stem for p in TASKS_DIR.rglob("*.yaml"))


def load_run_config() -> dict:
    """Resolve the run matrix: env overrides > ``experiments/run.yaml`` > defaults.

    Returns a dict with ``name``, ``models``, ``harnesses``, ``conditions``,
    ``tasks``, ``trials``, ``concurrency``, the ``roster`` and any
    ``unknown_models`` (ids not present in ``experiments/models.yaml``).

    Example::

        cfg = load_run_config()          # honours EAB_MODELS / EAB_CONCURRENCY / …
        cfg["models"], cfg["conditions"]
    """
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


def resolve_run_stamp(name: str) -> str:
    """The stamp for a run *name* — deterministic, so `--name X` always maps to one run.

    If a manifest ``<name>-<stamp>.json`` exists, reuse its stamp (relaunching the
    same name resumes the same run); otherwise mint a fresh ``YYYYMMDD-HHMMSS``.
    """
    import datetime
    import glob
    import re
    stamps = []
    for p in glob.glob(str(MANIFESTS_DIR / f"{name}-*.json")):
        match = re.search(r"-(\d{8}-\d{6})\.json$", Path(p).name)
        if match:
            stamps.append(match.group(1))
    if stamps:
        return max(stamps)
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def run_name_for_stamp(stamp: str, names: dict[str, str] | None = None) -> str:
    """The run a cell's per-job stamp belongs to (the nearest preceding run stamp).

    Job dirs carry a per-job stamp (when the job ran), not the run stamp, so map a
    cell back to its run by the latest manifest stamp <= the cell's stamp.
    """
    names = load_manifest_names() if names is None else names
    prior = [s for s in names if s and s <= stamp]
    return names[max(prior)] if prior else ""


def resolve_run_tasks(sel) -> list[Path]:
    """Resolve the *run* task selection (run.yaml `tasks`) into benchmark task YAMLs.

    Distinct from `harbor.resolve.resolve_tasks` (which expands task *references*
    — paths/ids/aliases/globs — and includes the eval suite). This one is
    benchmark-only and drives the run matrix (`eab config`).
    """
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
