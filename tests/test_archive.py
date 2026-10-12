"""Tests for run archiving (eab archive)."""

from __future__ import annotations

from earth_agent_bench import archive as ar


def _job(runs, name):
    d = runs / "harbor" / name / "trial"
    d.mkdir(parents=True)
    (d / "result.json").write_text("{}")


def test_archive_moves_run(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    (runs / "harbor").mkdir(parents=True)
    (runs / "manifests").mkdir()
    (runs / "eab-full-20260101-000000.log").write_text("x")
    (runs / "manifests" / "eab-full-20260101-000000.json").write_text("{}")
    _job(runs, "eab-t-m-pi-baseline-20260101-000000")
    _job(runs, "eab-t2-m-pi-baseline-20260102-000000")
    _job(runs, "eab-old-m-pi-baseline-20251231-000000")  # before run start
    monkeypatch.setattr(ar, "RUNS", runs)
    monkeypatch.setattr(ar, "ARCHIVE", runs / "archive")

    result = ar.archive_run("run-x", "20260101-000000")
    assert len(result["moved"]) == 4  # 2 job dirs + log + manifest
    dest = runs / "archive" / "run-x"
    assert (dest / "harbor" / "eab-t-m-pi-baseline-20260101-000000").exists()
    assert (dest / "logs" / "eab-full-20260101-000000.log").exists()
    assert (dest / "manifests" / "eab-full-20260101-000000.json").exists()
    # the pre-run job stays in the active tree
    assert (runs / "harbor" / "eab-old-m-pi-baseline-20251231-000000").exists()


def test_archive_dry_run_does_not_move(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    (runs / "harbor").mkdir(parents=True)
    _job(runs, "eab-t-m-pi-baseline-20260101-000000")
    monkeypatch.setattr(ar, "RUNS", runs)
    monkeypatch.setattr(ar, "ARCHIVE", runs / "archive")
    result = ar.archive_run("run-y", "20260101-000000", dry_run=True)
    assert len(result["moved"]) == 1
    assert (runs / "harbor" / "eab-t-m-pi-baseline-20260101-000000").exists()
    assert not (runs / "archive").exists()
