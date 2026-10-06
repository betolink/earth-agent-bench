"""Single-run orchestrator: build a workspace, wire a harness, launch one task.

Usage:
    uv run eab run benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml \
        --model tiel-coder-35b --harness opencode --condition mcp-skills --dry-run

What the runner does NOT do (still manual):
    - classifying the observed access pattern / byte counts (fill observation.json)
    - the minimal-science-gate check (validation_passed)
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .schemas import RunManifest
from .tasks import load_task, render_instruction
from .wiring import (
    gateway_base as _gateway_base,
    litellm_model as _litellm_model,
    load_yaml,
    mcp_servers_for as _mcp_servers_for,
    ready_mcp_urls as _ready_mcp_urls,
    skills_mounted as _skills_mounted,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_YAML = REPO_ROOT / "experiments" / "models.yaml"
CONDITIONS_YAML = REPO_ROOT / "experiments" / "conditions.yaml"
MCP_MANIFEST = REPO_ROOT / "mcp" / "manifest.yaml"
SKILLS_DIR = REPO_ROOT / "skills"

HARNESS_IDS = ("pi", "opencode", "codex-cli", "claude-code")
CLAUDE_LANE_MODELS = {"claude-sonnet-5-5"}

EVAL_OUTPUT_CONTRACT = """

## Output contract

- Write only your final answer to `./output/answer.txt` (a single clean value), then stop.

## Constraints

- Metadata search is permitted (e.g. `earthaccess.search_data` / `search_datasets`).
- Do **not** download, open, stream, virtualize, or process any granules — no I/O on
  science data. Produce the single value only.
"""


OUTPUT_CONTRACT = """

## Output contract

- Write all artifacts to `./output/` in the required format named above.
- Write `./output/access_summary.json` describing how data were accessed:

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

AGENTS_MD = """# Run workspace

Complete the task in `instruction.md`. Write artifacts to `./output/`.
{skills_note}
"""

SKILLS_NOTE = """
## Earthdata skills

Before starting, read the skill guides in `./skills/` (start with
`data-access-patterns/SKILL.md`) and follow them where relevant.
"""


@dataclass
class RunSpec:
    task_path: Path
    model_id: str
    harness: str
    condition: str = "baseline"
    trial: int = 1
    runs_root: Path = REPO_ROOT / "runs"
    timeout_s: int = 600

    @property
    def run_dir(self) -> Path:
        task_id = self.task_path.stem
        return (
            self.runs_root / task_id / self.model_id / self.harness
            / self.condition / f"trial-{self.trial}"
        )


def validate_spec(spec: RunSpec) -> None:
    roster = load_yaml(MODELS_YAML)["models"]
    if spec.model_id not in roster:
        raise SystemExit(
            f"unknown model '{spec.model_id}'; roster: {', '.join(sorted(roster))}"
        )
    if spec.harness not in HARNESS_IDS:
        raise SystemExit(
            f"unknown harness '{spec.harness}'; harnesses: {', '.join(HARNESS_IDS)}"
        )
    if spec.harness == "claude-code" and spec.model_id not in CLAUDE_LANE_MODELS:
        raise SystemExit(
            "claude-code is a restricted lane: only "
            f"{', '.join(sorted(CLAUDE_LANE_MODELS))} (see experiments/harnesses.yaml)"
        )
    if spec.condition not in ("baseline", "mcp", "skills", "mcp-skills"):
        raise SystemExit(f"unknown condition '{spec.condition}'")


def _write_opencode_config(run_dir: Path, mcp_urls: dict[str, str]) -> None:
    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "litellm": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {
                    "baseURL": f"{_gateway_base()}/v1",
                    "apiKey": "{env:LITELLM_API_KEY}",
                },
                "models": {},
            }
        },
    }
    if mcp_urls:
        config["mcp"] = {
            server: {"type": "url", "url": url}
            for server, url in mcp_urls.items()
        }
    (run_dir / "opencode.jsonc").write_text(json.dumps(config, indent=2))


def _write_codex_config(run_dir: Path, mcp_urls: dict[str, str]) -> None:
    lines = [
        'model_provider = "litellm"',
        "",
        "[model_providers.litellm]",
        'name = "litellm"',
        f'base_url = "{_gateway_base()}/v1"',
        'wire_api = "chat"',
        'env_key = "LITELLM_API_KEY"',
    ]
    for server, url in mcp_urls.items():
        lines += ["", f"[mcp_servers.{server}]", f'url = "{url}"']
    (run_dir / "config.toml").write_text("\n".join(lines) + "\n")


def _write_claude_config(run_dir: Path, mcp_urls: dict[str, str]) -> None:
    config = {"mcpServers": {}}
    for server, url in mcp_urls.items():
        config["mcpServers"][server] = {"type": "http", "url": url}
    (run_dir / ".mcp.json").write_text(json.dumps(config, indent=2))


def _write_pi_config(run_dir: Path, mcp_urls: dict[str, str]) -> None:
    config = {"mcpServers": {}}
    for server, url in mcp_urls.items():
        config["mcpServers"][server] = {"type": "url", "url": url}
    (run_dir / "pi.json").write_text(json.dumps(config, indent=2))


HARNESS_CONFIG_WRITERS = {
    "opencode": _write_opencode_config,
    "codex": _write_codex_config,
    "claude-code": _write_claude_config,
    "pi": _write_pi_config,
}


def prepare_run(spec: RunSpec) -> Path:
    validate_spec(spec)
    run_dir = spec.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    if spec.task_path.suffix == ".md":
        task_id = spec.task_path.stem
        instruction = spec.task_path.read_text() + EVAL_OUTPUT_CONTRACT
    else:
        task = load_task(spec.task_path)
        task_id = task.task_id
        instruction = render_instruction(task) + OUTPUT_CONTRACT

    (run_dir / "instruction.md").write_text(instruction)
    (run_dir / "AGENTS.md").write_text(
        AGENTS_MD.format(
            skills_note=SKILLS_NOTE if _skills_mounted(spec.condition) else ""
        )
    )

    output_dir = run_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if _skills_mounted(spec.condition):
        skills_link = run_dir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(SKILLS_DIR.resolve())

    mcp_urls = _ready_mcp_urls(_mcp_servers_for(spec.condition))
    HARNESS_CONFIG_WRITERS[spec.harness](run_dir, mcp_urls)

    roster = load_yaml(MODELS_YAML)["models"]
    model = roster[spec.model_id]
    manifest = RunManifest(
        task_id=task_id,
        model_id=spec.model_id,
        model_tier=model["tier"],
        harness=spec.harness,
        condition=spec.condition,
        trial=spec.trial,
        quantization=model.get("quantization"),
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))

    if spec.task_path.suffix != ".md":
        observation = {
            "task_id": task_id,
            "observed_patterns": [],
            "collection_short_names": [],
            "discovered_services": [],
            "representation": "unknown",
            "validation_passed": False,
            "metrics": {
                "bytes_read": 0,
                "objects_read": 0,
                "runtime_seconds": 0.0,
            },
        }
        (run_dir / "observation.template.json").write_text(
            json.dumps(observation, indent=2)
        )
    return run_dir


def build_env(spec: RunSpec) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k in {"PATH", "HOME", "LANG", "TERM", "EARTHDATA_USERNAME",
                    "EARTHDATA_PASSWORD", "LITELLM_API_KEY"}}
    gateway = _gateway_base()
    if spec.harness == "claude-code":
        env["ANTHROPIC_BASE_URL"] = gateway
        env["ANTHROPIC_AUTH_TOKEN"] = os.environ.get("LITELLM_API_KEY", "")
    else:
        env["OPENAI_BASE_URL"] = f"{gateway}/v1"
        env["OPENAI_API_KEY"] = os.environ.get("LITELLM_API_KEY", "")
    if spec.harness == "codex":
        env["CODEX_HOME"] = str(spec.run_dir.resolve())
    return env


def build_command(spec: RunSpec) -> list[str]:
    prompt = "$(cat instruction.md)"
    model = _litellm_model(spec.model_id)
    if spec.harness == "opencode":
        return ["sh", "-c",
                f'opencode run --model litellm/{model} "{prompt}"']
    if spec.harness == "codex-cli":
        return ["sh", "-c", f'codex exec --skip-git-repo-check -m {model} "{prompt}"']
    if spec.harness == "claude-code":
        return ["sh", "-c",
                f'claude -p "{prompt}" --model {spec.model_id} '
                f'--output-format json']
    if spec.harness == "pi":
        return ["sh", "-c", f'pi --print "{prompt}"']
    raise SystemExit(f"unknown harness '{spec.harness}'")


def execute(spec: RunSpec, dry_run: bool = False) -> int:
    run_dir = prepare_run(spec)
    env = build_env(spec)
    command = build_command(spec)

    printable_env = {
        k: ("***" if "KEY" in k or "TOKEN" in k or "PASSWORD" in k else v)
        for k, v in env.items()
        if k not in {"PATH", "HOME", "LANG", "TERM"}
    }
    print(f"workspace: {run_dir}")
    print(f"env: {json.dumps(printable_env, indent=2)}")
    print(f"command: {' '.join(command)}")
    if spec.harness == "pi":
        print("note: pi non-interactive invocation is verify-at-pilot "
              "(see experiments/harnesses.yaml)")

    if dry_run:
        return 0

    try:
        with (run_dir / "session.log").open("w") as log:
            process = subprocess.run(
                command, cwd=run_dir, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=spec.timeout_s,
            )
    except subprocess.TimeoutExpired:
        print(f"timed out after {spec.timeout_s}s; see {run_dir}/session.log")
        (run_dir / "TIMED_OUT").touch()
        return 124
    if process.returncode != 0:
        print(f"harness exited {process.returncode}; see {run_dir}/session.log")
    if spec.task_path.suffix == ".md":
        print("next: grade the answer with "
              f"uv run eab eval grade {spec.task_path.stem} {run_dir}/output/answer.txt")
    else:
        print("next: fill observation.json from the trajectory, then "
              f"uv run eab score {run_dir}/observation.json")
    return process.returncode
