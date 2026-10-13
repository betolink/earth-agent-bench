from __future__ import annotations

from pathlib import Path

import yaml

from .schemas import Task

DEFAULT_TASKS_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "tasks"


def load_task(path: str | Path) -> Task:
    """Load a grounded task YAML into a Task model."""
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f)
    data.setdefault("task_id", _derive_task_id(path))
    return Task.model_validate(data)


def load_all(tasks_dir: str | Path = DEFAULT_TASKS_DIR) -> list[Task]:
    """Load every task YAML under a directory."""
    tasks_dir = Path(tasks_dir)
    tasks = []
    for path in sorted(tasks_dir.rglob("*.yaml")):
        tasks.append(load_task(path))
    return tasks


def _derive_task_id(path: Path) -> str:
    """Derive a task id from its path."""
    relative = path.with_suffix("")
    return "/".join(relative.parts[-3:])


def _demo_scope_text(req) -> str:
    """Human description of the executable demo slice."""
    ds = req.demo_scope
    if ds is None:
        return "the smallest slice that shows the route (one day / a couple of granules)"
    if ds.note:
        return ds.note
    parts = []
    if ds.days:
        parts.append(f"{ds.days} day(s)")
    if ds.granules:
        parts.append(f"{ds.granules} granule(s)")
    if ds.bbox:
        parts.append(f"bbox {ds.bbox}")
    return ", ".join(parts) or "the smallest slice that shows the route"


def render_instruction(task: Task) -> str:
    """Render the agent-facing instruction.

    The goal is the access **code** (``access.py``), not the science: run it once
    on a small slice to prove the route. ``kind: daily`` produces the real result.
    """
    req = task.access_requirement
    bbox = req.spatial_extent.coordinates
    variables = ", ".join(req.variables_of_interest)
    datasets = [c for c in task.collections if c.tier == "preferred"] or list(task.collections)
    dataset_lines = [
        f"- {c.short_name}" + (f" (concept_id: {c.concept_id})" if c.concept_id else "")
        for c in datasets
    ]
    tail = f"output: {req.output_format}"
    if task.validation.units:
        tail += f"; units: {task.validation.units}"

    if req.kind == "daily":
        goal = ("**Goal — the deliverable is the code.** Write `access.py` that gets the "
                "data the best way; run it to produce the result for the single day/region. "
                "We grade the access code, not the science.")
        steps = [
            "1. Write `access.py`.",
            "2. Run it and write the result to `/app/output/`.",
        ]
        slice_line = (f"**Target.** bbox {bbox}; "
                      f"{req.temporal_extent.start} to {req.temporal_extent.end}; "
                      f"variables: {variables}; {tail}.")
    else:
        goal = ("**Goal — the deliverable is the code, not the science.** Write `access.py` "
                "that gets the data the best way, and run it once on a small slice to prove "
                "the route. We grade the access code, not the computed result.")
        steps = [
            "1. Write `access.py`.",
            "2. Run it once on a small slice — write the demo output to `/app/output/`. "
            "Do NOT process the full window.",
        ]
        slice_line = (f"**Slice.** bbox {bbox}; {_demo_scope_text(req)}; "
                      f"variables: {variables}; {tail}.")

    return "\n".join([
        f"# {task.title}",
        "",
        req.description,
        "",
        goal,
        "",
        "**Dataset(s):**",
        *dataset_lines,
        "",
        "**Steps:**",
        *steps,
        "- Write `/app/output/access_summary.json`: "
        '{"collections": ["SHORT_NAME"], "access_services_used": ["<service>"], '
        '"bytes_read_estimate": 0, "route_notes": "why you picked this route"}.',
        "",
        slice_line,
        "",
        "**Access.** Use earthaccess for everything (`earthaccess.login()` takes no "
        "arguments) — do NOT probe the raw CMR API or fetch granule URLs directly.",
        "",
        "**Skills.** If your environment provides skills, read the relevant ones first.",
    ])
