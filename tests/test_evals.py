from __future__ import annotations

from pathlib import Path

import pytest

from earth_agent_bench.evals import EvalGold, grade, load_suite, summarize

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE = REPO_ROOT / "experiments" / "evals" / "suite.yaml"


def _gold(task_id: str) -> EvalGold:
    return next(g for g in load_suite(SUITE) if g.task_id == task_id)


def test_suite_loads_all_ten():
    golds = load_suite(SUITE)
    assert len(golds) == 10
    ids = {g.task_id for g in golds}
    assert "01_hls_open_vs_download" in ids
    assert "10_hlss30_concept_id" in ids


def test_label_case_and_whitespace_insensitive():
    gold = _gold("01_hls_open_vs_download")
    assert grade(gold, "  Open ").correct
    assert grade(gold, "download").correct is False


def test_boolean_normalization():
    gold = _gold("08_mur_cloud_hosted")
    assert grade(gold, "yes").correct
    assert grade(gold, "TRUE").correct
    assert grade(gold, "no").correct is False


def test_string_exact_match():
    gold = _gold("10_hlss30_concept_id")
    assert grade(gold, "C2021957295-LPCLOUD").correct
    assert grade(gold, "c2021957295-lpcloud").correct is False


def test_integer_parse_and_tolerance():
    gold = EvalGold(task_id="x", answer_type="integer", answer="42", pinned=True)
    assert grade(gold, "42").correct
    assert grade(gold, "1,024").correct is False
    gold = EvalGold(task_id="y", answer_type="integer", answer="42", tolerance=2, pinned=True)
    assert grade(gold, "43").correct


def test_empty_answer_is_uncovered_not_wrong():
    gold = _gold("01_hls_open_vs_download")
    result = grade(gold, None)
    assert result.covered is False
    assert result.correct is False


def test_unpinned_gold_is_ungraded():
    gold = _gold("09_atl06_search_count")
    result = grade(gold, "12")
    assert result.covered is False
    assert result.error


def test_tool_bonus_reward():
    gold = _gold("03_emit_virtualize")
    correct_no_bonus = grade(gold, "virtualize")
    assert correct_no_bonus.reward == 1.0
    correct_with_bonus = grade(gold, "virtualize", tool_calls=15)
    assert correct_with_bonus.reward == pytest.approx(1.05)
    wrong = grade(gold, "open", tool_calls=15)
    assert wrong.reward == 0.0


def test_summary_pass1_and_coverage():
    gold = _gold("01_hls_open_vs_download")
    results = [
        grade(gold, "open"),
        grade(gold, "download"),
        grade(gold, None),  # uncovered infra failure
    ]
    summary = summarize(results)
    assert summary["attempts"] == 3
    assert summary["covered"] == 2
    assert summary["coverage"] == pytest.approx(2 / 3)
    assert summary["pass@1"] == pytest.approx(0.5)
