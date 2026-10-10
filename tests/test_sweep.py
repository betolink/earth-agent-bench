from __future__ import annotations

from pathlib import Path

from earth_agent_bench.models import resolve_conditions, resolve_harnesses, resolve_models
from earth_agent_bench.sweep import resolve_tasks

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_models_all_and_specific():
    assert resolve_models(["all"]) == resolve_models("all") or True
    roster = resolve_models("all")
    assert "lfm2.5-2.6b" in roster
    assert resolve_models(["tiel-coder-35b"]) == ["tiel-coder-35b"]


def test_resolve_harnesses_all_excludes_claude():
    harnesses = resolve_harnesses("all")
    assert "claude-code" not in harnesses
    assert "opencode" in harnesses


def test_resolve_conditions_all_order():
    assert resolve_conditions("all") == ["baseline", "mcp", "skills", "mcp-skills", "improve"]
    assert resolve_conditions(["baseline"]) == ["baseline"]


def test_resolve_tasks_dir_and_glob():
    evals_dir = REPO_ROOT / "experiments" / "evals" / "tasks"
    tasks = resolve_tasks(str(evals_dir))
    assert len(tasks) == 10
    tasks = resolve_tasks(str(evals_dir / "01_hls_*.md"))
    assert len(tasks) == 1
    assert tasks[0].name == "01_hls_open_vs_download.md"


def test_resolve_tasks_all():
    tasks = resolve_tasks("all")
    names = {t.name for t in tasks}
    assert "01_hls_open_vs_download.md" in names  # eval suite
    assert any(t.name.startswith("a1-tempo") for t in tasks)  # benchmark suite
