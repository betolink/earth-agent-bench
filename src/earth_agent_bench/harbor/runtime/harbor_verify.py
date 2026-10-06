"""Shared helpers for the Harbor verifiers (vendored into the task package).

Runs inside the sandbox. Locates the agent's outputs across the roots it might
have used, and summarizes the observed access events written by eab_instrument.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_ROOTS = ("/app", "/home/user", "/logs", "/")


def roots(workspace: str, extra: list[str] | None = None) -> list[Path]:
    return [
        Path(workspace),
        *(Path(root) for root in DEFAULT_ROOTS),
        *(Path(root) for root in (extra or [])),
    ]


def find(roots_list: list[Path], *relatives: str) -> Path | None:
    for root in roots_list:
        for relative in relatives:
            candidate = root / relative
            if candidate.exists():
                return candidate
    return None


def read_events(path: Path | None) -> list[dict]:
    events: list[dict] = []
    if path is None:
        return events
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize_events(events: list[dict]) -> dict:
    """Derive observed access behavior from instrumented events."""
    data = [
        event for event in events
        if not event.get("error") and (event.get("pattern") or event.get("service"))
    ]
    patterns: list[str] = []
    services: list[str] = []
    for event in data:
        if event.get("pattern") and event["pattern"] not in patterns:
            patterns.append(event["pattern"])
        if event.get("service") and event["service"] not in services:
            services.append(event["service"])

    materialized = any(
        (event.get("pattern") or "").startswith(("F", "M")) for event in data
    )
    if data:
        representation = "materialized" if materialized else "lazy"
    else:
        representation = "unknown"

    short_names: list[str] = []
    for event in events:
        for key in ("short_name", "concept_id"):
            value = event.get(key)
            if value and value not in short_names:
                short_names.append(value)

    return {
        "patterns": patterns,
        "services": services,
        "representation": representation,
        "short_names": short_names,
        "data_access": bool(data),
        "objects_read": sum(event.get("n_result") or 0 for event in data),
        "runtime_s": round(sum(event.get("duration_s") or 0 for event in data), 3),
    }
