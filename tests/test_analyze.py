"""Tests for the batched, resumable, verifiable postmortem analysis."""

from __future__ import annotations

from earth_agent_bench import analyze as A


def _cell(task: str, model: str = "m", harness: str = "pi", condition: str = "baseline",
          trial: str = "t1", reward: float = 0.5, status: str = "partial") -> dict:
    return {
        "task": task, "model": model, "harness": harness, "condition": condition,
        "trial": trial, "reward": reward, "status": status, "exception": "",
        "components": {"access_pattern": 0.4, "service_discovery": 0.1,
                       "representation": 0.2, "efficiency": 0.1, "validation": 0.0},
        "details_path": None, "trajectory": None, "run_name": "run-x",
    }


def _cells_two_rows() -> list[dict]:
    return [
        _cell("t1", condition="baseline", trial="a"),
        _cell("t2", condition="baseline", trial="b"),
        _cell("t1", condition="skills", trial="c"),
        _cell("t2", condition="skills", trial="d"),
    ]


def _stub(monkeypatch, cells, calls):
    monkeypatch.setattr(A, "collect_cells", lambda name, harness=None: cells)

    def fake_judge(model, payload, **kw):
        calls.append(payload)
        return f"SUMMARY-{len(calls)}"

    monkeypatch.setattr(A, "call_judge", fake_judge)


def test_group_rows_and_signature():
    cells = _cells_two_rows()
    rows = A._group_rows(cells)
    assert [k for k, _ in rows] == [("m", "pi", "baseline"), ("m", "pi", "skills")]
    batches = [[r] for r in rows]
    sig = A._signature(batches, "judge", 80, 240, 0, "low")
    again = [[r] for r in A._group_rows(_cells_two_rows())]
    assert sig == A._signature(again, "judge", 80, 240, 0, "low")
    assert sig != A._signature(batches, "judge", 40, 240, 0, "low")


def test_build_evidence_is_compact_and_has_facts():
    ev = A.build_evidence(_cells_two_rows())
    assert "Results table" in ev and "reward=0.5" in ev
    assert "observed=" in ev and "exec=" in ev
    assert len(ev) < 4000


def test_analyze_resumes_from_last_batch(tmp_path, monkeypatch):
    cells = _cells_two_rows()
    calls: list[str] = []
    _stub(monkeypatch, cells, calls)

    res = A.analyze("run-x", "judge", output=tmp_path, batch=1, progress=False)
    assert len(calls) == 2
    assert (tmp_path / "analysis-run-x.md").read_text().strip() == "SUMMARY-2"
    assert res["resumed_from"] == 0

    (tmp_path / "analysis-run-x" / "batch-01.summary.md").unlink()
    calls.clear()
    res2 = A.analyze("run-x", "judge", output=tmp_path, batch=1, progress=False)
    assert len(calls) == 1
    assert res2["resumed_from"] == 1
    assert (tmp_path / "analysis-run-x.md").read_text().strip() == "SUMMARY-1"

    calls.clear()
    A.analyze("run-x", "judge", output=tmp_path, batch=1, progress=False, resume=False)
    assert len(calls) == 2

    calls.clear()
    res4 = A.analyze("run-x", "judge", output=tmp_path, batch=1, max_steps=40, progress=False)
    assert res4["resumed_from"] == 0 and len(calls) == 2


def test_verify_pass_writes_corrected(tmp_path, monkeypatch):
    cells = _cells_two_rows()
    calls: list[str] = []
    _stub(monkeypatch, cells, calls)

    res = A.analyze("run-x", "judge", output=tmp_path, batch=1, progress=False,
                    verify_pass=True)
    vpath = tmp_path / "analysis-run-x-verified.md"
    assert vpath.exists()
    assert res["verified"] == str(vpath)
    verify_payload = calls[-1]
    assert "FACTS (authoritative" in verify_payload
    assert "DRAFT postmortem" in verify_payload
    assert "SUMMARY-2" in verify_payload
