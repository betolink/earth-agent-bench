from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from earth_agent_bench.harbor import (
    generate_package,
    render_harbor_command,
    resolve_task,
    resolve_tasks,
    run_harbor,
    write_job_config,
)
from earth_agent_bench.harbor.config import RUNTIME_DIR

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_TASK = "experiments/evals/tasks/01_hls_open_vs_download.md"
BENCH_TASK = "benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml"


def _toml(package: Path) -> dict:
    return tomllib.loads((package / "task.toml").read_text())


def _run_verifier(package: Path, workspace: Path, logs: Path, extra: list[str] | None = None):
    command = [
        sys.executable,
        str(package / "tests" / "verify.py"),
        "--workspace",
        str(workspace),
        "--logs",
        str(logs),
        *(extra or []),
    ]
    return subprocess.run(command, capture_output=True, text=True)


# --- task resolution -------------------------------------------------------

def test_alias_resolution():
    assert resolve_task("cryo-1").stem == "c1-itslive-jakobshavn-2015-2024"
    assert resolve_task("atmo-2").stem == "a2-emit-methane-permian-2024"
    assert resolve_task("solid-3").stem == "s3-central-valley-subsidence-2015-2024"
    assert resolve_task("l1").stem.startswith("l1-")
    assert resolve_task("atmosphere/a1-tempo-no2-florida-2024").parent.name == "atmosphere"
    assert resolve_task("01_hls_open_vs_download").name == "01_hls_open_vs_download.md"


def test_alias_lists():
    assert len(resolve_tasks("pilot")) == 3
    assert len(resolve_tasks("all")) == 28  # 18 benchmark + 10 eval
    assert len(resolve_tasks("cryo-1,atmo-2")) == 2


def test_resolve_tasks_dir_and_glob():
    assert len(resolve_tasks("benchmark/tasks")) == 18
    assert len(resolve_tasks("experiments/evals/tasks")) == 10
    assert len(resolve_tasks("benchmark/tasks/*/*.yaml")) == 18


def test_alias_errors():
    with pytest.raises(SystemExit):
        resolve_task("not-a-sphere-9")
    with pytest.raises(SystemExit):
        resolve_task("")


# --- package generation ----------------------------------------------------

def test_generate_eval_package(tmp_path):
    package = generate_package(EVAL_TASK, "baseline", tmp_path)
    for name in (
        "instruction.md", "task.toml",
        "environment/Dockerfile", "environment/agent-requirements.txt",
        "tests/test.sh", "tests/verify.py", "tests/gold.json",
        "tests/earth_agent_bench/evals.py", "solution/solve.sh",
    ):
        assert (package / name).exists(), name

    config = _toml(package)
    assert config["schema_version"] == "1.4"
    assert config["agent"]["timeout_sec"] == 900.0
    assert config["verifier"]["timeout_sec"] == 600.0
    assert config["environment"]["network_mode"] == "public"
    env = config["environment"]["env"]
    assert env["EARTHDATA_USERNAME"] == "${EARTHDATA_USERNAME:-}"
    assert env["EARTHDATA_PASSWORD"] == "${EARTHDATA_PASSWORD:-}"
    assert env["EARTHDATA_TOKEN"] == "${EARTHDATA_TOKEN:-}"

    gold = json.loads((package / "tests" / "gold.json").read_text())
    assert gold["answer_type"] == "label"
    assert gold["answer"] == "open"

    assert "./output/answer.txt" in (package / "instruction.md").read_text()
    requirements = (package / "environment" / "agent-requirements.txt").read_text()
    assert "github.com/betolink/earthaccess" in requirements
    assert requirements == (RUNTIME_DIR / "agent-requirements.txt").read_text()


def test_generate_benchmark_package(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    assert (package / "tests" / "task.yaml").exists()
    assert (package / "tests" / "earth_agent_bench" / "scoring" / "aggregate.py").exists()
    assert not (package / "tests" / "gold.json").exists()
    config = _toml(package)
    assert config["task"]["name"] == "earth-agent-bench/a1-tempo-no2-florida-2024"
    text = (package / "instruction.md").read_text()
    assert "primary_patterns" not in text and "gold:" not in text


def test_mcp_condition_declares_servers(tmp_path):
    package = generate_package(EVAL_TASK, "mcp", tmp_path)
    config = _toml(package)
    servers = config["environment"]["mcp_servers"]
    assert servers and servers[0]["name"] == "cmr"
    assert servers[0]["url"] == "https://cmr.earthdata.nasa.gov/mcp/v1"
    assert "skills_dir" not in config["environment"]


def test_skills_condition_sets_skills_dir(tmp_path):
    package = generate_package(EVAL_TASK, "skills", tmp_path)
    config = _toml(package)
    assert config["environment"]["skills_dir"] == "/harbor/skills"
    assert "mcp_servers" not in config["environment"]


def test_baseline_has_no_condition_wiring(tmp_path):
    package = generate_package(EVAL_TASK, "baseline", tmp_path)
    config = _toml(package)
    assert "skills_dir" not in config["environment"]
    assert "mcp_servers" not in config["environment"]


# --- verifier end-to-end ---------------------------------------------------

def test_eval_verifier_grades_answer(tmp_path):
    package = generate_package(EVAL_TASK, "baseline", tmp_path)
    workspace = tmp_path / "ws"
    (workspace / "output").mkdir(parents=True)
    logs = tmp_path / "logs"

    (workspace / "output" / "answer.txt").write_text("  Open \n")
    run = _run_verifier(package, workspace, logs)
    assert run.returncode == 0, run.stderr
    assert json.loads((logs / "reward.json").read_text())["reward"] == 1.0

    (workspace / "output" / "answer.txt").write_text("download")
    _run_verifier(package, workspace, logs)
    assert json.loads((logs / "reward.json").read_text())["reward"] == 0.0

    (workspace / "output" / "answer.txt").unlink()
    _run_verifier(package, workspace, logs)
    assert json.loads((logs / "reward.json").read_text())["reward"] == 0.0


def test_eval_verifier_finds_answer_in_search_root(tmp_path):
    package = generate_package(EVAL_TASK, "baseline", tmp_path)
    workspace = tmp_path / "empty"
    workspace.mkdir()
    alt = tmp_path / "alt"
    (alt / "output").mkdir(parents=True)
    (alt / "output" / "answer.txt").write_text("open")
    logs = tmp_path / "logs"
    run = _run_verifier(package, workspace, logs, extra=["--search-root", str(alt)])
    assert run.returncode == 0, run.stderr
    assert json.loads((logs / "reward.json").read_text())["reward"] == 1.0


def test_benchmark_verifier_handles_empty_summary(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    workspace = tmp_path / "ws"
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "access_summary.json").write_text(json.dumps({}))
    logs = tmp_path / "logs"
    run = _run_verifier(package, workspace, logs)
    assert run.returncode == 0, run.stderr
    assert json.loads((logs / "reward.json").read_text())["reward"] == 0.0


def test_benchmark_verifier_reward_json_is_numeric(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    workspace = tmp_path / "ws"
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "observation.json").write_text(json.dumps({
        "task_id": "atmosphere/a1-tempo-no2-florida-2024",
        "observed_patterns": ["C1"],
        "collection_short_names": ["TEMPO_NO2_L3"],
        "discovered_services": [],
        "representation": "lazy",
        "validation_passed": True,
        "metrics": {"bytes_read": 1, "objects_read": 1, "runtime_seconds": 1.0},
    }))
    logs = tmp_path / "logs"
    run = _run_verifier(package, workspace, logs)
    assert run.returncode == 0, run.stderr
    rewards = json.loads((logs / "reward.json").read_text())
    assert rewards and all(
        isinstance(v, (int, float)) and not isinstance(v, bool)
        for v in rewards.values()
    )
    assert "access_pattern_details" not in rewards
    details = json.loads((logs / "details.json").read_text())
    assert "access_pattern_details" in details


def test_benchmark_verifier_uses_observed_events(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    workspace = tmp_path / "ws"
    (workspace / "output").mkdir(parents=True)
    # Misleading/empty self-report; the observed events are the ground truth.
    (workspace / "output" / "access_summary.json").write_text(json.dumps({}))
    events = [
        {"function": "earthaccess.search_data", "short_name": "TEMPO_NO2_L3",
         "service": None, "pattern": None, "n_result": 30, "error": None,
         "duration_s": 1.0},
        {"function": "earthaccess.virtualize", "service": "virtual_zarr",
         "pattern": "C1", "n_result": 1, "error": None, "duration_s": 5.0},
    ]
    (workspace / "access_events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n"
    )
    logs = tmp_path / "logs"
    run = _run_verifier(package, workspace, logs)
    assert run.returncode == 0, run.stderr
    rewards = json.loads((logs / "reward.json").read_text())
    details = json.loads((logs / "details.json").read_text())
    assert rewards["access_pattern"] == 1.0
    assert rewards["collection_selection"] == 1.0
    assert rewards["validation"] == 1.0
    assert rewards["representation"] == 1.0
    assert details["access_pattern_details"]["observed_patterns"] == ["C1"]


def test_instrumenter_patches_and_logs(tmp_path, monkeypatch):
    import importlib.util
    import sys as _sys
    import types

    path = tmp_path / "eab_instrument.py"
    path.write_text((RUNTIME_DIR / "eab_instrument.py").read_text())
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("EAB_ACCESS_LOG", str(log))

    spec = importlib.util.spec_from_file_location("eab_instrument_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fake = types.ModuleType("earthaccess")
    fake.open = lambda *args, **kwargs: ["obj", "obj2"]
    monkeypatch.setitem(_sys.modules, "earthaccess", fake)
    module._patch("earthaccess", "open", None, "C1")
    fake.open("x", short_name="ATL06")

    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert events[0]["function"] == "earthaccess.open"
    assert events[0]["short_name"] == "ATL06"
    assert events[0]["pattern"] == "C1"
    assert events[0]["n_result"] == 2


def test_instrumenter_patches_dotted_attributes(tmp_path, monkeypatch):
    import importlib.util
    import sys as _sys
    import types

    path = tmp_path / "eab_instrument.py"
    path.write_text((RUNTIME_DIR / "eab_instrument.py").read_text())
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("EAB_ACCESS_LOG", str(log))

    spec = importlib.util.spec_from_file_location("eab_instrument_dotted", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class S3FileSystem:
        def open(self, *args, **kwargs):
            return "handle"

    s3fs = types.ModuleType("s3fs")
    s3fs.S3FileSystem = S3FileSystem
    monkeypatch.setitem(_sys.modules, "s3fs", s3fs)

    module._patch("s3fs", "S3FileSystem.open", None, "C1")
    assert S3FileSystem().open("bucket/key") == "handle"

    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert events[0]["function"] == "s3fs.S3FileSystem.open"
    assert events[0]["pattern"] == "C1"


def test_benchmark_instruction_uses_absolute_output_path(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    assert "/app/output/" in (package / "instruction.md").read_text()


def test_benchmark_verifier_scores_access_summary(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    workspace = tmp_path / "ws"
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "artifact.nc").write_bytes(b"placeholder")
    (workspace / "output" / "access_summary.json").write_text(json.dumps({
        "collections": ["TEMPO_NO2_L3"],
        "access_services_used": ["virtualization", "harmony"],
        "bytes_read_estimate": 45_000_000,
        "pattern_notes": "virtualized the archive, lazy monthly means",
    }))
    logs = tmp_path / "logs"

    run = _run_verifier(package, workspace, logs)
    assert run.returncode == 0, run.stderr
    rewards = json.loads((logs / "reward.json").read_text())
    assert rewards["access_pattern"] == 1.0
    assert rewards["collection_selection"] == 1.0
    assert rewards["reward"] > 0.8


# --- JobConfig + harbor invocation -----------------------------------------

def test_job_config_opencode_model_and_skills(tmp_path):
    generate_package(EVAL_TASK, "mcp-skills", tmp_path)
    job_path = write_job_config(EVAL_TASK, "tiel-coder-35b", "opencode", "mcp-skills", tmp_path)
    job = yaml.safe_load(job_path.read_text())
    agent = job["agents"][0]
    assert agent["name"] == "opencode"
    assert agent["model_name"] == "litellm/local/Tiel-Coder-35B-A3B"
    assert agent["env"]["OPENAI_API_KEY"] == "${LITELLM_API_KEY:-}"
    assert agent["env"]["OPENAI_BASE_URL"].endswith("/v1")
    assert agent["skills"]
    assert job["n_attempts"] == 1


def test_job_config_codex_maps_to_codex_agent(tmp_path):
    generate_package(EVAL_TASK, "baseline", tmp_path)
    job = yaml.safe_load(
        write_job_config(EVAL_TASK, "glm-5.3-flash", "codex-cli", "baseline", tmp_path).read_text()
    )
    agent = job["agents"][0]
    assert agent["name"] == "codex"
    assert agent["model_name"] == "openai/zai/glm-5.3-flash"
    assert "skills" not in agent


def test_job_config_pi_has_model_api_kwarg(tmp_path):
    generate_package(EVAL_TASK, "baseline", tmp_path)
    job = yaml.safe_load(
        write_job_config(EVAL_TASK, "tiel-coder-35b", "pi", "baseline", tmp_path).read_text()
    )
    assert job["agents"][0]["kwargs"] == {"model_api": "openai-completions"}


def test_job_config_claude_lane(tmp_path):
    generate_package(EVAL_TASK, "baseline", tmp_path)
    job = yaml.safe_load(
        write_job_config(EVAL_TASK, "claude-sonnet-5-5", "claude-code", "baseline", tmp_path).read_text()
    )
    agent = job["agents"][0]
    assert agent["name"] == "claude-code"
    assert agent["model_name"] == "anthropic/copilot/claude-sonnet-5.5"
    assert "ANTHROPIC_API_KEY" in agent["env"]

    # claude-code is allowed on any roster model when ANTHROPIC_BASE_URL points
    # at the LiteLLM gateway (anthropic-compatible /v1/messages).
    job2 = yaml.safe_load(
        write_job_config(EVAL_TASK, "tiel-coder-35b", "claude-code", "baseline", tmp_path).read_text()
    )
    assert job2["agents"][0]["name"] == "claude-code"
    assert job2["agents"][0]["model_name"] == "anthropic/local/Tiel-Coder-35B-A3B"


def test_unknown_harness_and_model_rejected(tmp_path):
    generate_package(EVAL_TASK, "baseline", tmp_path)
    with pytest.raises(SystemExit):
        write_job_config(EVAL_TASK, "tiel-coder-35b", "nope", "baseline", tmp_path)
    with pytest.raises(SystemExit):
        write_job_config(EVAL_TASK, "no-such-model", "opencode", "baseline", tmp_path)


def test_render_command_uses_real_harbor_flags(tmp_path):
    generate_package(EVAL_TASK, "baseline", tmp_path)
    job_path = write_job_config(EVAL_TASK, "tiel-coder-35b", "opencode", "baseline", tmp_path)
    command = render_harbor_command(job_path, tmp_path / "jobs")
    assert command[0].endswith("harbor")
    assert command[1] == "run"
    assert "--config" in command and "--jobs-dir" in command and "--yes" in command
    assert "--task-path" not in command


def test_run_harbor_dry_run_does_not_execute(tmp_path, capsys):
    code = run_harbor(
        EVAL_TASK, "tiel-coder-35b", "opencode", "baseline",
        out_root=tmp_path, jobs_dir=tmp_path / "jobs", dry_run=True,
    )
    assert code == 0
    assert "harbor run --config" in capsys.readouterr().out


def test_run_harbor_requires_credentials(tmp_path, monkeypatch):
    for name in (
        "LITELLM_API_KEY", "EARTHDATA_TOKEN",
        "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit):
        run_harbor(
            EVAL_TASK, "tiel-coder-35b", "opencode", "baseline",
            out_root=tmp_path, jobs_dir=tmp_path / "jobs",
        )


def test_run_harbor_accepts_edl_token(tmp_path, monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "k")
    monkeypatch.setenv("EARTHDATA_TOKEN", "t")
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    monkeypatch.setattr(
        "earth_agent_bench.harbor.jobs.shutil.which",
        lambda name: "/usr/bin/harbor",
    )
    monkeypatch.setattr(
        "earth_agent_bench.harbor.jobs.subprocess.run",
        lambda *a, **k: type("P", (), {"returncode": 0})(),
    )
    code = run_harbor(
        EVAL_TASK, "tiel-coder-35b", "opencode", "baseline",
        out_root=tmp_path, jobs_dir=tmp_path / "jobs",
    )
    assert code == 0


def test_job_config_name_uses_timestamp(tmp_path):
    generate_package(EVAL_TASK, "baseline", tmp_path)
    name = yaml.safe_load(
        write_job_config(EVAL_TASK, "tiel-coder-35b", "opencode", "baseline", tmp_path).read_text()
    )["job_name"]
    assert re.fullmatch(
        r"eab-01_hls_open_vs_download-tiel-coder-35b-opencode-baseline-\d{8}-\d{6}",
        name,
    )


def _stub_harbor(monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "k")
    monkeypatch.setenv("EARTHDATA_TOKEN", "t")
    monkeypatch.setattr(
        "earth_agent_bench.harbor.jobs.shutil.which",
        lambda name: "/usr/bin/harbor",
    )
    monkeypatch.setattr(
        "earth_agent_bench.harbor.jobs.subprocess.run",
        lambda *a, **k: type("P", (), {"returncode": 0})(),
    )


def test_run_harbor_force_overwrites_job_dir(tmp_path, monkeypatch):
    _stub_harbor(monkeypatch)
    jobs = tmp_path / "jobs"
    job_dir = jobs / "fixed"
    job_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text("{}")
    code = run_harbor(
        EVAL_TASK, "tiel-coder-35b", "opencode", "baseline",
        out_root=tmp_path, jobs_dir=jobs, job_name="fixed", force=True,
    )
    assert code == 0
    assert not job_dir.exists()


def test_run_harbor_without_force_keeps_job_dir(tmp_path, monkeypatch):
    _stub_harbor(monkeypatch)
    jobs = tmp_path / "jobs"
    job_dir = jobs / "fixed"
    job_dir.mkdir(parents=True)
    run_harbor(
        EVAL_TASK, "tiel-coder-35b", "opencode", "baseline",
        out_root=tmp_path, jobs_dir=jobs, job_name="fixed",
    )
    assert job_dir.exists()


def test_job_name_rejects_path_separators(tmp_path, monkeypatch):
    _stub_harbor(monkeypatch)
    with pytest.raises(SystemExit):
        run_harbor(
            EVAL_TASK, "tiel-coder-35b", "opencode", "baseline",
            out_root=tmp_path, jobs_dir=tmp_path / "jobs", job_name="../evil",
        )
