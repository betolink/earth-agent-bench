"""Helpers for the Harbor run tree under ``runs/harbor``.

A job directory is named::

    eab-<task>-<model>-<harness>-<condition>-<stamp>

where ``<stamp>`` is ``YYYYMMDD-HHMMSS`` and every field except ``<task>`` comes
from a known set (the roster, ``harnesses.yaml``, ``conditions.yaml``). Parsing
that name was duplicated across the codebase (and bug-prone); this module is the
single implementation.

Example::

    from earth_agent_bench.runs import parse_job_dir, read_json
    ref = parse_job_dir("eab-a3-maiac-aod-eastern-us-2023-tiel-coder-35b-pi-baseline-20261011-005413")
    ref.task, ref.model, ref.harness, ref.condition, ref.stamp
    # ('a3-maiac-aod-eastern-us-2023', 'tiel-coder-35b', 'pi', 'baseline', '20261011-005413')
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_STAMP = re.compile(r"^(.*)-(\d{8}-\d{6})$")


@dataclass(frozen=True)
class RunRef:
    """A parsed job directory name: task/model/harness/condition/stamp."""

    name: str
    task: str = ""
    model: str = ""
    harness: str = ""
    condition: str = ""
    stamp: str = ""


def _known() -> tuple[list[str], list[str], list[str]]:
    """Known model/harness/condition ids from the master config."""
    from .runconfig import condition_ids, harness_ids, roster_ids
    return roster_ids(), harness_ids(), condition_ids()


def _suffix(value: str, options) -> str:
    """Longest option that ``value`` ends with as ``-<option>`` ('' if none)."""
    best = ""
    for option in options:
        if value == option or value.endswith("-" + option):
            if len(option) > len(best):
                best = option
    return best


def parse_job_dir(name: str, models=None, harnesses=None, conditions=None) -> RunRef:
    """Parse ``eab-<task>-<model>-<harness>-<cond>-<stamp>`` into a :class:`RunRef`.

    Fields are matched against the known sets (roster/harnesses/conditions) from
    the master config, so dashes inside ``<task>`` are handled correctly. Unknown
    fields are left empty; a name without a valid stamp returns a bare RunRef.
    """
    if models is None or harnesses is None or conditions is None:
        default_models, default_harnesses, default_conditions = _known()
        models = models or default_models
        harnesses = harnesses or default_harnesses
        conditions = conditions or default_conditions
    base = name[len("eab-"):] if name.startswith("eab-") else name
    match = _STAMP.match(base)
    if not match:
        return RunRef(name)
    rest, stamp = match.group(1), match.group(2)
    condition = _suffix(rest, conditions)
    if condition:
        rest = rest[: -(len(condition) + 1)]
    harness = _suffix(rest, harnesses)
    if harness:
        rest = rest[: -(len(harness) + 1)]
    model = _suffix(rest, models)
    task = rest[: -(len(model) + 1)] if model else rest
    return RunRef(name, task, model, harness, condition, stamp)


def read_json(path: Path) -> dict:
    """Best-effort JSON read; returns ``{}`` on missing/unreadable/invalid input."""
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}
