"""Tests for run config naming + the run manifest."""

from __future__ import annotations

from earth_agent_bench import runconfig as rc


def test_run_config_has_name():
    cfg = rc.load_run_config()
    assert cfg["name"]  # non-empty
    for key in ("models", "harnesses", "conditions", "concurrency"):
        assert key in cfg


def test_manifest_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "MANIFESTS_DIR", tmp_path)
    cfg = {"name": "exp-x", "models": ["m"], "harnesses": ["pi"],
           "conditions": ["baseline"], "tasks": "all", "trials": 1, "concurrency": 1}
    p = rc.write_manifest(cfg, "20260101-000000")
    assert p.name == "exp-x-20260101-000000.json"
    names = rc.load_manifest_names()
    assert names["20260101-000000"] == "exp-x"
