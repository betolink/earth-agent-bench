"""Tests for the access instrumentation wrapper (signature/docstring preservation)."""

from __future__ import annotations

import inspect

from earth_agent_bench.harbor.runtime import eab_instrument as inst


def _sample(a, b=2, *, c=3):
    """Sample docstring."""
    return a + b + c


def test_wrap_preserves_signature_and_docstring():
    wrapped = inst._wrap(_sample, "mod.fn", None, None)
    assert str(inspect.signature(wrapped)) == "(a, b=2, *, c=3)"
    assert wrapped.__doc__ == "Sample docstring."
    assert wrapped.__name__ == "_sample"


def test_wrap_still_records_and_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(inst, "LOG", str(tmp_path / "events.jsonl"))
    wrapped = inst._wrap(_sample, "mod.fn", "svc", "C1")
    assert wrapped(1) == 6
    assert (tmp_path / "events.jsonl").read_text().strip()
