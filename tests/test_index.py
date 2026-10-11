"""Tests for the rebuildable run index (eab index)."""

from __future__ import annotations

import json

from earth_agent_bench import index as ix


def _fake_tree(root):
    trial = root / "eab-fake-task-model-pi-baseline-20260101-000000" / "fake-task__abc"
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({
        "config": {"agent": {"name": "pi", "model_name": "openai/local/Model"},
                   "task": {"path": "/x/harbor/generated/fake-task"}},
        "agent_result": {"n_input_tokens": 5, "n_output_tokens": 2, "n_cache_tokens": 0},
        "exception_info": {},
        "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:01:00Z",
    }))
    (trial / "verifier" / "reward.json").write_text(
        json.dumps({"reward": 0.4, "access_pattern": 0.4}))
    (trial / "agent" / "trajectory.json").write_text(
        json.dumps({"final_metrics": {"total_steps": 3}}))


def test_index_records(tmp_path):
    root = tmp_path / "harbor"
    _fake_tree(root)
    recs = ix.index_records(root)
    assert len(recs) == 1
    r = recs[0]
    assert r["task"] == "fake-task"
    assert r["harness"] == "pi"
    assert r["condition"] == "baseline"
    assert r["status"] == "partial"
    assert r["reward"] == 0.4
    assert r["components"]["access_pattern"] == 0.4
    assert r["steps"] == 3
    assert r["duration_sec"] == 60.0
    assert r["trajectory"].endswith("agent/trajectory.json")


def test_index_jsonl_and_csv(tmp_path):
    root = tmp_path / "harbor"
    _fake_tree(root)
    recs = ix.index_records(root)

    jl = tmp_path / "index.jsonl"
    ix.write_index(recs, jl, "jsonl")
    assert len(jl.read_text().splitlines()) == 1
    assert json.loads(jl.read_text())["model"] == "local/Model"

    cp = tmp_path / "index.csv"
    ix.write_index(recs, cp, "csv")
    header = cp.read_text().splitlines()[0]
    assert "access_pattern" in header and "condition" in header


def test_status_classification(tmp_path):
    assert ix._classify(1.0, "") == "solved"
    assert ix._classify(0.5, "") == "partial"
    assert ix._classify(0.0, "") == "fail"
    assert ix._classify(0.0, "AgentTimeoutError") == "timeout"
    assert ix._classify(0.0, "SomeError") == "error"
