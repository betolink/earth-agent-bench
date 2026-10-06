"""Model roster helpers: load, resolve, and discover gateway model names."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_YAML = REPO_ROOT / "experiments" / "models.yaml"
HARNESSES_YAML = REPO_ROOT / "experiments" / "harnesses.yaml"
CONDITIONS_YAML = REPO_ROOT / "experiments" / "conditions.yaml"


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_models() -> dict:
    return load_yaml(MODELS_YAML)


def model_ids() -> list[str]:
    return list(load_models()["models"].keys())


def gateway() -> dict:
    return load_models()["gateway"]


def _split(selection: list[str] | str) -> list[str]:
    if isinstance(selection, str):
        return [s.strip() for s in selection.split(",") if s.strip()]
    return [s.strip() for s in selection if s.strip()]


def resolve_models(selection: list[str] | str) -> list[str]:
    """Expand a model selection to roster ids. 'all' -> every roster model."""
    roster = model_ids()
    chosen = _split(selection)
    if chosen == ["all"]:
        return roster
    unknown = [s for s in chosen if s not in roster]
    if unknown:
        raise SystemExit(f"unknown model(s) {unknown}; roster: {', '.join(sorted(roster))}")
    return chosen


def default_harnesses() -> list[str]:
    return list(load_yaml(HARNESSES_YAML)["crossing"]["default_harnesses"])


def resolve_harnesses(selection: list[str] | str) -> list[str]:
    known = list(load_yaml(HARNESSES_YAML)["harnesses"].keys())
    chosen = _split(selection)
    if chosen == ["all"]:
        return default_harnesses()
    unknown = [s for s in chosen if s not in known]
    if unknown:
        raise SystemExit(f"unknown harness(es) {unknown}; known: {', '.join(sorted(known))}")
    return chosen


def resolve_conditions(selection: list[str] | str) -> list[str]:
    order = list(load_yaml(CONDITIONS_YAML)["order"])
    chosen = _split(selection)
    if chosen == ["all"]:
        return order
    unknown = [s for s in chosen if s not in order]
    if unknown:
        raise SystemExit(f"unknown condition(s) {unknown}; known: {', '.join(order)}")
    return chosen


def discover_models() -> list[dict]:
    """Query the LiteLLM gateway /v1/models and return the raw model records."""
    g = gateway()
    base = os.environ.get("LITELLM_BASE_URL", g["base_url"]).rstrip("/")
    key = os.environ.get("LITELLM_API_KEY", "")
    url = f"{base}{g.get('discover_endpoint', '/v1/models')}"
    headers = {"User-Agent": "earth-agent-bench/0.1"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:  # noqa: S310
        data = json.load(response)
    return data.get("data", [])


def reconcile_models() -> dict[str, str | None]:
    """Map roster id -> gateway model name (or None if not found on the gateway)."""
    gateway_names = {m["id"] for m in discover_models()}
    out: dict[str, str | None] = {}
    for model_id, entry in load_models()["models"].items():
        candidate = entry.get("litellm_model")
        out[model_id] = candidate if candidate in gateway_names else None
    return out
