"""Shared condition / gateway wiring used by the direct and Harbor runners."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_YAML = REPO_ROOT / "experiments" / "models.yaml"
CONDITIONS_YAML = REPO_ROOT / "experiments" / "conditions.yaml"
MCP_MANIFEST = REPO_ROOT / "mcp" / "manifest.yaml"
SKILLS_DIR = REPO_ROOT / "skills"
IMPROVEMENTS_DIR = REPO_ROOT / "improvements"


def load_yaml(path: str | Path) -> dict:
    with Path(path).open() as handle:
        return yaml.safe_load(handle) or {}


def gateway_base() -> str:
    if os.environ.get("LITELLM_BASE_URL"):
        return os.environ["LITELLM_BASE_URL"]
    gateway = load_yaml(MODELS_YAML).get("gateway", {})
    return gateway.get("base_url", "http://localhost:4000")


def litellm_model(model_id: str) -> str:
    roster = load_yaml(MODELS_YAML).get("models", {})
    return roster.get(model_id, {}).get("litellm_model", model_id)


def mcp_servers_for(condition: str) -> list[str]:
    wiring = load_yaml(CONDITIONS_YAML)["wiring"]
    return list(wiring["mcp_servers"].get(condition, []))


def ready_mcp_urls(server_ids: list[str]) -> dict[str, str]:
    manifest = load_yaml(MCP_MANIFEST)["servers"]
    urls = {}
    for server_id in server_ids:
        entry = manifest.get(server_id, {})
        if entry.get("status") == "ready" and entry.get("url"):
            urls[entry.get("expose_as", server_id)] = entry["url"]
    return urls


def skills_mounted(condition: str) -> bool:
    wiring = load_yaml(CONDITIONS_YAML)["wiring"]
    return bool(wiring["skills_mounted"].get(condition, False))


def improvement_mounted(condition: str) -> bool:
    """True when the condition also mounts the model's self-improvement skill."""
    wiring = load_yaml(CONDITIONS_YAML)["wiring"]
    return bool(wiring.get("improvement_mounted", {}).get(condition, False))


def improvement_dir(model_id: str) -> Path | None:
    """The per-model skill dir to mount, or None if no improvement exists."""
    d = IMPROVEMENTS_DIR / model_id
    return d if d.is_dir() else None
