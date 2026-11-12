"""Tests for the master-config matrix (models × harnesses × conditions × tasks)."""

from __future__ import annotations

from earth_agent_bench.harbor.matrix import (
    resolve_cells,
    resolve_selection,
    resolve_task_paths,
    run_matrix,
)


def test_resolve_cells_is_cartesian():
    cells, skipped = resolve_cells("lfm2.5-2.6b,ornith-1.5-9b", "pi,opencode",
                                   "baseline,skills")
    assert not skipped
    assert len(cells) == 2 * 2 * 2
    assert {"model": "ornith-1.5-9b", "harness": "opencode", "condition": "skills"} in cells


def test_restricted_harness_crossing_is_applied():
    cells, skipped = resolve_cells("lfm2.5-2.6b,claude-sonnet-5-5", "claude-code", "baseline")
    assert skipped == [("lfm2.5-2.6b", "claude-code")]
    assert [cell["model"] for cell in cells] == ["claude-sonnet-5-5"]


def test_selection_defaults_to_run_config():
    selection = resolve_selection()
    cfg = selection["config"]
    assert selection["models"] == ",".join(cfg["models"])
    assert selection["harnesses"] == ",".join(cfg["harnesses"])
    assert selection["conditions"] == ",".join(cfg["conditions"])
    # run.yaml `tasks: all` means the grounded suite, not the eval suite.
    assert len(resolve_task_paths(None, cfg)) == 18


def test_explicit_selection_overrides_run_config():
    selection = resolve_selection(models="lfm2.5-2.6b", harnesses="pi", conditions="baseline")
    assert selection["models"] == "lfm2.5-2.6b"
    assert selection["harnesses"] == "pi"
    assert selection["conditions"] == "baseline"


def test_dry_run_expands_matrix_and_nests_packages_by_condition(tmp_path, capsys):
    out = tmp_path / "generated"
    jobs = tmp_path / "jobs"
    code = run_matrix(
        tasks="cryo-1",
        models="lfm2.5-2.6b",
        harnesses="pi",
        conditions="baseline,skills",
        out=out,
        jobs_dir=jobs,
        dry_run=True,
    )
    captured = capsys.readouterr().out
    assert code == 0
    assert "[matrix] 1 task(s) x 2 cell(s) = 2 job(s)" in captured
    assert (out / "baseline" / "c1-itslive-jakobshavn-2015-2024").is_dir()
    assert (out / "skills" / "c1-itslive-jakobshavn-2015-2024").is_dir()
    assert not (jobs / "anything").exists()


def test_single_condition_keeps_flat_package_layout(tmp_path):
    out = tmp_path / "generated"
    run_matrix(tasks="cryo-1", models="lfm2.5-2.6b", harnesses="pi",
               conditions="baseline", out=out, jobs_dir=tmp_path / "jobs", dry_run=True)
    assert (out / "c1-itslive-jakobshavn-2015-2024" / "task.toml").is_file()


def test_matrix_rejects_empty_selection(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        run_matrix(tasks="cryo-1", models="lfm2.5-2.6b", harnesses="claude-code",
                   conditions="baseline", out=tmp_path / "g",
                   jobs_dir=tmp_path / "j", dry_run=True)


def test_archive_uses_newest_harbor_job(tmp_path, monkeypatch):
    from earth_agent_bench import archive

    harbor = tmp_path / "harbor"
    (harbor / "eab-a1-x-pi-baseline-20260101-000000").mkdir(parents=True)
    (harbor / "eab-a2-x-pi-baseline-20260202-000000").mkdir(parents=True)
    monkeypatch.setattr(archive, "RUNS", tmp_path)
    assert archive.latest_stamp() == "20260202-000000"
