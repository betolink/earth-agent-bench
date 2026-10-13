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
        return "the smallest slice that shows the pattern (one day / a couple of granules)"
    if ds.note:
        return ds.note
    parts = []
    if ds.days:
        parts.append(f"{ds.days} day(s)")
    if ds.granules:
        parts.append(f"{ds.granules} granule(s)")
    if ds.bbox:
        parts.append(f"bbox {ds.bbox}")
    return ", ".join(parts) or "the smallest slice that shows the pattern"


def render_instruction(task: Task) -> str:
    """Render the agent-facing instruction (tight v2: write + run ``access.py``).

    Leads with the dataset and the deliverable, then one target line and a short
    access policy. ``kind: daily`` writes the real result; otherwise the agent
    runs ``access.py`` once on a small demo slice — the task grades the *access
    pattern*, not the full science result.
    """
    req = task.access_requirement
    bbox = req.spatial_extent.coordinates
    variables = ", ".join(req.variables_of_interest)
    datasets = [c for c in task.collections if c.tier == "preferred"] or list(task.collections)
    dataset_lines = [
        f"- {c.short_name}" + (f" (concept_id: {c.concept_id})" if c.concept_id else "")
        for c in datasets
    ]
    target = [f"bbox {bbox}", f"{req.temporal_extent.start} to {req.temporal_extent.end}",
              f"variables: {variables}", f"output: {req.output_format}"]
    if task.validation.aggregation:
        target.insert(2, f"aggregation: {task.validation.aggregation}")
    if task.validation.units:
        target.append(f"units: {task.validation.units}")

    if req.kind == "daily":
        steps = [
            "1. `access.py` obtains the data with the best access pattern.",
            "2. Run it and write the actual result for the single day / region to `/app/output/`.",
        ]
        tail = []
    else:
        steps = [
            "1. `access.py` obtains the data with the best access pattern.",
            f"2. Run it once on the smallest slice that shows the pattern "
            f"({_demo_scope_text(req)}) — write the demo artifact to `/app/output/`.",
            "3. Do NOT process the full window — demonstrate the pattern, don't run the study.",
        ]
        tail = []

    return "\n".join([
        f"# {task.title}",
        "",
        req.description,
        "",
        "**Dataset (use exactly this — do not search for alternatives):**",
        *dataset_lines,
        "",
        "**Deliverable — write and run `access.py`:**",
        *steps,
        "- Write `/app/output/access_summary.json`: "
        '{"collections": ["SHORT_NAME"], "access_services_used": ["<service>"], '
        '"bytes_read_estimate": 0, "pattern_notes": "one sentence justifying the choice"}.',
        *tail,
        "",
        "**Access.** Use earthaccess for everything (`earthaccess.login()` takes no "
        "arguments) — do NOT probe the raw CMR API or fetch granule URLs directly.",
        "",
        f"**Target.** {'; '.join(target)}.",
        "",
        "**Skills.** If your environment provides skills, read the relevant ones first.",
    ])
