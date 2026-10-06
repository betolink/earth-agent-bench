"""Generate Harbor task packages from benchmark and eval tasks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..evals import EvalGold, load_suite
from ..tasks import load_task, render_instruction
from ..wiring import mcp_servers_for, ready_mcp_urls, skills_mounted
from .config import DEFAULT_OUT, EVAL_SUITE, RUNTIME_DIR, skills_env_dir

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

EVAL_ABS_NOTE = "\n\nWrite the final value to `/app/output/answer.txt` (absolute path)."


def find_gold(task_id: str) -> EvalGold:
    for gold in load_suite(EVAL_SUITE):
        if gold.task_id == task_id:
            return gold
    raise SystemExit(f"eval task '{task_id}' not found in {EVAL_SUITE}")


def _describe(task_path: Path, is_eval: bool) -> str:
    if is_eval:
        return f"Correctness eval: {task_path.stem}"
    return load_task(task_path).title


def _render_task_toml(task_id: str, description: str, condition: str) -> str:
    lines = [
        'schema_version = "1.4"',
        "",
        "[task]",
        f'name = "earth-agent-bench/{task_id}"',
        'version = "1.0.0"',
        f"description = {json.dumps(description)}",
        "",
        "[agent]",
        "timeout_sec = 600.0",
        "",
        "[verifier]",
        "timeout_sec = 600.0",
        "",
        "[environment]",
        'network_mode = "public"',
        "build_timeout_sec = 1800.0",
    ]
    if skills_mounted(condition):
        lines.append(f'skills_dir = "{skills_env_dir()}"')

    for name, url in ready_mcp_urls(mcp_servers_for(condition)).items():
        lines += [
            "",
            "[[environment.mcp_servers]]",
            f'name = "{name}"',
            'transport = "streamable-http"',
            f'url = "{url}"',
        ]

    lines += [
        "",
        "[environment.env]",
        'EARTHDATA_USERNAME = "${EARTHDATA_USERNAME:-}"',
        'EARTHDATA_PASSWORD = "${EARTHDATA_PASSWORD:-}"',
        'EARTHDATA_TOKEN = "${EARTHDATA_TOKEN:-}"',
    ]
    return "\n".join(lines) + "\n"


def _vendor_benchmark(tests: Path) -> None:
    src = Path(__file__).resolve().parents[1]
    dest = tests / "earth_agent_bench"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "__init__.py").write_text(VENDOR_INIT)
    shutil.copy(RUNTIME_DIR / "harbor_verify.py", dest / "harbor_verify.py")
    for name in BENCHMARK_VENDOR:
        shutil.copy(src / name, dest / name)
    scoring = dest / "scoring"
    scoring.mkdir()
    for path in sorted((src / "scoring").glob("*.py")):
        shutil.copy(path, scoring / path.name)


def _vendor_eval(tests: Path) -> None:
    src = Path(__file__).resolve().parents[1]
    dest = tests / "earth_agent_bench"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "__init__.py").write_text(VENDOR_INIT)
    shutil.copy(RUNTIME_DIR / "harbor_verify.py", dest / "harbor_verify.py")
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
        instruction = task_path.read_text().rstrip() + EVAL_ABS_NOTE + "\n"
        shutil.copy(RUNTIME_DIR / "verify_eval.py", tests / "verify.py")
        (tests / "gold.json").write_text(find_gold(task_id).model_dump_json(indent=2))
        _vendor_eval(tests)
    else:
        instruction = render_instruction(load_task(task_path)) + HARBOR_OUTPUT_CONTRACT
        shutil.copy(RUNTIME_DIR / "verify_benchmark.py", tests / "verify.py")
        shutil.copy(task_path, tests / "task.yaml")
        _vendor_benchmark(tests)

    (package / "instruction.md").write_text(instruction.rstrip() + "\n")
    (package / "task.toml").write_text(
        _render_task_toml(task_id, _describe(task_path, is_eval), condition)
    )
    return package
