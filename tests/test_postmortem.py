"""Tests for the self-improvement postmortem digest."""

from __future__ import annotations

import json

from earth_agent_bench import postmortem as pm


def _cell(root, model, harness, cond, task, reward=0.0, timeout=False):
    d = root / f"eab-{task}-{model}-{harness}-{cond}-20260101-000000"
    d.mkdir(parents=True)
    ev = {"metrics": [{"reward": reward}]}
    if timeout:
        ev["exception_stats"] = {"AgentTimeoutError": 1}
    (d / "result.json").write_text(json.dumps({"stats": {"evals": {"e": ev}}}))
    return d


def test_build_digest_single_harness(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "RUNS_DIR", tmp_path)
    _cell(tmp_path, "m", "pi", "baseline", "t1", reward=0.5)
    _cell(tmp_path, "m", "opencode", "baseline", "t1", reward=0.5)
    d = pm.build_digest("m", harness="pi", run_start="")
    assert len(d.cells) == 1
    assert d.cells[0].condition == "baseline"
    assert d.cells[0].status == "partial"


def test_build_digest_all_harnesses_and_skips_improve(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "RUNS_DIR", tmp_path)
    _cell(tmp_path, "m", "pi", "baseline", "t1", reward=0.0, timeout=True)
    _cell(tmp_path, "m", "opencode", "baseline", "t1", reward=0.5)
    _cell(tmp_path, "m", "pi", "improve", "t1", reward=0.9)  # must be skipped
    d = pm.build_digest("m", harness="all", run_start="")
    harnesses = sorted({c.status for c in d.cells})
    assert len(d.cells) == 2                      # pi + opencode baseline, not improve
    assert "timeout" in harnesses and "partial" in harnesses
    assert all(c.condition != "improve" for c in d.cells)
