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
    """Load a YAML file into a dict."""
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_models() -> dict:
    """The models section of experiments/models.yaml."""
    return load_yaml(MODELS_YAML)


def model_ids() -> list[str]:
    """Roster model ids."""
    return list(load_models()["models"].keys())


def gateway() -> dict:
    """The gateway section of models.yaml."""
    return load_models()["gateway"]


def _split(selection: list[str] | str) -> list[str]:
    """Split a 'provider/model' string into (provider, model)."""
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
    """Default harness list from harnesses.yaml."""
    return list(load_yaml(HARNESSES_YAML)["crossing"]["default_harnesses"])


def resolve_harnesses(selection: list[str] | str) -> list[str]:
    """Resolve a harness selection to concrete ids."""
    known = list(load_yaml(HARNESSES_YAML)["harnesses"].keys())
    chosen = _split(selection)
    if chosen == ["all"]:
        return default_harnesses()
    unknown = [s for s in chosen if s not in known]
    if unknown:
        raise SystemExit(f"unknown harness(es) {unknown}; known: {', '.join(sorted(known))}")
    return chosen


def resolve_conditions(selection: list[str] | str) -> list[str]:
    """Resolve a condition selection to concrete ids."""
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
    base = (os.environ.get("LITE_LLM_ENDPOINT") or os.environ.get("LITELLM_BASE_URL")
            or g["base_url"]).rstrip("/")
    key = (os.environ.get("LITE_LLM_API_KEY")
           or os.environ.get("LITELLM_API_KEY") or "")
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


# --------------------------------------------------------------------------
# Serving preflight ("doctor").  Borrowed from clusterfunk/intelligence-index:
# verify a model is served AND can complete an agentic turn (tool call + JSON)
# before spending Harbor runs on it.
# --------------------------------------------------------------------------
import time  # noqa: E402
from urllib.error import HTTPError  # noqa: E402

_PING_TOOL = [{
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Return the provided value. Use this to acknowledge.",
        "parameters": {"type": "object", "properties": {"value": {"type": "string"}},
                       "required": ["value"]},
    },
}]


def gateway_chat(model: str, messages: list[dict], tools: list[dict] | None = None,
                 max_tokens: int = 256, timeout: int = 180) -> dict:
    """POST a chat completion to the gateway and return the parsed response."""
    g = gateway()
    base = (os.environ.get("LITE_LLM_ENDPOINT") or os.environ.get("LITELLM_BASE_URL")
            or g["base_url"]).rstrip("/")
    key = (os.environ.get("LITE_LLM_API_KEY")
           or os.environ.get("LITELLM_API_KEY") or "")
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens,
                  "temperature": 0}
    if tools:
        body["tools"] = tools
    req = Request(f"{base}/v1/chat/completions", data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json",
                           "User-Agent": "earth-agent-bench/0.1",
                           "Authorization": f"Bearer {key}"},
                  method="POST")
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def _probe(model: str, messages: list[dict], tools: list[dict] | None = None,
           max_tokens: int = 256, timeout: int = 180) -> tuple[dict | None, float, str]:
    """Return (assistant_message_or_None, elapsed_s, error_note)."""
    start = time.time()
    try:
        data = gateway_chat(model, messages, tools, max_tokens, timeout)
    except HTTPError as error:
        return None, time.time() - start, f"HTTP {error.code}"
    except Exception as error:  # noqa: BLE001
        return None, time.time() - start, f"{type(error).__name__}: {str(error)[:100]}"
    message = (data.get("choices") or [{}])[0].get("message") or {}
    return message, time.time() - start, ""


def doctor_model(model_id: str, timeout: int = 180) -> dict:
    """Preflight one roster model: served? tool call? valid JSON? latency."""
    entry = load_models()["models"].get(model_id, {})
    litellm_model = entry.get("litellm_model", model_id)
    result = {"model": model_id, "litellm_model": litellm_model,
              "served": False, "tool_ok": False, "json_ok": False,
              "latency_s": None, "note": ""}
    try:
        gateway_names = {m["id"] for m in discover_models()}
    except Exception as error:  # noqa: BLE001
        result["note"] = f"gateway query failed: {error}"
        return result
    if litellm_model not in gateway_names:
        result["note"] = "not on gateway"
        return result
    result["served"] = True

    # Tool-call probe.
    msg, dt, err = _probe(litellm_model,
                          [{"role": "user", "content": "Call the ping tool with value \"pong\"."}],
                          tools=_PING_TOOL, max_tokens=256, timeout=timeout)
    result["latency_s"] = round(dt, 1)
    if msg is None:
        result["note"] = err
    else:
        calls = msg.get("tool_calls") or []
        names = [c.get("function", {}).get("name") for c in calls]
        result["tool_ok"] = "ping" in names
        if not result["tool_ok"] and not calls:
            result["note"] = (msg.get("content") or "")[:80]

    # JSON probe.
    msg2, _, _ = _probe(litellm_model,
                        [{"role": "user", "content":
                          "Reply with JSON only, no prose: {\"ok\": true}"}],
                        max_tokens=128, timeout=timeout)
    if msg2 is not None:
        content = msg2.get("content") or ""
        try:
            lo = content[content.index("{"):content.rindex("}") + 1]
            result["json_ok"] = json.loads(lo).get("ok") is True
        except Exception:  # noqa: BLE001
            result["json_ok"] = False
    return result


def doctor_models(selection: list[str] | str = "all", timeout: int = 180) -> list[dict]:
    """Check each roster model is served by the gateway; return rows."""
    return [doctor_model(m, timeout=timeout) for m in resolve_models(selection)]
