"""Thin Harbor adapter.

Turns benchmark tasks into Harbor task packages and wraps the `harbor` CLI.

    eab harbor generate --tasks cryo-1,atmo-2
    eab harbor run --tasks cryo-1 --model tiel-coder-35b --harness opencode --dry-run

The generated package (harbor/generated/<task>/):
    instruction.md            agent-facing requirement + output contract
    AGENTS.md                 workspace rules (+ skills pointer when mounted)
    agent-requirements.txt    the agent-side Python stack
    environment/Dockerfile    workspace image (no secrets baked in)
    solution/solve.sh         expert reference placeholder (not given to agent)
    tests/                    verifier: vendored scorer + task gold YAML
    skills/, opencode.jsonc, config.toml, .mcp.json, pi.json   condition wiring

Credentials are injected at runtime via environment (harbor/harbor.yaml
pass_through_env) — never into images or the repo.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

from .runner import (
    AGENTS_MD,
    OUTPUT_CONTRACT,
    SKILLS_NOTE,
    _ready_mcp_urls,
    _skills_mounted,
    _write_claude_config,
    _write_codex_config,
    _write_opencode_config,
    _write_pi_config,
)
from .tasks import load_task, render_instruction

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"
HARBOR_DIR = REPO_ROOT / "harbor"
HARBOR_CONFIG = HARBOR_DIR / "harbor.yaml"
DEFAULT_OUT = HARBOR_DIR / "generated"

SPHERE_PREFIXES = {
    "atmo": "atmosphere", "a": "atmosphere",
    "cryo": "cryosphere", "c": "cryosphere",
    "bio": "biosphere", "b": "biosphere",
    "ocean": "ocean", "o": "ocean",
    "solid": "solid-earth", "se": "solid-earth", "s": "solid-earth",
    "land": "land-surface", "ls": "land-surface", "l": "land-surface",
}

VENDORED_MODULES = (
    "__init__.py", "schemas.py", "patterns.py", "tasks.py",
)

ENVIRONMENT_DOCKERFILE = """FROM python:3.12-slim

RUN apt-get update \\
    && apt-get install -y --no-install-recommends git ca-certificates curl \\
    && rm -rf /var/lib/apt/lists/*

COPY agent-requirements.txt /tmp/agent-requirements.txt
RUN pip install --no-cache-dir -r /tmp/agent-requirements.txt

RUN useradd -m agent
WORKDIR /app
USER agent
{extra}"""

TESTS_DOCKERFILE = """FROM python:3.12-slim

RUN pip install --no-cache-dir pydantic pyyaml

COPY earth_agent_bench /tests/earth_agent_bench
COPY verify.py run.sh task.yaml /tests/

ENTRYPOINT ["/tests/run.sh"]"""

RUN_SH = """#!/bin/bash
python /tests/verify.py --workspace /app --task /tests/task.yaml
"""

VERIFY_PY = '''"""Harbor verifier: classify the run, score it, emit evaluation.json."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from earth_agent_bench.schemas import RunObservation
from earth_agent_bench.scoring import score_run
from earth_agent_bench.scoring.service_discovery import SERVICE_ALIASES
from earth_agent_bench.tasks import load_task

CANONICAL_TO_PATTERN = {
    "virtual_zarr": "C1", "native_zarr": "C2", "cog": "C3",
    "harmony": "S1", "opendap": "S2", "opendap_cloud": "S3",
    "appeears": "S4", "giovanni": "S5",
    "filtered_download": "F1", "full_download": "M1",
}


def canonical(service: str):
    token = str(service).strip().lower()
    for name, aliases in SERVICE_ALIASES.items():
        if token in aliases:
            return name
    return token


def classify(services):
    patterns = []
    for service in services or []:
        pattern = CANONICAL_TO_PATTERN.get(canonical(service))
        if pattern and pattern not in patterns:
            patterns.append(pattern)
    return patterns


def dominant_pattern(patterns, tiers):
    for tier in ("best", "acceptable", "marginal"):
        for candidate in getattr(tiers, tier):
            if candidate in patterns:
                return candidate
    return patterns[0] if patterns else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    task = load_task(args.task)

    obs_path = workspace / "observation.json"
    if obs_path.exists():
        observation = RunObservation.model_validate(json.loads(obs_path.read_text()))
    else:
        summary_path = workspace / "output" / "access_summary.json"
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        patterns = classify(summary.get("access_services_used"))
        output_dir = workspace / "output"
        artifacts = list(output_dir.glob("artifact*")) if output_dir.exists() else []
        observation = RunObservation(
            task_id=task.task_id,
            observed_patterns=[dominant_pattern(patterns, task.pattern_tiers)],
            collection_short_names=summary.get("collections", []),
            discovered_services=summary.get("access_services_used", []),
            representation="lazy" if any(p[0] in "CT" for p in patterns) else "unknown",
            validation_passed=bool(artifacts),
            metrics={
                "bytes_read": int(summary.get("bytes_read_estimate", 0) or 0),
                "objects_read": 0,
                "runtime_seconds": 0.0,
            },
        )

    result = score_run(task, observation)
    evaluation = Path(__file__).resolve().parent / "evaluation.json"
    evaluation.write_text(result.model_dump_json(indent=2))
    print(result.model_dump_json(indent=2))

    output_dir = workspace / "output"
    artifacts = list(output_dir.glob("*")) if output_dir.exists() else []
    sys.exit(0 if artifacts else 1)


if __name__ == "__main__":
    main()
'''

SOLVE_SH = """#!/bin/bash
set -euo pipefail

python /app/solution/reference_workflow.py
"""


def resolve_task(token: str) -> Path:
    token = token.strip().lower()
    if not token:
        raise SystemExit("empty task token")
    if token.endswith(".yaml"):
        matches = list(TASKS_DIR.rglob(Path(token).name))
        if len(matches) == 1:
            return matches[0]
        raise SystemExit(f"task file '{token}' matched {len(matches)} files")
    if "/" in token:
        target = TASKS_DIR / f"{token}.yaml"
        if target.exists():
            return target
        raise SystemExit(f"no task '{token}' under {TASKS_DIR}")
    sphere, _, code = token.rpartition("-")
    if sphere and sphere in SPHERE_PREFIXES:
        if not code.isdigit():
            raise SystemExit(
                f"task '{token}' needs a number, e.g. '{sphere}-1'"
            )
        directory = SPHERE_PREFIXES[sphere]
        prefix = f"{directory[0]}{code}"
        matches = sorted((TASKS_DIR / directory).glob(f"{prefix}-*.yaml"))
        if len(matches) == 1:
            return matches[0]
        raise SystemExit(
            f"task '{token}' matched {len(matches)} files in {directory}: "
            f"{[m.name for m in matches]}"
        )
    exact = sorted(TASKS_DIR.rglob(f"{token}.yaml"))
    if len(exact) == 1:
        return exact[0]
    matches = sorted(TASKS_DIR.rglob(f"{token}-*.yaml"))
    if len(matches) == 1:
        return matches[0]
    candidates = sorted({m.parent.name for m in TASKS_DIR.rglob("*.yaml")})
    raise SystemExit(
        f"cannot resolve task '{token}'. Use forms like 'cryo-1', 'atmo-2', "
        f"'solid-3', or a full id. Spheres: {candidates}"
    )


def resolve_tasks(tokens: str) -> list[Path]:
    if tokens.strip().lower() == "all":
        return sorted(TASKS_DIR.rglob("*.yaml"))
    if tokens.strip().lower() == "pilot":
        pilot = yaml.safe_load((REPO_ROOT / "experiments" / "pilot.yaml").read_text())
        resolved = []
        for task_id in pilot["tasks"]:
            resolved.append(resolve_task(task_id.split("/")[-1]))
        return resolved
    return [resolve_task(token) for token in tokens.split(",") if token.strip()]


def _agent_requirements() -> str:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    group = pyproject["dependency-groups"]["agent"]
    return "\n".join(group) + "\n"


def generate_package(task_path: str | Path, condition: str = "baseline",
                     out_root: Path = DEFAULT_OUT) -> Path:
    task = load_task(task_path)
    package = out_root / task_path.stem
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)

    (package / "instruction.md").write_text(render_instruction(task) + OUTPUT_CONTRACT)
    (package / "AGENTS.md").write_text(
        AGENTS_MD.format(skills_note=SKILLS_NOTE if _skills_mounted(condition) else "")
    )
    (package / "agent-requirements.txt").write_text(_agent_requirements())

    extra = ""
    if _skills_mounted(condition):
        shutil.copytree(REPO_ROOT / "skills", package / "skills")
        extra += "\nCOPY skills /app/skills\n"

    mcp_urls = _ready_mcp_urls(
        yaml.safe_load((REPO_ROOT / "experiments" / "conditions.yaml").read_text())
        ["wiring"]["mcp_servers"].get(condition, [])
    )
    if mcp_urls:
        _write_opencode_config(package, mcp_urls)
        _write_codex_config(package, mcp_urls)
        _write_claude_config(package, mcp_urls)
        _write_pi_config(package, mcp_urls)
        extra += "COPY opencode.jsonc config.toml .mcp.json pi.json /app/\n"

    environment = package / "environment"
    environment.mkdir()
    (environment / "Dockerfile").write_text(
        ENVIRONMENT_DOCKERFILE.format(extra=extra or "")
    )

    solution = package / "solution"
    solution.mkdir()
    (solution / "solve.sh").write_text(SOLVE_SH)
    (solution / "reference_workflow.py").write_text(
        "# expert reference workflow — TODO: implemented per task before the pilot\n"
    )

    tests = package / "tests"
    tests.mkdir()
    (tests / "Dockerfile").write_text(TESTS_DOCKERFILE)
    (tests / "run.sh").write_text(RUN_SH)
    (tests / "verify.py").write_text(VERIFY_PY)
    shutil.copy(task_path, tests / "task.yaml")
    vendored = tests / "earth_agent_bench"
    vendored.mkdir()
    src = REPO_ROOT / "src" / "earth_agent_bench"
    for name in VENDORED_MODULES:
        shutil.copy(src / name, vendored / name)
    scoring = vendored / "scoring"
    scoring.mkdir()
    for path in sorted((src / "scoring").glob("*.py")):
        shutil.copy(path, scoring / path.name)
    return package


def load_harbor_config() -> dict:
    return yaml.safe_load(HARBOR_CONFIG.read_text())


def render_harbor_command(task_path: str | Path, model_id: str, harness: str,
                          condition: str = "baseline",
                          out_root: Path = DEFAULT_OUT) -> list[str]:
    config = load_harbor_config()
    agent = config["agents"].get(harness)
    if agent is None:
        raise SystemExit(
            f"harness '{harness}' has no Harbor agent mapping in {HARBOR_CONFIG}"
        )
    task = load_task(task_path)
    package = out_root / Path(task_path).stem
    template = config["run_command_template"]
    rendered = template.format(
        task_path=package, agent=agent, model=model_id, condition=condition
    ).split()
    return [config["cli"], *rendered]


def run_harbor(task_path: str | Path, model_id: str, harness: str,
               condition: str = "baseline", out_root: Path = DEFAULT_OUT,
               dry_run: bool = False) -> int:
    generate_package(task_path, condition, out_root)
    command = render_harbor_command(task_path, model_id, harness, condition, out_root)
    print(" ".join(command))
    if dry_run:
        return 0
    return subprocess.run(command, cwd=REPO_ROOT).returncode
