"""Deterministic correctness eval for the single-clean-value task suite.

The judge here is intentionally *not* an LLM: each task has a gold answer and a
typed comparison (label / boolean / integer / string). An LLM judge would inject
a second uncontrolled model into the measurement and drift between runs.

The FineEnvs tool-efficiency bonus is applied only when a tool-call count is
instrumented:

    bonus  = 0.1 * 15 / (15 + tool_calls)   if tool_calls and tool_calls > 0 else 0
    reward = correct * (1 + bonus)

An empty/missing answer is treated as *uncovered* (an infrastructure failure),
not as a wrong answer — reported separately, never scored as zero.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel

AnswerType = Literal["label", "boolean", "integer", "string"]


class EvalGold(BaseModel):
    task_id: str
    answer_type: AnswerType
    answer: Optional[str | bool | int | float] = None  # native type; parsed per answer_type
    tolerance: float = 0.0        # for integer answers
    pinned: bool = True
    note: str = ""


class EvalResult(BaseModel):
    task_id: str
    correct: bool
    covered: bool
    tool_calls: Optional[int] = None
    reward: float = 0.0
    produced: Optional[str] = None
    error: Optional[str] = None


TRUE = {"yes", "true", "1", "y", "t"}
FALSE = {"no", "false", "0", "n", "f"}
NOT_APPLICABLE = "not applicable"


def _strip(value: str) -> str:
    return value.strip()


def _label(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _boolean(value: str) -> Optional[bool]:
    token = value.strip().lower()
    if token in TRUE:
        return True
    if token in FALSE:
        return False
    return None


def _integer(value: str) -> Optional[int]:
    token = value.strip().replace(",", "").replace("_", "")
    try:
        return int(float(token)) if "." in token else int(token)
    except (ValueError, TypeError):
        return None


def _string(value: str) -> str:
    return value.strip()


def _parse(gold: EvalGold, produced: str) -> Optional[object]:
    """Parse `produced` into gold's domain, or None if unparseable."""
    if gold.answer_type == "label":
        return _label(produced)
    if gold.answer_type == "boolean":
        return _boolean(produced)
    if gold.answer_type == "integer":
        return _integer(produced)
    if gold.answer_type == "string":
        return _string(produced)
    return None


def _gold_value(gold: EvalGold) -> object:
    if gold.answer_type == "boolean":
        return str(gold.answer).strip().lower() in TRUE
    if gold.answer_type == "integer":
        return int(gold.answer)
    if gold.answer_type == "label":
        return _label(str(gold.answer))
    return str(gold.answer).strip()


def _match(gold: EvalGold, parsed: object, gold_value: object) -> bool:
    if gold.answer_type == "integer":
        return abs(parsed - gold_value) <= gold.tolerance
    return parsed == gold_value


def grade(gold: EvalGold, produced: Optional[str], tool_calls: Optional[int] = None) -> EvalResult:
    """Grade a single produced answer against its gold."""
    if gold.answer is None and not gold.pinned:
        return EvalResult(
            task_id=gold.task_id,
            correct=False,
            covered=False,
            tool_calls=tool_calls,
            error="gold answer is unpinned; pin it at build time before scoring",
        )

    if produced is None or produced.strip() == "":
        return EvalResult(task_id=gold.task_id, correct=False, covered=False, tool_calls=tool_calls)

    parsed = _parse(gold, produced)
    if parsed is None:
        return EvalResult(task_id=gold.task_id, correct=False, covered=True,
                          tool_calls=tool_calls, produced=produced)

    correct = _match(gold, parsed, _gold_value(gold))
    bonus = 0.1 * 15 / (15 + tool_calls) if tool_calls and tool_calls > 0 else 0.0
    reward = (1.0 + bonus) if correct else 0.0
    return EvalResult(task_id=gold.task_id, correct=correct, covered=True,
                      tool_calls=tool_calls, reward=reward, produced=produced)


def load_suite(path: str | Path) -> list[EvalGold]:
    """Load the consolidated eval suite manifest (experiments/evals/suite.yaml)."""
    data = yaml.safe_load(Path(path).read_text())
    return [EvalGold.model_validate({**t, "pinned": t.get("pinned", True)}) for t in data["tasks"]]


def summarize(results: list[EvalResult]) -> dict:
    """pass@1 + coverage + tool-call aggregate over a list of graded results."""
    covered = [r for r in results if r.covered]
    total = len(results)
    correct = sum(1 for r in covered if r.correct)
    tooled = [r for r in covered if r.tool_calls is not None]
    return {
        "attempts": total,
        "covered": len(covered),
        "coverage": (len(covered) / total) if total else 0.0,
        "pass@1": (correct / len(covered)) if covered else 0.0,
        "correct": correct,
        "mean_reward": sum(r.reward for r in covered) / len(covered) if covered else 0.0,
        "mean_tool_calls": sum(r.tool_calls for r in tooled) / len(tooled) if tooled else None,
    }
