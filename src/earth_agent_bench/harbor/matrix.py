"""Resolve and execute the model × harness × condition × task matrix.

The master config is split by concern:

- ``experiments/models.yaml``  — who: the roster (local + API models)
- ``experiments/run.yaml``     — which: the selection to benchmark
- ``experiments/harnesses.yaml`` — runtime + crossing restrictions
- ``harbor/harbor.yaml``       — wiring (agent ids, gateway kwargs, budgets)

``resolve_selection`` reads that chain (env vars override ``run.yaml``), and
``run_matrix`` expands it into Harbor cells and executes them.
"""

from __future__ import annotations

from pathlib import Path

from ..models import resolve_conditions, resolve_harnesses, resolve_models
from ..runconfig import load_run_config, resolve_run_tasks, restricted_models
from .config import DEFAULT_JOBS, DEFAULT_OUT
from .jobs import run_harbor
from .resolve import resolve_tasks


def resolve_selection(
    models: str | None = None,
    harnesses: str | None = None,
    conditions: str | None = None,
    tasks: str | None = None,
    config: str | Path | None = None,
) -> dict:
    """Resolve the run selection (CLI args > env > run.yaml > defaults).

    ``tasks`` is left as the raw selection; call ``resolve_task_paths`` to turn it
    into task files. ``config`` selects an alternate run-config YAML.
    """
    cfg = load_run_config(config)
    return {
        "config": cfg,
        "models": models or ",".join(cfg["models"]),
        "harnesses": harnesses or ",".join(cfg["harnesses"]),
        "conditions": conditions or ",".join(cfg["conditions"]),
        "tasks": tasks,
    }


def resolve_task_paths(tasks: str | None, cfg: dict) -> list[Path]:
    """Task files for a matrix run.

    An explicit ``tasks`` argument expands like ``eab harbor run <refs>`` (ids,
    paths, aliases, globs, ``all`` = benchmark + eval). Omitting it uses
    ``run.yaml``'s selection, where ``all`` means the 18 grounded tasks.
    """
    if tasks is None:
        return resolve_run_tasks(cfg.get("tasks", "all"))
    return resolve_tasks(tasks)


def resolve_cells(
    models: str | list[str],
    harnesses: str | list[str],
    conditions: str | list[str],
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Expand a selection into cells, applying harness crossing restrictions.

    Returns ``(cells, skipped)`` where each cell is
    ``{model, harness, condition}`` and ``skipped`` lists model/harness pairs a
    restricted harness is not allowed to run.
    """
    model_ids = resolve_models(models)
    harness_ids = resolve_harnesses(harnesses)
    condition_ids = resolve_conditions(conditions)

    cells: list[dict] = []
    skipped: list[tuple[str, str]] = []
    for harness in harness_ids:
        allowed = restricted_models(harness)
        for model in model_ids:
            if allowed and model not in allowed:
                skipped.append((model, harness))
                continue
            for condition in condition_ids:
                cells.append({"model": model, "harness": harness, "condition": condition})
    return cells, skipped


def run_matrix(
    tasks: str | None = None,
    models: str | None = None,
    harnesses: str | None = None,
    conditions: str | None = None,
    config: str | Path | None = None,
    out: Path = DEFAULT_OUT,
    jobs_dir: Path = DEFAULT_JOBS,
    dry_run: bool = False,
    job_name: str | None = None,
    force: bool = False,
) -> int:
    """Execute every selected cell through Harbor; return a process exit code."""
    selection = resolve_selection(models, harnesses, conditions, tasks, config)
    task_paths = resolve_task_paths(selection["tasks"], selection["config"])
    cells, skipped = resolve_cells(
        selection["models"], selection["harnesses"], selection["conditions"]
    )

    for model, harness in skipped:
        print(f"[skip] {model} on {harness}: restricted crossing (harnesses.yaml)")

    total = len(task_paths) * len(cells)
    print(
        f"[matrix] {len(task_paths)} task(s) x {len(cells)} cell(s) = {total} job(s)"
        f"  (config: {selection['config'].get('config_path')})"
    )
    if not cells:
        raise SystemExit("no runnable cells: check the model/harness crossing rules")

    # A condition changes task.toml (skills/MCP wiring), so give each condition
    # its own package directory when more than one is selected. This keeps a
    # dry-run's printed commands accurate and lets sequential runs coexist.
    conditions_selected = {cell["condition"] for cell in cells}
    nest_by_condition = len(conditions_selected) > 1

    code = 0
    for task_path in task_paths:
        for cell in cells:
            cell_name = job_name
            if cell_name and len(cells) * len(task_paths) > 1:
                cell_name = f"{job_name}-{cell['model']}-{cell['harness']}-{cell['condition']}"
            cell_out = out / cell["condition"] if nest_by_condition else out
            code = (
                run_harbor(
                    task_path,
                    cell["model"],
                    cell["harness"],
                    cell["condition"],
                    cell_out,
                    jobs_dir,
                    dry_run,
                    job_name=cell_name,
                    force=force,
                )
                or code
            )
            if code != 0:
                return code
    return code
