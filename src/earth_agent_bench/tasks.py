from __future__ import annotations

from pathlib import Path

import yaml

from .schemas import Task

DEFAULT_TASKS_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "tasks"


def load_task(path: str | Path) -> Task:
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f)
    data.setdefault("task_id", _derive_task_id(path))
    return Task.model_validate(data)


def load_all(tasks_dir: str | Path = DEFAULT_TASKS_DIR) -> list[Task]:
    tasks_dir = Path(tasks_dir)
    tasks = []
    for path in sorted(tasks_dir.rglob("*.yaml")):
        tasks.append(load_task(path))
    return tasks


def _derive_task_id(path: Path) -> str:
    relative = path.with_suffix("")
    return "/".join(relative.parts[-3:])


def render_instruction(task: Task) -> str:
    req = task.access_requirement
    bbox = req.spatial_extent.coordinates
    variables = ", ".join(req.variables_of_interest)
    lines = [
        f"# {task.title}",
        "",
        req.description,
        "",
        "## Requirement",
        f"- Spatial extent ({req.spatial_extent.type}): {bbox}",
        f"- Temporal extent: {req.temporal_extent.start} to {req.temporal_extent.end}",
        f"- Variables of interest: {variables}",
        f"- Output format: {req.output_format}",
    ]
    if task.validation.aggregation:
        lines.append(f"- Required aggregation: {task.validation.aggregation}")
    if task.validation.units:
        lines.append(f"- Expected units: {task.validation.units}")
    lines.append("")
    lines.append("Produce the output artifact. Choose access services and patterns for")
    lines.append("the collection(s) you select; justify your access choice in the workflow.")
    return "\n".join(lines)
