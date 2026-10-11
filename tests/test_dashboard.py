"""Tests for the dashboard live-view condenser (all harness schemas)."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("textual")
from earth_agent_bench.dashboard import _condense  # noqa: E402


def test_pi_schema():
    assert _condense('{"type":"tool_execution_start","toolName":"bash",'
                     '"args":{"command":"ls -la"}}') == "▶ bash: ls -la"
    assert _condense('{"type":"tool_execution_end","toolName":"bash"}') == "✓ bash"


def test_opencode_schema():
    line = json.dumps({"type": "tool_use", "part": {
        "tool": "bash", "state": {"status": "completed", "input": {"command": "grep foo"}}}})
    assert _condense(line) == "✓ bash: grep foo"
    r = json.dumps({"type": "reasoning", "part": {"text": "thinking hard"}})
    assert _condense(r) == "🧠 thinking hard"


def test_codex_schema():
    assert _condense(json.dumps(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "fetch it"}})
    ) == "✎ fetch it"
    assert _condense(json.dumps(
        {"type": "item.started", "item": {"type": "command_execution", "command": "python x.py"}})
    ) == "▶ $ python x.py"
    assert _condense(json.dumps(
        {"type": "item.completed",
         "item": {"type": "command_execution", "command": "python x.py"}})
    ) == "✓ $ python x.py"


def test_claude_schema():
    assert _condense(json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Using Harmony"}]}})
    ) == "✎ Using Harmony"
    assert _condense(json.dumps(
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "curl https://cmr"}}]}})
    ) == "▶ Bash: curl https://cmr"


def test_generic_and_plain():
    assert _condense(json.dumps(
        {"type": "whatever", "tool": "search", "arguments": {"query": "modis"}})
    ) == "▶ search: modis"
    assert _condense(json.dumps({"type": "delta", "text": "streaming answer"})) == "✎ streaming answer"
    assert _condense("codex: starting session") == "codex: starting session"


def test_skips_noise():
    assert _condense('{"type":"step_start","part":{"type":"step-start"}}') is None
    assert _condense("") is None
