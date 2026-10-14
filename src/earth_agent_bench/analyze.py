"""Analyze a run with a judge model: summary + postmortem + results table.

Collects a run's cells (instructions + ATIF trajectories + verifier details),
builds a single prompt (benchmark context → what we want → the payload), sends it
to a judge model on the gateway, and writes the analysis.

    eab analyze --name local-pi --judge glm-5.3 --harness pi --output ./
    eab analyze --name local-pi --dry-run          # write the payload only

The payload embeds each cell's trajectory in **ATIF** form (the schema Harbor
writes to ``agent/trajectory.json`` — see
https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md),
condensed to fit a prompt.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import trajectory as tj
from .index import index_records

REPO_ROOT = tj.REPO_ROOT

CONTEXT = """\
earth-agent-bench (EAB) grades whether an agent picks and executes the best
*data-access route* for a NASA Earthdata dataset — **not** the science result.

- Each task names the dataset(s) + CMR `concept_id` and asks the agent to write
  `access.py` and run it once on a small **demo slice**. We grade the **route**,
  from the **observed** calls (instrumented): `earthaccess.open`/`virtualize` →
  `C1`, `harmony.submit` → `S1`, `pydap` → `S2`, `earthaccess.download` → `F1`, …
- Components (weighted): access-pattern 0.45 · service discovery 0.15 ·
  representation 0.15 · efficiency 0.15 · validation 0.10. An unsanctioned
  deliverable (raw CMR / no earthaccess) is penalised 0.5x.
- Route preference: **data virtualization first**, then **streaming**
  (`earthaccess.open`), then **Harmony / OPeNDAP** (async, queued — heavier),
  then download.
- Conditions: `baseline` (no help) · `mcp` · `skills` (mounted guidance) ·
  `mcp-skills` · `improve` (a per-model self-improvement skill).
"""

ASK = """\
Analyze this run as a whole and per condition/row, grounded in the trajectories.
Cover:

1. **What happened** — which routes the agents actually took (virtualize / stream
   / Harmony / OPeNDAP / download / raw CMR), where they succeeded or failed, and
   why. Cite specific cells.
2. **Postmortem** — the dominant failure modes (timeouts, wrong route, loops,
   auth, tool misuse, ignoring the dataset) with evidence from the trajectories.
3. **Did the knowledge conditions help?** Compare `skills` (and `mcp`) against
   `baseline`: did the route change, and did the score move? Why / why not.
4. **Recommendations** — concrete, prioritized changes to the **skills**, the
   **tasks**, or the **harness**, each tied to evidence.
5. **Results table** — a markdown table of the run (rows × mean reward, timeouts,
   access-pattern).

Be specific and evidence-based; do not restate the prompt.
"""


def collect_cells(name: str, harness: str | None = None) -> list[dict]:
    """Cells of a run (index records whose `run_name` == name), optional harness filter."""
    rows = index_records()
    cells = [r for r in rows if r.get("run_name") == name]
    if harness:
        cells = [r for r in cells if r.get("harness") == harness]
    return cells


def _condense_steps(traj: dict, max_steps: int = 200, width: int = 240) -> list[str]:
    """Compact ATIF trajectory: instruction + per-step reasoning/tool/observation.

    ``max_steps`` defaults high (200) so a whole trajectory is kept — the judge
    needs the *middle* (route decision, pivots, loops), not just head+tail. Bound
    the size with ``width`` (per-line truncation) instead of dropping steps.
    """
    out: list[str] = []
    for step in (traj.get("steps") or [])[:max_steps]:
        src = step.get("source", "")
        if src == "user":
            msg = " ".join(str(step.get("message") or "").split())
            out.append(f"[user] {msg[:width * 3]}")
            continue
        reasoning = " ".join(str(step.get("reasoning_content") or "").split())
        if reasoning:
            out.append(f"  [think] {reasoning[:width]}")
        for call in (step.get("tool_calls") or []):
            fn = call.get("function_name") or call.get("name") or "?"
            args = call.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            detail = (args.get("command") or args.get("path") or args.get("query")
                      or json.dumps(args)[:width])
            out.append(f"  [tool:{fn}] {' '.join(str(detail).split())[:width]}")
        obs = step.get("observation")
        if obs:
            out.append(f"  [obs] {' '.join(str(obs).split())[:width]}")
    return out


def _cell_block(cell: dict, max_steps: int, width: int = 240) -> str:
    """One cell: header + condensed ATIF trajectory."""
    head = (f"### {cell['task']} · {cell['model']} · {cell['harness']} · "
            f"{cell['condition']} — reward={cell['reward']} status={cell['status']}")
    lines = [head]
    if cell.get("exception"):
        lines.append(f"exception: {cell['exception']}")
    traj_path = cell.get("trajectory")
    if traj_path and Path(traj_path).exists():
        traj = json.loads(Path(traj_path).read_text())
        ok, errors = tj.validate_atif(traj_path)
        note = "" if ok else f", INVALID ATIF: {errors[:2]}"
        lines.append(f"(ATIF {traj.get('schema_version')}, "
                     f"agent={traj.get('agent', {}).get('name')}{note})")
        lines += _condense_steps(traj, max_steps=max_steps, width=width)
    else:
        lines.append("(no trajectory)")
    return "\n".join(lines)


def _results_table(cells: list[dict]) -> str:
    """Markdown table: one row per (model, harness, condition)."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for c in cells:
        buckets[(c["model"], c["harness"], c["condition"])].append(c)
    lines = ["| model | harness | condition | n | mean reward | timeouts | access_pattern |",
             "|---|---|---|---|---|---|---|"]
    for key in sorted(buckets):
        v = buckets[key]
        n = len(v)
        mean = sum(x["reward"] or 0 for x in v) / n
        to = sum(1 for x in v if x["status"] == "timeout")
        ap = sum((x["components"].get("access_pattern") or 0) for x in v) / n
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {n} | {mean:.3f} | {to} | {ap:.2f} |")
    return "\n".join(lines)


def build_payload(name: str, cells: list[dict], max_cells: int = 12,
                  max_steps: int = 200, width: int = 240) -> str:
    """The full judge prompt: context → ask → run table → condensed trajectories."""
    chosen = cells[:max_cells]
    parts = [
        "# Benchmark analysis request",
        "",
        "## Context",
        CONTEXT,
        "## What we want",
        ASK,
        "## Run",
        f"`{name}` — {len(cells)} cells"
        + (f" (showing {len(chosen)} trajectories)" if len(chosen) < len(cells) else ""),
        "",
        _results_table(cells),
        "",
        "## Trajectories (ATIF, condensed)",
        "",
    ]
    parts += [_cell_block(c, max_steps, width) for c in chosen]
    return "\n".join(parts)


def call_judge(model: str, payload: str, max_tokens: int = 32000, timeout: int = 1800) -> str:
    """Send the payload to a judge model on the gateway; return its reply (streamed).

    ``model`` may be a roster id (resolved via models.yaml) or a raw gateway id.
    Streamed (SSE) so long reasoning generations don't hit the proxy's idle
    timeout (HTTP 524). ``max_tokens`` must be generous — reasoning models spend a
    lot before the answer.
    """
    import json
    import os
    from urllib.request import Request, urlopen

    from .wiring import gateway_base, litellm_model

    resolved = litellm_model(model)
    key = (os.environ.get("LITE_LLM_API_KEY")
           or os.environ.get("LITELLM_API_KEY") or "")
    body = {"model": resolved, "messages": [{"role": "user", "content": payload}],
            "max_tokens": max_tokens, "temperature": 0, "stream": True}
    req = Request(f"{gateway_base()}/v1/chat/completions",
                  data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json",
                           "Accept": "text/event-stream",
                           "User-Agent": "earth-agent-bench/0.1",
                           "Authorization": f"Bearer {key}"},
                  method="POST")
    parts: list[str] = []
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
            if delta.get("content"):
                parts.append(delta["content"])
    return "".join(parts)


def analyze(name: str, judge: str, harness: str | None = None, output: Path = Path("."),
            max_cells: int = 12, max_steps: int = 200, width: int = 240,
            max_tokens: int = 32000,
            dry_run: bool = False) -> dict:
    """Collect a run, build the payload, call the judge, write payload + analysis."""
    cells = collect_cells(name, harness)
    if not cells:
        raise SystemExit(f"no cells for run '{name}'"
                         + (f" / harness '{harness}'" if harness else ""))
    payload = build_payload(name, cells, max_cells=max_cells,
                            max_steps=max_steps, width=width)

    output.mkdir(parents=True, exist_ok=True)
    payload_path = output / f"payload-{name}.md"
    payload_path.write_text(payload + "\n")

    result = {"name": name, "cells": len(cells), "payload": str(payload_path),
              "analysis": None}
    if dry_run:
        return result
    analysis = call_judge(judge, payload, max_tokens=max_tokens)
    analysis_path = output / f"analysis-{name}.md"
    analysis_path.write_text(analysis + "\n")
    result["analysis"] = str(analysis_path)
    return result
