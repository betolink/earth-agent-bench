import json
import subprocess
import sys
from pathlib import Path

import pytest

from earth_agent_bench.harbor_adapter import (
    generate_package,
    render_harbor_command,
    resolve_task,
    resolve_tasks,
)

TASKS = Path("benchmark/tasks")


def test_alias_resolution():
    assert resolve_task("cryo-1").stem == "c1-itslive-jakobshavn-2015-2024"
    assert resolve_task("atmo-2").stem == "a2-emit-methane-permian-2024"
    assert resolve_task("solid-3").stem == "s3-central-valley-subsidence-2015-2024"
    assert resolve_task("l1").stem.startswith("l1-")
    full = resolve_task("atmosphere/a1-tempo-no2-florida-2024")
    assert full.parent.name == "atmosphere"


def test_alias_lists():
    assert len(resolve_tasks("pilot")) == 3
    assert len(resolve_tasks("all")) == 18
    assert len(resolve_tasks("cryo-1,atmo-2")) == 2


def test_alias_errors():
    with pytest.raises(SystemExit):
        resolve_task("not-a-sphere-9")
    with pytest.raises(SystemExit):
        resolve_task("")


def test_generate_package_baseline(tmp_path):
    task = resolve_task("cryo-1")
    package = generate_package(task, "baseline", tmp_path)
    assert (package / "instruction.md").exists()
    assert (package / "environment" / "Dockerfile").exists()
    assert (package / "solution" / "solve.sh").exists()
    assert (package / "tests" / "task.yaml").exists()
    assert (package / "tests" / "verify.py").exists()
    assert (package / "tests" / "earth_agent_bench" / "scoring" / "aggregate.py").exists()
    requirements = (package / "agent-requirements.txt").read_text()
    assert "earthaccess" in requirements
    assert not (package / "skills").exists()
    text = (package / "instruction.md").read_text()
    assert "primary_patterns" not in text
    dockerfile = (package / "environment" / "Dockerfile").read_text()
    assert "COPY skills" not in dockerfile


def test_generate_package_mcp_skills(tmp_path):
    task = resolve_task("atmo-1")
    package = generate_package(task, "mcp-skills", tmp_path)
    assert (package / "skills" / "data-access-patterns" / "SKILL.md").exists()
    opencode = json.loads((package / "opencode.jsonc").read_text())
    assert opencode["mcp"]["cmr"]["url"] == "https://cmr.earthdata.nasa.gov/mcp/v1"
    dockerfile = (package / "environment" / "Dockerfile").read_text()
    assert "COPY skills /app/skills" in dockerfile
    assert ".mcp.json" in dockerfile


def test_verifier_scores_from_access_summary(tmp_path):
    package = generate_package(resolve_task("atmo-1"), "baseline", tmp_path)
    workspace = tmp_path / "workspace"
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "artifact.nc").write_bytes(b"placeholder")
    (workspace / "output" / "access_summary.json").write_text(json.dumps({
        "collections": ["TEMPO_NO2_L3"],
        "access_services_used": ["virtualization", "harmony"],
        "bytes_read_estimate": 45_000_000,
        "pattern_notes": "virtualized the archive, lazy monthly means",
    }))

    result = subprocess.run(
        [sys.executable, str(package / "tests" / "verify.py"),
         "--workspace", str(workspace), "--task", str(package / "tests" / "task.yaml")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    evaluation = json.loads((package / "tests" / "evaluation.json").read_text())
    assert evaluation["access_pattern"] == 1.0
    assert evaluation["collection_selection"] == 1.0
    assert evaluation["reward"] > 0.8


def test_render_harbor_command(tmp_path):
    task = resolve_task("cryo-1")
    generate_package(task, "baseline", tmp_path)
    command = render_harbor_command(task, "tiel-coder-35b", "opencode",
                                    "baseline", tmp_path)
    assert command[0] == "harbor"
    assert "opencode" in command
    assert "tiel-coder-35b" in command
    assert str(tmp_path / task.stem) in " ".join(command)
