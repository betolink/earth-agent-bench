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
    """Render the agent-facing instruction (v2 contract: access code at demo scope).

    The deliverable is ``access.py`` run on a small demo slice — the task grades
    the *access pattern*, not the full science result. ``kind: daily`` is the one
    exception (the real result for a single day/region is the deliverable).
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
        f"- Kind: {req.kind}",
        f"- Spatial extent ({req.spatial_extent.type}): {bbox}",
        f"- Temporal extent (science window): {req.temporal_extent.start} to {req.temporal_extent.end}",
        f"- Variables of interest: {variables}",
        f"- Output format: {req.output_format}",
    ]
    if task.validation.aggregation:
        lines.append(f"- Required aggregation: {task.validation.aggregation}")
    if task.validation.units:
        lines.append(f"- Expected units: {task.validation.units}")
    lines.append(f"- Demo scope: {_demo_scope_text(req)}")

    datasets = [c for c in task.collections if c.tier == "preferred"] or list(task.collections)
    if datasets:
        lines += ["", "## Datasets to use"]
        lines.append("Use the following dataset(s) — this is the required collection;")
        lines.append("do not search for alternatives. Resolve access via the CMR concept_id:")
        for collection in datasets:
            cid = f" (concept_id: {collection.concept_id})" if collection.concept_id else ""
            lines.append(f"- {collection.short_name}{cid}")

    if req.kind == "daily":
        deliverable = [
            "## Deliverable",
            "1. Write `access.py` that obtains the data with the best access pattern.",
            "2. Run it and write the actual result for the single day / region asked.",
            "3. Write the access summary (pattern used, services found, bytes expected).",
        ]
    else:
        deliverable = [
            "## Deliverable",
            "1. Write `access.py` that obtains the data with the best access pattern.",
            "2. Run it on the SMALLEST scope that shows the pattern "
            f"({_demo_scope_text(req)}) and write the demo artifact.",
            "3. Write the access summary (pattern used, services found, bytes expected).",
            "Do NOT process the full time range — demonstrate the pattern, don't run the study.",
        ]

    lines += [
        "",
        *deliverable,
        "",
        "## Access policy (outside AWS; HTTPS only)",
        "- Use earthaccess for everything (login() takes no arguments; never raw CMR or",
        "  direct URL fetches — open() returns an authenticated file object).",
        "- Order: virtualize (DMR++ then native parser) → stream via open() (xarray/h5py)",
        "  → Harmony/OPeNDAP (async, last) → download.",
        "- Be decisive: one search, then act and write; do not loop or retry.",
        "",
        "## Skills",
        "If your environment provides skills, READ them before starting and use the",
        "ones relevant to this task.",
    ]
    return "\n".join(lines)
