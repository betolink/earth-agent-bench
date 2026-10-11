"""MCP server preflight. Borrowed from clusterfunk/intelligence-index: probe the
MCP servers declared for a condition *before* a scored run, because a dead MCP
silently invalidates the `mcp`/`mcp-skills` conditions (the intervention itself).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_MANIFEST = REPO_ROOT / "mcp" / "manifest.yaml"

_INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
               "clientInfo": {"name": "earth-agent-bench", "version": "0.1"}},
}


def load_servers() -> dict:
    """MCP server entries from mcp/manifest.yaml."""
    with MCP_MANIFEST.open() as f:
        return (yaml.safe_load(f) or {}).get("servers", {})


def probe_server(name: str, entry: dict, timeout: int = 20) -> dict:
    """Probe one MCP server endpoint; return its status dict."""
    url = entry.get("url")
    result = {"server": name, "url": url, "declared": entry.get("status", "?"),
              "reachable": False, "http": None, "note": ""}
    if not url:
        result["note"] = f"status={entry.get('status', 'pending')} (no url)"
        return result
    req = Request(url, data=json.dumps(_INIT).encode(),
                  headers={"Content-Type": "application/json",
                           "Accept": "application/json, text/event-stream",
                           "User-Agent": "earth-agent-bench/0.1"},
                  method="POST")
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310
            result["reachable"] = True
            result["http"] = response.status
    except HTTPError as error:  # reached a server that rejected the request
        result["reachable"] = True
        result["http"] = error.code
    except Exception as error:  # noqa: BLE001
        result["note"] = f"{type(error).__name__}: {str(error)[:80]}"
    return result


def doctor_servers(timeout: int = 20) -> list[dict]:
    """Probe all MCP servers and return (id, status, detail) rows."""
    return [probe_server(name, entry, timeout) for name, entry in load_servers().items()]
