"""Aggregate Harbor runs into a per-model report.

Borrowed from clusterfunk/intelligence-index's export step: one place that reads
the runs on disk and emits a compact table (reward / pass / tokens) so a model
comparison is reproducible without hand-tallying run directories.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HARBOR_RUNS = REPO_ROOT / "runs" / "harbor"


def _condition(job_name: str) -> str:
    """Condition parsed from a Harbor job dir name ('' if not a run dir)."""
    from .runs import parse_job_dir
    return parse_job_dir(job_name or "").condition or "?"


def collect(root: Path = DEFAULT_HARBOR_RUNS) -> list[dict]:
    """Read every completed Harbor run dir into flat records."""
    rows: list[dict] = []
    for run_dir in sorted(root.glob("eab-*")):
        cfg_path, res_path = run_dir / "config.json", run_dir / "result.json"
        if not (cfg_path.exists() and res_path.exists()):
            continue
        try:
            cfg = json.loads(cfg_path.read_text())
            res = json.loads(res_path.read_text())
        except Exception:  # noqa: BLE001
            continue
        agent = (cfg.get("agents") or [{}])[0]
        model = (agent.get("model_name") or "").replace("openai/", "").replace("anthropic/", "")
        harness = agent.get("name", "")
        tasks = [Path(t["path"]).name for t in cfg.get("tasks", [])]
        stats = res.get("stats", {})
        reward = None
        for eval_block in stats.get("evals", {}).values():
            metrics = eval_block.get("metrics") or []
            if metrics and metrics[0].get("mean") is not None:
                reward = metrics[0]["mean"]
        rows.append({
            "task": tasks[0] if tasks else "",
            "model": model,
            "harness": harness,
            "condition": _condition(cfg.get("job_name", run_dir.name)),
            "reward": reward,
            "in_tokens": stats.get("n_input_tokens"),
            "cache_tokens": stats.get("n_cache_tokens"),
            "out_tokens": stats.get("n_output_tokens"),
            "errored": stats.get("n_errored_trials", 0),
            "run": run_dir.name,
        })
    return rows


def summarize(rows: list[dict], by: tuple[str, ...] = ("model",)) -> list[dict]:
    """Aggregate collected runs into per-(model,condition) stats."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[b] for b in by)].append(row)
    out: list[dict] = []
    for key, items in sorted(groups.items()):
        scored = [r for r in items if r["reward"] is not None]
        rewards = [r["reward"] for r in scored]
        record = dict(zip(by, key, strict=False))
        record.update({
            "n": len(items),
            "n_scored": len(scored),
            "n_errored": sum(int(r.get("errored") or 0) for r in items),
            "mean_reward": round(sum(rewards) / len(rewards), 3) if rewards else None,
            "pass_rate": round(sum(1 for r in rewards if r >= 0.999) / len(rewards), 3) if rewards else None,
            "in_tokens": sum(int(r.get("in_tokens") or 0) for r in items),
            "out_tokens": sum(int(r.get("out_tokens") or 0) for r in items),
        })
        out.append(record)
    return out


def to_markdown(rows: list[dict], by: tuple[str, ...] = ("model",)) -> str:
    """Render the summary as a Markdown table."""
    summary = summarize(rows, by=by)
    cols = list(by) + ["n", "n_scored", "n_errored", "mean_reward", "pass_rate", "in_tokens", "out_tokens"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for record in summary:
        lines.append("| " + " | ".join(str(record.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def main(root: Path = DEFAULT_HARBOR_RUNS, by: tuple[str, ...] = ("model",)) -> str:
    """CLI entry: print a report for the runs tree."""
    return to_markdown(collect(root), by=by)
