"""Profiler integration for the executor (scalene / memray).

Kept deliberately thin: we only *construct* the command and check availability;
the executor runs it. Profiling perturbs timing, so it is meant for a second,
efficiency-only pass over an already-correct deliverable — never for the timing
that decides pass/fail.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

KINDS = ("scalene", "memray")


class ProfilerError(RuntimeError):
    pass


def profile_available(kind: str) -> bool:
    if kind == "scalene":
        return importlib.util.find_spec("scalene") is not None
    if kind == "memray":
        return importlib.util.find_spec("memray") is not None
    return False


def available() -> dict[str, bool]:
    return {kind: profile_available(kind) for kind in KINDS}


def build_profile_command(kind: str, base_cmd: list[str], out: Path) -> list[str]:
    """Wrap a `[python, script, *args]` command so it runs under `kind`."""
    python, script, *args = base_cmd
    if kind == "scalene":
        # scalene writes a JSON profile with per-line CPU/memory attribution.
        if out.suffix != ".json":
            out = out.with_suffix(".json")
        return [python, "-m", "scalene", "run", "--json", "--outfile", str(out), script, *args]
    if kind == "memray":
        if out.suffix != ".bin":
            out = out.with_suffix(".bin")
        return [python, "-m", "memray", "run", "--force", "-o", str(out), script, *args]
    raise ProfilerError(f"unknown profiler '{kind}' (choose {', '.join(KINDS)})")


def describe(kind: str) -> str:
    if kind == "scalene":
        return "scalene --json: per-line CPU + memory attribution"
    if kind == "memray":
        return "memray run: allocation profile (.bin -> flamegraph/stats)"
    return "no profiling"
