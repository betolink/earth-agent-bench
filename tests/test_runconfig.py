"""Tests for run config naming + the run manifest."""

from __future__ import annotations

import pytest

from earth_agent_bench import runconfig as rc


def test_run_config_has_name():
    cfg = rc.load_run_config()
    assert cfg["name"]  # non-empty
    for key in ("models", "harnesses", "conditions", "concurrency"):
        assert key in cfg


def test_run_config_path_resolution(tmp_path, monkeypatch):
    assert rc.run_config_path() == rc.RUN_YAML          # default
    assert rc.run_config_path(rc.RUN_YAML) == rc.RUN_YAML  # explicit, existing
    with pytest.raises(FileNotFoundError):
        rc.run_config_path("does-not-exist.yml")        # typo fails loudly
    # $EAB_RUN_CONFIG is honoured
    alt = tmp_path / "smart-external.yml"
    alt.write_text("name: alt\nmodels: []\n")
    monkeypatch.setenv(rc.RUN_CONFIG_ENV, str(alt))
    assert rc.run_config_path() == alt


def test_load_run_config_from_alternate_file(tmp_path):
    alt = tmp_path / "smart-external.yml"
    alt.write_text(
        "name: smart-ext\nmodels: [glm-5.3-flash]\nharnesses: [pi]\n"
        "conditions: [baseline]\ntasks: all\ntrials: 1\nconcurrency: 8\n")
    cfg = rc.load_run_config(alt)
    assert cfg["name"] == "smart-ext"
    assert cfg["concurrency"] == 8
    assert cfg["models"] == ["glm-5.3-flash"]
    assert cfg["config_path"] == str(alt)


def test_manifest_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "MANIFESTS_DIR", tmp_path)
    cfg = {"name": "exp-x", "models": ["m"], "harnesses": ["pi"],
           "conditions": ["baseline"], "tasks": "all", "trials": 1, "concurrency": 1}
    p = rc.write_manifest(cfg, "20260101-000000")
    assert p.name == "exp-x-20260101-000000.json"
    names = rc.load_manifest_names()
    assert names["20260101-000000"] == "exp-x"
