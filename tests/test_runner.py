import json
from pathlib import Path

import pytest

from earth_agent_bench.runner import (
    RunSpec,
    build_command,
    prepare_run,
    validate_spec,
)

TASK = Path("benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml")


def make_spec(tmp_path, harness="opencode", condition="baseline", model="tiel-coder-35b"):
    return RunSpec(
        task_path=TASK, model_id=model, harness=harness,
        condition=condition, trial=1, runs_root=tmp_path / "runs",
    )


def test_prepare_creates_workspace(tmp_path):
    spec = make_spec(tmp_path)
    run_dir = prepare_run(spec)
    for name in ("instruction.md", "AGENTS.md", "manifest.json",
                 "observation.template.json", "opencode.jsonc", "session.log"):
        assert (run_dir / name).exists() or name == "session.log", name
    assert (run_dir / "output").is_dir()


def test_instruction_hides_gold(tmp_path):
    run_dir = prepare_run(make_spec(tmp_path))
    text = run_dir.joinpath("instruction.md").read_text()
    assert "primary_patterns" not in text
    assert "pattern_tiers" not in text
    assert "gold:" not in text


def test_manifest_and_observation(tmp_path):
    run_dir = prepare_run(make_spec(tmp_path))
    from earth_agent_bench.schemas import RunManifest, RunObservation

    manifest = RunManifest.model_validate(
        json.loads(run_dir.joinpath("manifest.json").read_text())
    )
    assert manifest.model_id == "tiel-coder-35b"
    assert manifest.model_tier == "local"
    assert manifest.condition == "baseline"

    observation = RunObservation.model_validate(
        json.loads(run_dir.joinpath("observation.template.json").read_text())
    )
    assert observation.task_id == "atmosphere/a1-tempo-no2-florida-2024"


def test_skills_condition_mounts_skills(tmp_path):
    run_dir = prepare_run(make_spec(tmp_path, condition="mcp-skills"))
    assert (run_dir / "skills").exists()
    assert (run_dir / "skills" / "data-access-patterns" / "SKILL.md").exists()
    assert "skills" in run_dir.joinpath("AGENTS.md").read_text()


def test_mcp_condition_wires_cmr(tmp_path):
    run_dir = prepare_run(make_spec(tmp_path, condition="mcp"))
    config = json.loads(run_dir.joinpath("opencode.jsonc").read_text())
    assert config["mcp"]["cmr"]["url"] == "https://cmr.earthdata.nasa.gov/mcp/v1"
    assert "{env:LITE_LLM_API_KEY}" in json.dumps(config)


def test_claude_lane_restriction(tmp_path):
    with pytest.raises(SystemExit):
        validate_spec(make_spec(tmp_path, harness="claude-code",
                                model="tiel-coder-35b"))
    validate_spec(make_spec(tmp_path, harness="claude-code",
                            model="claude-sonnet-5-5"))


def test_build_commands(tmp_path):
    spec = make_spec(tmp_path, harness="codex-cli")
    assert "codex exec" in " ".join(build_command(spec))
    spec = make_spec(tmp_path, harness="opencode")
    assert "litellm/local/Tiel-Coder-35B-A3B" in " ".join(build_command(spec))
    spec = make_spec(tmp_path, harness="claude-code", model="claude-sonnet-5-5")
    command = " ".join(build_command(spec))
    assert "claude -p" in command and "claude-sonnet-5-5" in command


EVAL_TASK = Path("experiments/evals/tasks/01_hls_open_vs_download.md")


def test_prepare_run_md_eval_task(tmp_path):
    spec = RunSpec(
        task_path=EVAL_TASK, model_id="tiel-coder-35b", harness="opencode",
        condition="baseline", trial=1, runs_root=tmp_path / "runs",
    )
    run_dir = prepare_run(spec)
    instruction = run_dir.joinpath("instruction.md").read_text()
    assert "open" in instruction.lower()
    assert "./output/answer.txt" in instruction
    assert not (run_dir / "observation.template.json").exists()
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text())
    assert manifest["task_id"] == "01_hls_open_vs_download"
