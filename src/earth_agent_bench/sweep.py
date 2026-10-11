"""Batch sweep: expand tasks x models x harnesses x conditions and run each cell."""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

from .models import resolve_conditions, resolve_harnesses, resolve_models
from .runner import RunSpec, execute

REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_tasks(selection: str) -> list[Path]:
    """Expand a comma-separated list of paths / dirs / globs into task files.

    'all' expands to the benchmark suite plus the eval suite.
    """
    tokens = [t.strip() for t in selection.split(",") if t.strip()]
    if tokens == ["all"]:
        tokens = ["benchmark/tasks", "experiments/evals/tasks"]

    paths: list[Path] = []
    for token in tokens:
        if any(c in token for c in "*?["):
            matches = [Path(m) for m in glob.glob(token, recursive=True)]
        else:
            matches = [Path(token)]
        for match in matches:
            if match.is_dir():
                paths.extend(sorted(match.rglob("*.md")))
                paths.extend(sorted(match.rglob("*.yaml")))
            elif match.is_file():
                paths.append(match)

    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    if not ordered:
        raise SystemExit(f"no tasks matched '{selection}'")
    return ordered


@dataclass
class SweepSpec:
    """A sweep over models x harnesses x conditions."""
    tasks: str
    models: str = "all"
    harnesses: str = "all"
    conditions: str = "all"
    trial: int = 1
    runs_root: Path = REPO_ROOT / "runs"
    dry_run: bool = False
    continue_on_error: bool = True
    timeout_s: int = 600


def run_sweep(spec: SweepSpec) -> int:
    """Execute a SweepSpec, returning per-run results."""
    tasks = resolve_tasks(spec.tasks)
    models = resolve_models(spec.models)
    harnesses = resolve_harnesses(spec.harnesses)
    conditions = resolve_conditions(spec.conditions)

    total = len(tasks) * len(models) * len(harnesses) * len(conditions)
    print(f"sweep: {len(tasks)} tasks x {len(models)} models x "
          f"{len(harnesses)} harnesses x {len(conditions)} conditions = {total} runs")

    code = 0
    for task in tasks:
        for model in models:
            for harness in harnesses:
                for condition in conditions:
                    rs = RunSpec(
                        task_path=task, model_id=model, harness=harness,
                        condition=condition, trial=spec.trial, runs_root=spec.runs_root,
                        timeout_s=spec.timeout_s,
                    )
                    rc = execute(rs, dry_run=spec.dry_run)
                    code = rc or code
                    if rc != 0 and not spec.continue_on_error:
                        return code
    return code
