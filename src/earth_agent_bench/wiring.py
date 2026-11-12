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


def load_yaml(path: str | Path) -> dict:
    """Load a YAML file into a dict."""
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
    """The gateway model name for a roster model id."""
    roster = load_yaml(MODELS_YAML).get("models", {})
    return roster.get(model_id, {}).get("litellm_model", model_id)


def mcp_servers_for(condition: str) -> list[str]:
    """MCP server ids wired for a condition."""
    wiring = load_yaml(CONDITIONS_YAML)["wiring"]
    return list(wiring["mcp_servers"].get(condition, []))


def ready_mcp_urls(server_ids: list[str]) -> dict[str, str]:
    """URLs of ready MCP servers for a set of ids (name -> url)."""
    manifest = load_yaml(MCP_MANIFEST)["servers"]
    urls = {}
    for server_id in server_ids:
        entry = manifest.get(server_id, {})
        if entry.get("status") == "ready" and entry.get("url"):
            urls[entry.get("expose_as", server_id)] = entry["url"]
    return urls


def skills_mounted(condition: str) -> bool:
    """Whether a condition mounts the skills dir."""
    wiring = load_yaml(CONDITIONS_YAML)["wiring"]
    return bool(wiring["skills_mounted"].get(condition, False))



