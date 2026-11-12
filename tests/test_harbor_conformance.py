"""Harbor interoperability conformance tests.

These assert the generated packages satisfy Harbor's task schema and the
dataset/verifier conventions we publish under, so a change cannot silently make
the suite unrunnable or unscorable outside this repo.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from earth_agent_bench.harbor import generate_package, resolve_tasks
from earth_agent_bench.harbor.config import (
    RUNTIME_DIR,
    artifact_sources,
    resources,
    verifier_environment_mode,
)
from earth_agent_bench.harbor.dataset import write_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_TASK = "benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml"
EVAL_TASK = "experiments/evals/tasks/01_hls_open_vs_download.md"


def _task_config(package: Path):
    from harbor.models.task.config import TaskConfig

    return TaskConfig.model_validate_toml((package / "task.toml").read_text())


def _run_verifier(package: Path, workspace: Path, logs: Path):
    return subprocess.run(
        [sys.executable, str(package / "tests" / "verify.py"),
         "--workspace", str(workspace), "--logs", str(logs)],
        capture_output=True, text=True,
    )


def test_every_generated_package_matches_harbor_schema(tmp_path):
    for task_path in resolve_tasks("all"):
        package = generate_package(task_path, "baseline", tmp_path)
        config = _task_config(package)
        assert config.task is not None
        assert config.task.name == f"earth-agent-bench/{package.name}"


def test_benchmark_package_carries_interop_metadata(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    config = _task_config(package)
    metadata = config.metadata
    assert metadata["suite"] == "benchmark"
    assert metadata["sphere"] == "atmosphere"
    assert metadata["kind"] == "aggregate"
    assert metadata["infeasible"] is False
    assert metadata["access_pattern_gold"] == ["C1"]
    assert metadata["collections"] == ["TEMPO_NO2_L3"]
    assert config.task.keywords
    assert config.source == "benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml"


def test_eval_package_carries_interop_metadata(tmp_path):
    package = generate_package(EVAL_TASK, "baseline", tmp_path)
    config = _task_config(package)
    assert config.metadata["suite"] == "correctness"
    assert config.metadata["answer_type"] == "label"
    assert config.source == "experiments/evals/tasks/01_hls_open_vs_download.md"


def test_verifier_is_isolated_and_artifacts_are_declared(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    config = _task_config(package)
    assert config.verifier.environment_mode.value == verifier_environment_mode() == "separate"
    assert [artifact.source for artifact in config.artifacts] == artifact_sources()

    # Tests and solution must not be baked into the agent image.
    dockerfile = (package / "environment" / "Dockerfile").read_text()
    assert "COPY tests" not in dockerfile
    assert "COPY solution" not in dockerfile


def test_resource_caps_and_pinned_dependencies(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    config = _task_config(package)
    expected = resources()
    assert config.environment.cpus == expected["cpus"]
    assert config.environment.memory_mb == expected["memory_mb"]

    requirements = (package / "environment" / "agent-requirements.txt").read_text()
    assert requirements == (RUNTIME_DIR / "agent-requirements.txt").read_text()
    unpinned = [
        line for line in requirements.splitlines()
        if line.strip() and not line.startswith("#")
        and "==" not in line and "@ git+" not in line
    ]
    assert not unpinned, f"unpinned requirements: {unpinned}"
    assert "@79782b6798bbcc325c18d1b2f3dfab2dfb7b4977" in requirements


def test_pass_requires_execution_and_sanctioned_code(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    ws = tmp_path / "ws"
    (ws / "output").mkdir(parents=True)
    (ws / "access.py").write_text(
        "import requests  # raw CMR, unsanctioned\n"
        "requests.get('https://cmr.earthdata.nasa.gov/search/collections.json')\n"
    )
    logs = tmp_path / "logs"
    run = _run_verifier(package, ws, logs)
    assert run.returncode == 0, run.stderr
    details = json.loads((logs / "details.json").read_text())
    assert details["code_check"]["sanctioned"] is False
    assert details["pass"] == 0.0


def test_pass_credits_real_instrumented_events(tmp_path):
    package = generate_package(BENCH_TASK, "baseline", tmp_path)
    ws = tmp_path / "ws"
    (ws / "output").mkdir(parents=True)
    (ws / "agent").mkdir()
    # Sanctioned deliverable that exits cleanly (no network in the test env).
    (ws / "access.py").write_text(
        "# earthaccess-based route, exercised at demo scope\n"
        "print('done')\n"
    )
    events = [
        {"function": "earthaccess.search_data", "short_name": "TEMPO_NO2_L3",
         "service": None, "pattern": None, "n_result": 30, "error": None,
         "duration_s": 1.0},
        {"function": "harmony.Submit", "service": "harmony",
         "pattern": "S1", "n_result": 1, "error": None, "duration_s": 5.0},
    ]
    (ws / "agent" / "access_events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n"
    )
    logs = tmp_path / "logs"
    run = _run_verifier(package, ws, logs)
    assert run.returncode == 0, run.stderr
    rewards = json.loads((logs / "reward.json").read_text())
    details = json.loads((logs / "details.json").read_text())
    assert details["events_source"].startswith("agent-run")
    assert rewards["access_pattern"] == 0.7
    assert rewards["pass"] == 1.0
    assert (logs / "reward.txt").read_text().strip() == "1.0"


def test_metric_selects_pass_headline(tmp_path):
    path = REPO_ROOT / "harbor" / "metric.py"
    spec = importlib.util.spec_from_file_location("eab_metric", path)
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)

    input_path = tmp_path / "rewards.jsonl"
    input_path.write_text(
        json.dumps({"pass": 1.0, "score": 0.9, "access_pattern": 1.0}) + "\n"
        + json.dumps({"pass": 0.0, "score": 0.8, "access_pattern": 1.0}) + "\n"
    )
    output_path = tmp_path / "out.json"
    metric.main(input_path, output_path)
    assert json.loads(output_path.read_text()) == {"mean": 0.5}


def test_dataset_manifest_is_digest_pinned(tmp_path):
    from harbor.models.dataset.manifest import DatasetManifest

    tasks = list(resolve_tasks("cryo-1,atmo-2"))
    dataset = write_dataset(tasks, out_root=tmp_path / "generated",
                            dataset_path=tmp_path / "dataset.toml")
    manifest = DatasetManifest.from_toml_file(dataset)
    assert manifest.dataset.name == "eab/earth-agent-bench"
    assert len(manifest.tasks) == 2
    assert all(task.digest.startswith("sha256:") for task in manifest.tasks)
    assert (tmp_path / "metric.py").exists()
