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
    """LiteLLM endpoint: LITE_LLM_ENDPOINT (preferred) or LITELLM_BASE_URL, else models.yaml."""
    env = os.environ.get("LITE_LLM_ENDPOINT") or os.environ.get("LITELLM_BASE_URL")
    if env:
        return env.rstrip("/")
    gateway = load_yaml(MODELS_YAML).get("gateway", {})
    return str(gateway.get("base_url", "http://localhost:4000")).rstrip("/")


def llm_api_key_name() -> str:
    """Name of the gateway key env var to reference (new name preferred)."""
    if os.environ.get("LITE_LLM_API_KEY") or not os.environ.get("LITELLM_API_KEY"):
        return "LITE_LLM_API_KEY"
    return "LITELLM_API_KEY"


def llm_api_key_ref() -> str:
    """Harbor-resolved reference to the gateway key, e.g. ``${LITE_LLM_API_KEY:-}``."""
    return "${" + llm_api_key_name() + ":-}"


def missing_credentials() -> list[str]:
    """The env contract to run EAB: EARTHDATA_TOKEN, LITE_LLM_ENDPOINT, LITE_LLM_API_KEY."""
    missing = []
    if not (os.environ.get("LITE_LLM_API_KEY") or os.environ.get("LITELLM_API_KEY")):
        missing.append("LITE_LLM_API_KEY")
    if not (os.environ.get("EARTHDATA_TOKEN")
            or (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))):
        missing.append("EARTHDATA_TOKEN (or EARTHDATA_USERNAME+EARTHDATA_PASSWORD)")
    if not (os.environ.get("LITE_LLM_ENDPOINT") or os.environ.get("LITELLM_BASE_URL")
            or load_yaml(MODELS_YAML).get("gateway", {}).get("base_url")):
        missing.append("LITE_LLM_ENDPOINT")
    return missing


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
