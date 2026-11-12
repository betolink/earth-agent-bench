"""Harbor integration configuration (harbor/harbor.yaml and repo paths)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
HARBOR_DIR = REPO_ROOT / "harbor"
HARBOR_CONFIG = HARBOR_DIR / "harbor.yaml"
DEFAULT_OUT = HARBOR_DIR / "generated"
DEFAULT_JOBS = REPO_ROOT / "runs" / "harbor"
RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"
BENCHMARK_TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"
EVAL_TASKS_DIR = REPO_ROOT / "experiments" / "evals" / "tasks"
EVAL_SUITE = REPO_ROOT / "experiments" / "evals" / "suite.yaml"
SKILLS_DIR = REPO_ROOT / "skills"


def load_harbor_config() -> dict:
    """Load and cache harbor/harbor.yaml."""
    return yaml.safe_load(HARBOR_CONFIG.read_text()) or {}


def cli() -> str:
    """Return a top-level value from the harbor config."""
    return load_harbor_config().get("cli", "harbor")


def agents() -> dict[str, str]:
    """benchmark harness id -> Harbor agent name."""
    return load_harbor_config().get("agents", {})


def model_provider(harness: str) -> str | None:
    """Provider prefix Harbor expects for the gateway (e.g. 'openai')."""
    return load_harbor_config().get("model_provider", {}).get(harness)


def agent_kwargs(harness: str) -> dict:
    """Default agent kwargs from the harbor config."""
    return dict(load_harbor_config().get("agent_kwargs", {}).get(harness, {}))


def skills_env_dir() -> str:
    """In-container directory where skills are mounted."""
    return load_harbor_config().get("skills_dir", "/harbor/skills")


def agent_timeout_sec() -> float:
    """Agent execution cap in seconds."""
    return float(load_harbor_config().get("agent_timeout_sec", 600.0))


def verifier_timeout_sec() -> float:
    """Verifier execution cap in seconds."""
    return float(load_harbor_config().get("verifier_timeout_sec", 600.0))


def verifier_environment_mode() -> str:
    """Harbor verifier mode: 'separate' (trusted container) or 'shared'."""
    return str(load_harbor_config().get("verifier_environment_mode", "separate"))


def resources() -> dict:
    """Container resource caps baked into generated task.toml files."""
    return dict(load_harbor_config().get("resources", {}))


def instruction_access_policy() -> bool:
    """Whether rendered instructions state the access policy the verifier enforces."""
    return bool(load_harbor_config().get("instruction_access_policy", True))


def artifact_sources() -> list[str]:
    """Container paths collected into the trial artifacts dir (and the verifier)."""
    return list(load_harbor_config().get(
        "artifacts", ["/app/output", "/app/work", "/app/access.py", "/logs/agent"]
    ))
