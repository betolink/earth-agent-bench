"""Tests for trial trajectory/metadata resolution (eab trajectory)."""

from __future__ import annotations

import json

from earth_agent_bench import trajectory as tj


def _fake_trial(root, *, task="fake-task", model="model", harness="pi",
                condition="baseline", stamp="20260101-000000"):
    job = root / f"eab-{task}-{model}-{harness}-{condition}-{stamp}"
    trial = job / f"{task}__abc123"
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({
        "config": {"agent": {"name": harness, "model_name": f"openai/local/{model}",
                             "kwargs": {"model_api": "openai-completions"},
                             "env": {}, "skills": []}},
        "agent_info": {"version": "1.0", "model_info": {"provider": "openai"}},
        "agent_result": {"n_input_tokens": 10, "n_output_tokens": 3,
                         "n_cache_tokens": 0, "cost_usd": None},
        "exception_info": {}, "started_at": "t0", "finished_at": "t1",
    }))
    (trial / "verifier" / "reward.json").write_text(
        json.dumps({"reward": 0.5, "access_pattern": 0.5, "efficiency": 0.0}))
    (trial / "verifier" / "details.json").write_text(json.dumps({"reward": 0.5}))
    (trial / "agent" / "trajectory.json").write_text(json.dumps({
        "schema_version": "ATIF-v1.7", "session_id": "s",
        "steps": [{"step_id": 1, "source": "user", "message": "do the thing"}],
        "final_metrics": {},
    }))
    return trial


def test_find_and_bundle(tmp_path, monkeypatch):
    root = tmp_path / "harbor"
    _fake_trial(root)
    monkeypatch.setattr(tj, "RUNS_DIR", root)

    trials = tj.find_trials("fake-task", "model", "pi")
    assert len(trials) == 1
    assert trials[0].condition == "baseline"

    b = tj.build_bundle(trials[0], "fake-task", "model", "pi")
    assert b["run"]["condition"] == "baseline"
    assert b["agent"]["name"] == "pi"
    assert b["agent"]["provider"] == "openai"
    assert b["agent"]["params"] == {"model_api": "openai-completions"}
    assert b["task"]["instruction"] == "do the thing"
    assert b["metrics"]["reward"] == 0.5
    assert b["metrics"]["n_input_tokens"] == 10
    assert b["trajectory"]["schema_version"] == "ATIF-v1.7"
    # environment reflects the condition semantics from conditions.yaml
    assert b["environment"]["mcp"] is False
    assert b["environment"]["skills"] is False


def test_latest_is_chronological(tmp_path, monkeypatch):
    root = tmp_path / "harbor"
    _fake_trial(root, condition="baseline", stamp="20260101-000000")
    _fake_trial(root, condition="skills", stamp="20260102-000000")
    _fake_trial(root, condition="mcp-skills", stamp="20260103-000000")
    monkeypatch.setattr(tj, "RUNS_DIR", root)

    trials = tj.find_trials("fake-task", "model", "pi")
    assert [t.stamp for t in trials] == ["20260101-000000", "20260102-000000",
                                         "20260103-000000"]
    assert trials[-1].condition == "mcp-skills"


def test_artifact_formats(tmp_path, monkeypatch):
    root = tmp_path / "harbor"
    trial_dir = _fake_trial(root)
    monkeypatch.setattr(tj, "RUNS_DIR", root)
    t = tj.find_trials("fake-task", "model", "pi")[0]

    assert tj.artifact(t, "atif", "pi") == trial_dir / "agent" / "trajectory.json"
    assert tj.artifact(t, "reward", "pi") == trial_dir / "verifier" / "reward.json"
    assert tj.read_artifact(trial_dir / "agent" / "trajectory.json")["schema_version"] == "ATIF-v1.7"


def test_resolve_task_id():
    # real benchmark task ids live in benchmark/tasks/access-pattern/**.yaml
    assert tj.resolve_task_id("a1-tempo-no2-florida-2024") == "a1-tempo-no2-florida-2024"
    assert tj.resolve_task_id("a1").startswith("a1-")
