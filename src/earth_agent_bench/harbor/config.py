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
    return yaml.safe_load(HARBOR_CONFIG.read_text()) or {}


def cli() -> str:
    return load_harbor_config().get("cli", "harbor")


def agents() -> dict[str, str]:
    """benchmark harness id -> Harbor agent name."""
    return load_harbor_config().get("agents", {})


def model_provider(harness: str) -> str | None:
    return load_harbor_config().get("model_provider", {}).get(harness)


def agent_kwargs(harness: str) -> dict:
    return dict(load_harbor_config().get("agent_kwargs", {}).get(harness, {}))


def skills_env_dir() -> str:
    return load_harbor_config().get("skills_dir", "/harbor/skills")
