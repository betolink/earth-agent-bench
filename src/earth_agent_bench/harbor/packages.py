"""Generate Harbor task packages from benchmark and eval tasks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..evals import EVAL_OUTPUT_NOTE, EvalGold, load_suite, render_eval_instruction
from ..tasks import load_task, render_instruction
from ..wiring import mcp_servers_for, ready_mcp_urls, skills_mounted
from .config import (
    DEFAULT_OUT,
    EVAL_SUITE,
    RUNTIME_DIR,
    agent_timeout_sec,
    artifact_sources,
    instruction_access_policy,
    resources,
    skills_env_dir,
    verifier_environment_mode,
    verifier_timeout_sec,
)

VENDOR_INIT = '"""Vendored earth_agent_bench modules for the Harbor verifier."""\n'
BENCHMARK_VENDOR = ("schemas.py", "patterns.py", "tasks.py")

# Harbor instructions use an explicit absolute output path: agents otherwise
# resolve `./output/` against varying roots (/app, /home/user, /). The verifier
# still searches all of them.
HARBOR_OUTPUT_CONTRACT = """

## Output contract

- Write all artifacts to `/app/output/` (absolute path).
- Write `/app/output/access_summary.json` describing how data were accessed:

```json
{
  "collections": ["SHORT_NAME"],
  "access_services_used": ["harmony", "opendap", "virtualize"],
  "bytes_read_estimate": 0,
  "pattern_notes": "one sentence justifying the access choice"
}
```

- Do not modify `instruction.md`.
"""

# Re-exported for callers that referenced the old constant name.
EVAL_ABS_NOTE = EVAL_OUTPUT_NOTE


def find_gold(task_id: str) -> EvalGold:
    """Find the gold-standard file for a task, if present."""
    for gold in load_suite(EVAL_SUITE):
        if gold.task_id == task_id:
            return gold
    raise SystemExit(f"eval task '{task_id}' not found in {EVAL_SUITE}")


def _describe(task_path: Path, is_eval: bool) -> str:
    """Human description for a task package (eval vs grounded)."""
    if is_eval:
        return f"Correctness eval: {task_path.stem}"
    return load_task(task_path).title


def _toml_value(value) -> str:
    """Render a scalar or flat list as a TOML value."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value))


def _render_table(name: str, fields: dict) -> list[str]:
    """Render a TOML table, skipping None/empty values."""
    rendered = [
        f"{key} = {_toml_value(value)}"
        for key, value in fields.items()
        if value is not None and value != [] and value != ""
    ]
    if not rendered:
        return []
    return ["", f"[{name}]", *rendered]


def _benchmark_metadata(task) -> dict:
    """Flat interoperability metadata for a grounded benchmark task."""
    preferred = [c for c in task.collections if c.tier == "preferred"] or list(task.collections)
    labels = task.labels
    return {
        "suite": "benchmark",
        "task_id": task.task_id,
        "sphere": task.science_sphere,
        "kind": task.access_requirement.kind,
        "data_type": labels.data_type,
        "processing_level": labels.processing_level,
        "length_class": labels.length_class,
        "infeasible": labels.infeasible,
        "difficulty": labels.difficulty,
        "access_pattern_gold": list(task.gold.primary_patterns),
        "acceptable_patterns": list(task.gold.acceptable_patterns),
        "collections": [c.short_name for c in preferred],
        "concept_ids": [c.concept_id for c in preferred if c.concept_id],
        "demo_days": (task.access_requirement.demo_scope.days
                      if task.access_requirement.demo_scope else None),
        "demo_granules": (task.access_requirement.demo_scope.granules
                          if task.access_requirement.demo_scope else None),
    }


def _evaluation_metadata(gold) -> dict:
    """Flat interoperability metadata for a correctness eval task."""
    return {
        "suite": "correctness",
        "task_id": gold.task_id,
        "answer_type": gold.answer_type,
        "pinned": bool(gold.pinned),
        "infeasible": False,
    }


def _render_task_toml(
    task_id: str,
    description: str,
    condition: str,
    metadata: dict,
    keywords: list[str],
    source: str,
) -> str:
    """Render the generated task.toml (task, metadata, artifacts, env wiring)."""
    lines = [
        'schema_version = "1.4"',
        f"source = {_toml_value(source)}",
        "",
        "[task]",
        f'name = "earth-agent-bench/{task_id}"',
        'version = "1.0.0"',
        f"description = {json.dumps(description)}",
        'authors = [{ name = "earth-agent-bench contributors" }]',
        f"keywords = {_toml_value(keywords)}",
        "",
        "[metadata]",
    ]
    lines += [
        f"{key} = {_toml_value(value)}"
        for key, value in metadata.items()
        if value is not None and value != []
    ]
    lines += _render_table("agent", {"timeout_sec": agent_timeout_sec()})
    lines += _render_table("verifier", {
        "timeout_sec": verifier_timeout_sec(),
        "environment_mode": verifier_environment_mode(),
    })

    environment = {
        "network_mode": "public",
        "build_timeout_sec": 1800.0,
        "cpus": resources().get("cpus"),
        "memory_mb": resources().get("memory_mb"),
        "storage_mb": resources().get("storage_mb"),
        "skills_dir": skills_env_dir() if skills_mounted(condition) else None,
    }
    lines += _render_table("environment", environment)

    for name, url in ready_mcp_urls(mcp_servers_for(condition)).items():
        lines += [
            "",
            "[[environment.mcp_servers]]",
            f'name = "{name}"',
            'transport = "streamable-http"',
            f'url = "{url}"',
        ]

    lines += _render_table("environment.env", {
        "EARTHDATA_USERNAME": "${EARTHDATA_USERNAME:-}",
        "EARTHDATA_PASSWORD": "${EARTHDATA_PASSWORD:-}",
        "EARTHDATA_TOKEN": "${EARTHDATA_TOKEN:-}",
    })

    for artifact in artifact_sources():
        lines += ["", "[[artifacts]]", f"source = {_toml_value(artifact)}"]

    return "\n".join(lines) + "\n"


def _vendor_runtime(dest: Path) -> None:
    """Copy the shared runtime modules the verifiers import."""
    for name in ("harbor_verify.py", "executor.py", "profiler.py"):
        shutil.copy(RUNTIME_DIR / name, dest / name)


def _vendor_benchmark(tests: Path) -> None:
    """Copy the benchmark package + runtime modules into the task's tests dir."""
    src = Path(__file__).resolve().parents[1]
    dest = tests / "earth_agent_bench"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "__init__.py").write_text(VENDOR_INIT)
    _vendor_runtime(dest)
    for name in BENCHMARK_VENDOR:
        shutil.copy(src / name, dest / name)
    scoring = dest / "scoring"
    scoring.mkdir()
    for path in sorted((src / "scoring").glob("*.py")):
        shutil.copy(path, scoring / path.name)


def _vendor_eval(tests: Path) -> None:
    """Vendor the eval suite into the task package."""
    src = Path(__file__).resolve().parents[1]
    dest = tests / "earth_agent_bench"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "__init__.py").write_text(VENDOR_INIT)
    _vendor_runtime(dest)
    shutil.copy(src / "evals.py", dest / "evals.py")


def generate_package(
    task_path: str | Path,
    condition: str = "baseline",
    out_root: Path = DEFAULT_OUT,
) -> Path:
    """Generate a Harbor task package for one task under ``out_root``."""
    task_path = Path(task_path)
    if not task_path.is_file():
        raise SystemExit(f"task not found: {task_path}")

    is_eval = task_path.suffix == ".md"
    task_id = task_path.stem
    package = out_root / task_id
    if package.exists():
        shutil.rmtree(package)

    environment = package / "environment"
    tests = package / "tests"
    solution = package / "solution"
    for directory in (environment, tests, solution):
        directory.mkdir(parents=True)

    shutil.copy(RUNTIME_DIR / "Dockerfile", environment / "Dockerfile")
    shutil.copy(
        RUNTIME_DIR / "agent-requirements.txt", environment / "agent-requirements.txt"
    )
    shutil.copy(RUNTIME_DIR / "eab_instrument.py", environment / "eab_instrument.py")
    shutil.copy(RUNTIME_DIR / "test.sh", tests / "test.sh")
    shutil.copy(RUNTIME_DIR / "solve.sh", solution / "solve.sh")

    if is_eval:
        instruction = render_eval_instruction(task_path)
        shutil.copy(RUNTIME_DIR / "verify_eval.py", tests / "verify.py")
        gold = find_gold(task_id)
        (tests / "gold.json").write_text(gold.model_dump_json(indent=2))
        _vendor_eval(tests)
        metadata = _evaluation_metadata(gold)
        keywords = ["earthdata", "correctness", "eval", str(gold.answer_type)]
        source = f"benchmark/tasks/correctness/{task_path.name}"
    else:
        task = load_task(task_path)
        instruction = render_instruction(task, access_policy=instruction_access_policy())
        shutil.copy(RUNTIME_DIR / "verify_benchmark.py", tests / "verify.py")
        shutil.copy(task_path, tests / "task.yaml")
        _vendor_benchmark(tests)
        metadata = _benchmark_metadata(task)
        keywords = ["earthdata", "access-pattern", task.science_sphere,
                    task.access_requirement.kind]
        source = f"benchmark/tasks/access-pattern/{task.task_id}.yaml"

    (package / "instruction.md").write_text(instruction.rstrip() + "\n")
    (package / "task.toml").write_text(
        _render_task_toml(
            task_id, _describe(task_path, is_eval), condition, metadata, keywords, source
        )
    )
    return package
