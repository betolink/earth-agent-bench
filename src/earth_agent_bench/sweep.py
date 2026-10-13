"""Batch sweep: expand tasks x models x harnesses x conditions and run each cell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .harbor.resolve import resolve_tasks
from .models import resolve_conditions, resolve_harnesses, resolve_models
from .runner import RunSpec, execute

REPO_ROOT = Path(__file__).resolve().parents[2]


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
