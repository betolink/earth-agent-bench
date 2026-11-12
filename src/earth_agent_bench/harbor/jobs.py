"""Build Harbor JobConfigs and invoke the real ``harbor`` CLI."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..models import load_models
from ..wiring import (
    gateway_base,
    llm_api_key_ref,
    missing_credentials,
    skills_mounted,
)
from .config import (
    DEFAULT_JOBS,
    DEFAULT_OUT,
    HARBOR_CONFIG,
    SKILLS_DIR,
    agent_kwargs,
    agents,
    cli,
    model_provider,
)
from .packages import generate_package

CLAUDE_LANE_MODELS = {"claude-sonnet-5-5"}

# pi's custom-provider `api` ids (docs/custom-provider.md). LiteLLM speaks
# OpenAI Chat Completions.
PI_MODEL_APIS = {
    "openai-completions",
    "openai-responses",
    "anthropic-messages",
    "google-generative-ai",
}


def _harbor_model(model_id: str, harness: str) -> str:
    """Build the Harbor model_name string for a roster model id."""
    roster = load_models()["models"]
    if model_id not in roster:
        raise SystemExit(
            f"unknown model '{model_id}'; roster: {', '.join(sorted(roster))}"
        )
    litellm = roster[model_id].get("litellm_model", model_id)
    provider = model_provider(harness)
    return f"{provider}/{litellm}" if provider else litellm


def _subst_gateway(obj, base: str | None = None):
    """Replace ``{GATEWAY}`` placeholders in agent kwargs with the resolved endpoint."""
    base = base or gateway_base()
    if isinstance(obj, str):
        return obj.replace("{GATEWAY}", base)
    if isinstance(obj, dict):
        return {k: _subst_gateway(v, base) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_subst_gateway(v, base) for v in obj]
    return obj


def _agent_env(provider: str | None) -> dict[str, str]:
    """Env vars Harbor injects into the agent (gateway URL + key)."""
    base = gateway_base()
    key_ref = llm_api_key_ref()
    if provider == "anthropic":
        return {
            "ANTHROPIC_BASE_URL": base,
            "ANTHROPIC_API_KEY": key_ref,
        }
    if provider:
        return {
            "OPENAI_BASE_URL": f"{base}/v1",
            "OPENAI_API_KEY": key_ref,
        }
    return {}


def _job_name(
    task_path: str | Path, model_id: str, harness: str, condition: str
) -> str:
    """A readable, timestamped Harbor job name (one per run, minute precision).

    Harbor refuses to reuse a job directory whose config differs, so runs get a
    fresh directory by default. Pass an explicit ``job_name`` (with ``force`` to
    overwrite) when you want a stable, reproducible path.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"eab-{Path(task_path).stem}-{model_id}-{harness}-{condition}-{stamp}"


def write_job_config(
    task_path: str | Path,
    model_id: str,
    harness: str,
    condition: str = "baseline",
    out_root: Path = DEFAULT_OUT,
    jobs_dir: Path = DEFAULT_JOBS,
    job_name: str | None = None,
) -> Path:
    """Write the JobConfig that binds a generated package to one agent + model."""
    task_path = Path(task_path)
    known = agents()
    if harness not in known:
        raise SystemExit(
            f"harness '{harness}' has no Harbor agent mapping in {HARBOR_CONFIG}; "
            f"known: {', '.join(sorted(known))}"
        )
    # claude-code is allowed on any roster model when ANTHROPIC_BASE_URL
    # points at the LiteLLM gateway (anthropic-compatible /v1/messages).

    package = out_root / task_path.stem
    agent: dict = {
        "name": known[harness],
        "model_name": _harbor_model(model_id, harness),
    }
    env = _agent_env(model_provider(harness))
    if env:
        agent["env"] = env
    kwargs = agent_kwargs(harness)
    if harness == "pi":
        model_api = kwargs.get("model_api")
        if model_api is not None and model_api not in PI_MODEL_APIS:
            raise SystemExit(
                f"pi model_api '{model_api}' is invalid; choose one of "
                f"{', '.join(sorted(PI_MODEL_APIS))} (see {HARBOR_CONFIG})"
            )
    if kwargs:
        agent["kwargs"] = _subst_gateway(kwargs)
    if skills_mounted(condition):
        agent["skills"] = [str(SKILLS_DIR.resolve())]

    config = {
        "job_name": job_name or _job_name(task_path, model_id, harness, condition),
        "n_attempts": 1,
        "n_concurrent_trials": 1,
        "jobs_dir": str(Path(jobs_dir).resolve()),
        "agents": [agent],
        "tasks": [{"path": str(package.resolve())}],
    }
    job_config = package / "job.yaml"
    job_config.write_text(yaml.safe_dump(config, sort_keys=False))
    return job_config


def _harbor_cli() -> str:
    """Resolve the Harbor console script (PATH, else next to this interpreter)."""
    configured = cli()
    if shutil.which(configured):
        return configured
    sibling = Path(sys.executable).parent / configured
    if sibling.exists():
        return str(sibling)
    return configured


def render_harbor_command(
    job_config: str | Path, jobs_dir: Path = DEFAULT_JOBS
) -> list[str]:
    """The `harbor run --config ...` shell command for a job."""
    return [
        _harbor_cli(),
        "run",
        "--config",
        str(job_config),
        "--jobs-dir",
        str(Path(jobs_dir).resolve()),
        "--yes",
    ]


def _check_credentials() -> None:
    """Fail fast when a real run is missing the EAB env contract."""
    missing = missing_credentials()
    if missing:
        raise SystemExit(
            "missing credentials for a real run: " + ", ".join(missing)
            + " (set LITE_LLM_ENDPOINT, LITE_LLM_API_KEY, EARTHDATA_TOKEN)"
        )


def run_harbor(
    task_path: str | Path,
    model_id: str,
    harness: str,
    condition: str = "baseline",
    out_root: Path = DEFAULT_OUT,
    jobs_dir: Path = DEFAULT_JOBS,
    dry_run: bool = False,
    job_name: str | None = None,
    force: bool = False,
) -> int:
    """Generate a package + JobConfig, then invoke the real Harbor CLI.

    Runs get a unique job directory by default. Pass ``job_name`` for a stable
    path and ``force=True`` to delete it first (Harbor refuses to reuse a job
    directory whose config differs).
    """
    generate_package(task_path, condition, out_root)
    resolved_name = job_name or _job_name(task_path, model_id, harness, condition)
    if "/" in resolved_name or "\\" in resolved_name:
        raise SystemExit(f"job name must not contain path separators: {resolved_name!r}")
    job_config = write_job_config(
        task_path, model_id, harness, condition, out_root, jobs_dir, resolved_name
    )

    jobs_root = Path(jobs_dir).resolve()
    job_dir = jobs_root / resolved_name
    if force and job_dir.exists():
        if job_dir.parent != jobs_root:
            raise SystemExit(f"refusing to delete outside {jobs_root}: {job_dir}")
        shutil.rmtree(job_dir)

    command = render_harbor_command(job_config, jobs_dir)
    print(" ".join(shlex.quote(part) for part in command))
    print(f"job dir: {job_dir}")
    if dry_run:
        return 0
    _check_credentials()
    if shutil.which(command[0]) is None:
        raise SystemExit(
            f"'{command[0]}' was not found. Harbor is a project dependency: "
            "run `uv sync` (or `pixi install -e dev`) to install it, then retry. "
            f"The CLI name is configured in {HARBOR_CONFIG}."
        )
    return subprocess.run(command, cwd=Path(__file__).resolve().parents[3]).returncode
