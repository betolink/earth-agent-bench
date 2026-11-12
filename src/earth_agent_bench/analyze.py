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
import time
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
  `mcp-skills`.
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

VERIFY_ASK = """\
You are fact-checking a benchmark postmortem against authoritative data.

You get (1) a DRAFT postmortem and (2) a FACTS bundle computed directly from the
run: the results table and a per-cell evidence index (status, reward, component
scores, the observed access route, exec status, code-check flags, efficiency).

Do this:
1. For every **numeric** claim (means, counts, "X of Y", timeouts, scores), check it
   against the facts; correct any mismatch.
2. For every **per-cell** claim (which route a cell took, its status/reward), check it
   against the per-cell evidence; correct any mismatch.
3. For **causal** claims ("because…", "caused by…"), you CANNOT confirm them from the
   facts alone — keep one only if consistent with the observed evidence, and mark it
   "(hypothesis)" when it goes beyond what the facts show.
4. Return a short **Corrections** list (what changed and why), then the
   **corrected, complete postmortem**.

Never invent cells, routes, or numbers not present in the facts.
"""


def _signature(batches: list, judge: str, max_steps: int, width: int, max_cells: int,
               reasoning_effort: str | None) -> str:
    """Stable hash of the batch structure + params — detects a stale resume."""
    import hashlib

    src = json.dumps({
        "judge": judge, "max_steps": max_steps, "width": width,
        "max_cells": max_cells, "reasoning_effort": reasoning_effort,
        "batches": [[[k[0], k[1], k[2], sorted(c.get("trial", "") for c in cs)]
                     for k, cs in chunk] for chunk in batches],
    }, sort_keys=True)
    return hashlib.sha256(src.encode()).hexdigest()[:16]


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


def _group_rows(cells: list[dict]) -> list[tuple[tuple, list[dict]]]:
    """Cells grouped into rows (model × harness × condition), ordered."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for c in cells:
        buckets[(c["model"], c["harness"], c["condition"])].append(c)
    return [(k, buckets[k]) for k in sorted(buckets)]


def build_payload(name: str, batch_cells: list[dict], all_cells: list[dict],
                  batch_rows: list[str], prior_summary: str = "",
                  max_steps: int = 80, width: int = 240) -> str:
    """The judge prompt for one batch: context → task → prior draft → rows → ATIF.

    The whole-run table is included every call; the trajectories are just this
    batch's cells. ``prior_summary`` is the rolling postmortem so far.
    """
    parts = [
        "# Benchmark analysis — update the running postmortem",
        "",
        "## Context",
        CONTEXT,
        "## Your task",
        ASK,
        "Return the **complete** postmortem (headline · routes taken · failure modes · "
        "condition effect · recommendations · results table). Keep all prior findings "
        "and extend/revise them with this batch — never drop rows you already analyzed.",
        "",
        "## Current postmortem (draft so far)",
        prior_summary.strip() or "(none yet — start it)",
        "",
        f"## Run `{name}` — batch: {', '.join(batch_rows)}",
        "",
        "### Whole-run results so far",
        _results_table(all_cells),
        "",
        "### This batch's trajectories (ATIF, condensed)",
        "",
    ]
    parts += [_cell_block(c, max_steps, width) for c in batch_cells]
    return "\n".join(parts)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def build_evidence(cells: list[dict]) -> str:
    """Compact, code-derived facts: results table + per-cell route/status evidence.

    Deliberately small (~300-500 B/cell) so the verify pass never re-reads the
    trajectories.
    """
    lines = ["### Results table (authoritative)", _results_table(cells), "",
             "### Per-cell evidence (authoritative)", ""]
    for c in sorted(cells, key=lambda c: (c["model"], c["condition"], c["task"])):
        comp = c.get("components") or {}
        det = _read_json(tj.REPO_ROOT / c["details_path"]) if c.get("details_path") else {}
        obs = det.get("access_pattern_details") or {}
        cc = det.get("code_check") or {}
        eff = det.get("efficiency_metrics") or {}
        lines.append(
            f"- {c['task']} · {c['model']}/{c['harness']}/{c['condition']} — "
            f"reward={c['reward']} status={c['status']} "
            f"ap={comp.get('access_pattern')} sd={comp.get('service_discovery')} "
            f"repr={comp.get('representation')} eff={comp.get('efficiency')} "
            f"val={comp.get('validation')}")
        lines.append(
            f"    observed={obs.get('observed_patterns')} "
            f"class={obs.get('observed_classifications')} gold={obs.get('primary_gold')} "
            f"best={obs.get('best_available')} gap={obs.get('gap_reason')!r}")
        lines.append(
            f"    exec={det.get('exec_status')} sanctioned={cc.get('sanctioned')} "
            f"earthaccess={cc.get('uses_earthaccess')} virtualize={cc.get('uses_virtualize')} "
            f"open={cc.get('uses_open')} raw_cmr={cc.get('raw_cmr')} "
            f"raw_fetch={cc.get('raw_url_fetch')} bytes={eff.get('bytes_read')} "
            f"objects={eff.get('objects_read')} runtime={eff.get('runtime_seconds')}")
        if c.get("exception"):
            lines.append(f"    exception={c['exception']}")
    return "\n".join(lines)


def verify(name: str, judge: str, cells: list[dict], draft: str,
           reasoning_effort: str | None = "high", max_tokens: int = 32000,
           timeout: int = 1200, on_progress=None) -> tuple[str, str]:
    """Fact-check + merge the draft against a compact evidence bundle.

    Returns ``(payload, corrected)``. Input is bounded by the draft + the evidence
    index (~10-20K tokens) — the trajectories are NOT re-sent.
    """
    payload = "\n".join([
        "# Verify & correct the postmortem", "", VERIFY_ASK,
        "## FACTS (authoritative — trust these over the draft)", "",
        build_evidence(cells), "",
        "## DRAFT postmortem (to correct)", "", draft,
    ])
    corrected = call_judge(judge, payload, max_tokens=max_tokens, timeout=timeout,
                           on_progress=on_progress, reasoning_effort=reasoning_effort)
    return payload, corrected


def call_judge(model: str, payload: str, max_tokens: int = 32000, timeout: int = 1200,
               on_progress=None, reasoning_effort: str | None = "low") -> str:
    """Send the payload to a judge model on the gateway; return its reply (streamed).

    ``model`` may be a roster id (resolved via models.yaml) or a raw gateway id
    (e.g. ``zai/glm-5.3-flash``). Streamed (SSE) so long generations don't hit the
    proxy's idle timeout (HTTP 524). ``on_progress(chars_out, chars_reasoning,
    elapsed_s)`` is called every ~10 s so the caller can show a heartbeat.

    NOTE: many ``glm-*`` "flash" models are **reasoning** models — they spend
    ``max_tokens`` on hidden ``reasoning_content`` before any answer (we measured
    ~27 K reasoning tokens per batch on ``glm-5.3-flash``). ``reasoning_effort="low"``
    disables it (~7x faster); pass ``None`` to leave the model's default on.
    """
    import os
    from urllib.request import Request, urlopen

    from .wiring import gateway_base, litellm_model

    resolved = litellm_model(model)
    key = (os.environ.get("LITE_LLM_API_KEY")
           or os.environ.get("LITELLM_API_KEY") or "")
    body = {"model": resolved, "messages": [{"role": "user", "content": payload}],
            "max_tokens": max_tokens, "temperature": 0, "stream": True}
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    req = Request(f"{gateway_base()}/v1/chat/completions",
                  data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json",
                           "Accept": "text/event-stream",
                           "User-Agent": "earth-agent-bench/0.1",
                           "Authorization": f"Bearer {key}"},
                  method="POST")
    parts: list[str] = []
    n_out = n_reason = 0
    started = last = time.time()
    try:
        response = urlopen(req, timeout=timeout)  # noqa: S310
    except OSError as e:
        base = gateway_base()
        raise SystemExit(
            f"cannot reach the LiteLLM gateway at {base}: {e}\n"
            "Set LITE_LLM_ENDPOINT (and LITE_LLM_API_KEY) — e.g. source your .env:\n"
            "  set -a; . ./.env; set +a") from None
    with response:
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
            if delta.get("reasoning_content"):
                n_reason += len(delta["reasoning_content"])
            if delta.get("content"):
                c = delta["content"]
                parts.append(c)
                n_out += len(c)
            if on_progress and time.time() - last >= 10:
                on_progress(n_out, n_reason, time.time() - started)
                last = time.time()
    return "".join(parts)


def analyze(name: str, judge: str, harness: str | None = None, output: Path = Path("."),
            batch: int = 1, max_steps: int = 80, width: int = 240, max_cells: int = 0,
            max_tokens: int = 32000, timeout: int = 1200, reasoning_effort: str | None = "low",
            dry_run: bool = False, progress: bool = True, resume: bool = True,
            verify_pass: bool = False, verify_effort: str | None = "high") -> dict:
    """Analyze a run in batches of rows, maintaining a rolling postmortem.

    Splits the run's rows (model × harness × condition) into batches of ``batch``;
    each judge call receives the postmortem so far + the batch's trajectories and
    returns the **updated complete postmortem**. The last one is written to
    ``analysis-<name>.md``; per-batch drafts go to ``analysis-<name>/batch-NN.*``.

    **Resume**: a completed batch is a non-empty ``batch-NN.summary.md``; with
    ``resume`` (default) an interrupted run continues from the last one, using its
    summary as the rolling draft. A ``meta.json`` signature of (params + cells per
    batch) guards against resuming on changed inputs.

    ``verify_pass`` adds a final reasoning-``verify_effort`` call that fact-checks
    the merged postmortem against a compact evidence index (results table + per-cell
    route/status) — it does **not** re-read the trajectories.
    """
    from rich.console import Console

    cells = collect_cells(name, harness)
    if not cells:
        raise SystemExit(f"no cells for run '{name}'"
                         + (f" / harness '{harness}'" if harness else ""))
    rows = _group_rows(cells)
    batches = ([rows] if batch <= 0 or batch >= len(rows)
               else [rows[i:i + batch] for i in range(0, len(rows), batch)])

    outdir = output / f"analysis-{name}"
    outdir.mkdir(parents=True, exist_ok=True)
    con = Console(stderr=True) if progress else None
    if con:
        from .wiring import gateway_base, litellm_model
        con.print(f"[dim]judge={litellm_model(judge)} @ {gateway_base()}[/dim]")

    sig = _signature(batches, judge, max_steps, width, max_cells, reasoning_effort)
    meta_path = outdir / "meta.json"
    prev = _read_json(meta_path)
    start, summary = 0, ""
    if resume and not dry_run and prev.get("signature") == sig:
        for i in range(len(batches)):
            f = outdir / f"batch-{i:02d}.summary.md"
            if f.is_file() and f.read_text().strip():
                start, summary = i + 1, f.read_text()
            else:
                break
    elif resume and not dry_run and prev and prev.get("signature") != sig:
        if con:
            con.print("[yellow]inputs changed since the last run — starting fresh[/yellow]")

    if not dry_run:
        meta_path.write_text(json.dumps({
            "signature": sig, "judge": judge, "batch": batch, "max_steps": max_steps,
            "width": width, "max_cells": max_cells, "reasoning_effort": reasoning_effort,
            "rows": [[k[0], k[1], k[2]] for k, _ in rows], "batches": len(batches),
        }, indent=2) + "\n")

    result = {"name": name, "cells": len(cells), "rows": len(rows),
              "batches": len(batches), "dir": str(outdir), "analysis": None,
              "verified": None, "resumed_from": start, "elapsed": 0.0}
    if con and start:
        con.print(f"[green]resuming[/green] — {start}/{len(batches)} batch(es) already done")

    def _beat(n_out, n_reason, el):
        if con:
            con.print(f"  [dim]… {n_out:,} out · {n_reason:,} reasoning · {el:.0f}s[/dim]")

    t_start = time.time()
    for i, chunk in enumerate(batches):
        if i < start:
            if con:
                con.print(f"[dim]batch {i + 1}/{len(batches)} — cached[/dim]")
            continue
        batch_cells = [c for _, cs in chunk for c in cs]
        if max_cells and len(batch_cells) > max_cells:
            batch_cells = batch_cells[:max_cells]
        batch_rows = [f"{k[0]}/{k[1]}/{k[2]}" for k, _ in chunk]
        prompt = build_payload(name, batch_cells, cells, batch_rows, summary,
                               max_steps=max_steps, width=width)
        (outdir / f"batch-{i:02d}.payload.md").write_text(prompt + "\n")
        if dry_run:
            continue
        if con:
            con.print(f"[cyan]batch {i + 1}/{len(batches)}[/cyan] "
                      f"{', '.join(batch_rows)} · ~{len(prompt) // 4:,} tok in "
                      f"· {len(batch_cells)} traj"
                      + (f" (of {len([c for _, cs in chunk for c in cs])})"
                         if max_cells else ""))
        t0 = time.time()
        summary = call_judge(judge, prompt, max_tokens=max_tokens, timeout=timeout,
                             on_progress=_beat, reasoning_effort=reasoning_effort)
        (outdir / f"batch-{i:02d}.summary.md").write_text(summary + "\n")
        if con:
            con.print(f"  [green]done[/green] {len(summary):,} chars in {time.time() - t0:.0f}s")

    if dry_run:
        result["elapsed"] = time.time() - t_start
        return result

    analysis_path = output / f"analysis-{name}.md"
    analysis_path.write_text(summary + "\n")
    result["analysis"] = str(analysis_path)

    if verify_pass and summary.strip():
        if con:
            con.print(f"[cyan]verify[/cyan] fact-checking against the evidence index "
                      f"(reasoning={verify_effort})")
        vpayload, corrected = verify(name, judge, cells, summary,
                                     reasoning_effort=verify_effort, max_tokens=max_tokens,
                                     timeout=timeout, on_progress=_beat)
        (outdir / "verify.payload.md").write_text(vpayload + "\n")
        (outdir / "verify.summary.md").write_text(corrected + "\n")
        vpath = output / f"analysis-{name}-verified.md"
        vpath.write_text(corrected + "\n")
        result["verified"] = str(vpath)

    result["elapsed"] = time.time() - t_start
    return result
