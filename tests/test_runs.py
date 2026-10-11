"""Tests for run-dir name parsing (the shared helper)."""

from __future__ import annotations

from earth_agent_bench.runs import RunRef, parse_job_dir, read_json


def test_parse_job_dir_full():
    ref = parse_job_dir(
        "eab-a3-maiac-aod-eastern-us-2023-tiel-coder-35b-pi-mcp-skills-20261011-005413")
    assert ref.task == "a3-maiac-aod-eastern-us-2023"
    assert ref.model == "tiel-coder-35b"
    assert ref.harness == "pi"
    assert ref.condition == "mcp-skills"      # dashes in condition
    assert ref.stamp == "20261011-005413"


def test_parse_job_dir_without_prefix_and_unknown():
    assert parse_job_dir("not-a-run-dir") == RunRef("not-a-run-dir")
    ref = parse_job_dir("eab-x-m-pi-baseline-20260101-000000",
                        models=["m"], harnesses=["pi"], conditions=["baseline"])
    assert (ref.task, ref.model, ref.harness, ref.condition) == ("x", "m", "pi", "baseline")


def test_read_json_best_effort(tmp_path):
    assert read_json(tmp_path / "missing.json") == {}
    (tmp_path / "bad.json").write_text("{not json")
    assert read_json(tmp_path / "bad.json") == {}
    (tmp_path / "ok.json").write_text('{"a": 1}')
    assert read_json(tmp_path / "ok.json") == {"a": 1}
