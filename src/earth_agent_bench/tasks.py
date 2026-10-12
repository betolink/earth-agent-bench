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


def render_instruction(task: Task) -> str:
    """Render a task's instruction.md from its definition.

    The dataset(s) the agent must use are stated explicitly (short_name +
    concept_id) so the task tests *access-pattern* choice, not collection
    discovery — collection selection is handled by the project's semantic
    discovery part, which this benchmark does not cover.
    """
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

    datasets = [c for c in task.collections if c.tier == "preferred"] or list(task.collections)
    if datasets:
        lines += ["", "## Datasets to use"]
        lines.append("Use the following dataset(s) — this is the required collection;")
        lines.append("do not search for alternatives. Resolve access via the CMR concept_id:")
        for collection in datasets:
            cid = f" (concept_id: {collection.concept_id})" if collection.concept_id else ""
            lines.append(f"- {collection.short_name}{cid}")

    lines += [
        "",
        "Produce the output artifact. Choose the best access service and pattern for",
        "the dataset(s) above; justify your access choice in the workflow.",
        "",
        "## Execution policy (this environment runs OUTSIDE AWS)",
        "- Direct S3 / cloud-native direct access is NOT available; always use HTTPS.",
        "- Do NOT retry the same access service more than twice. On the second",
        "  failure, move to the next acceptable pattern (e.g. Harmony -> OPeNDAP ->",
        "  DMR++ -> Giovanni) instead of repeating the same call.",
        "- Be decisive: if no service succeeds within your budget, write your best",
        "  answer and the required access summary, then stop. Do not loop.",
    ]
    return "\n".join(lines)
