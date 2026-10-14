#!/usr/bin/env python3
"""Quantify failure-mode signatures across a run's trajectories.

Turns the postmortem's "(hypothesis)" items into measured frequencies by scanning
each cell's ATIF trajectory for the signatures behind the recommendations
(API friction, HDF4/GDAL, edit-thrash, auth, service reachability).

    python scripts/quantify_failures.py --run local-pi
    python scripts/quantify_failures.py --run local-pi --by condition
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from earth_agent_bench import trajectory as tj  # noqa: E402
from earth_agent_bench.index import index_records  # noqa: E402

# signature -> regex over the concatenated tool args + observations
PATTERNS: dict[str, str] = {
    "api_kwarg_error": r"unexpected keyword|Unknown key|got an unexpected|Unknown argument|is not a valid",
    "search_kwarg_tax": r"search_data\([^)]{0,200}?(limit|count|max_items|max_results|max_granules)\s*=",
    "hdf4": r"\bHDF4\b|\bHDF-4\b|0e 03 13 01|\\x0e\\x03\\x13\\x01|pyhdf",
    "gdal": r"\bGDAL\b|\bgdal\b",
    "edit_no_match": r"String to replace not found|No match found|does not match|multiple matches|old_str|oldString",
    "auth_http": r"(HTTP|status|error|code|Error)[^0-9]{0,6}40[13]\b|\bUnauthorized\b|\bForbidden\b|AccessDenied|get_s3_credentials",
    "harmony_fail": r"harmony[^\n]{0,120}(40[0-9]|50[0-9]|error|fail|refus|unreachable|not resolv)",
    "opendap_fail": r"opendap[^\n]{0,120}(40[0-9]|50[0-9]|error|fail|refus)|DispatchError",
    "no_bucket": r"NoSuchBucket|NoSuchKey|bucket does not exist",
    "timeout": r"timed out|TimeoutError|Command timed|timedout",
}
EDIT_TOOLS = {"edit", "str_replace", "str_replace_editor", "write", "apply_patch",
              "create_file", "multi_edit"}


def cell_text(traj_path: Path) -> tuple[str, Counter]:
    """Concatenated tool args + observations, and a counter of tool names."""
    if not traj_path.exists():
        return "", Counter()
    traj = json.loads(traj_path.read_text())
    chunks: list[str] = []
    tools: Counter = Counter()
    for step in traj.get("steps") or []:
        if step.get("message"):
            chunks.append(str(step["message"]))
        for call in step.get("tool_calls") or []:
            fn = call.get("function_name") or call.get("name") or "?"
            tools[fn] += 1
            args = call.get("arguments") or {}
            chunks.append(fn + " " + (args if isinstance(args, str) else json.dumps(args)))
        if step.get("observation"):
            chunks.append(str(step["observation"]))
    return "\n".join(chunks), tools


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--by", default="condition", choices=["condition", "model", "task"])
    args = ap.parse_args()

    cells = [r for r in index_records() if r.get("run_name") == args.run]
    if not cells:
        raise SystemExit(f"no cells for run '{args.run}'")

    hits: dict[str, Counter] = defaultdict(Counter)
    edit_calls: Counter = Counter()
    n_traj = 0
    for c in cells:
        key = c.get(args.by) or "?"
        traj_path = (tj.REPO_ROOT / c["trajectory"]) if c.get("trajectory") else Path("/nonexistent")
        text, tools = cell_text(traj_path)
        if text:
            n_traj += 1
        for sig, pat in PATTERNS.items():
            if re.search(pat, text, re.IGNORECASE):
                hits[sig][key] += 1
        edit_calls[key] += sum(tools[t] for t in EDIT_TOOLS)

    keys = sorted({c.get(args.by) for c in cells})
    print(f"run={args.run}  cells={len(cells)}  with-trajectory={n_traj}  by={args.by}\n")
    width = max(len(s) for s in PATTERNS) + 2
    print(f"{'signature':<{width}}" + "".join(f"{k:>26}" for k in keys) + f"{'TOTAL':>8}")
    for sig in PATTERNS:
        row = hits[sig]
        print(f"{sig:<{width}}" + "".join(f"{row[k]:>26}" for k in keys)
              + f"{sum(row.values()):>8}")
    print(f"{'edit_tool_calls':<{width}}" + "".join(f"{edit_calls[k]:>26}" for k in keys)
          + f"{sum(edit_calls.values()):>8}")


if __name__ == "__main__":
    main()
