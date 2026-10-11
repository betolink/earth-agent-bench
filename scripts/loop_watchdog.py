#!/usr/bin/env python3
"""Loop/stall watchdog: end a trial early only when *that* trial is stuck.

Harbor can't interrupt an agent mid-run, so this host-side monitor watches the
agent output of the **currently running container** and kills it when:

  * STALL  — its output hasn't grown for > WATCH_STALL seconds (default 180), or
  * LOOP   — the same command (URLs/tokens/timestamps normalized) has been issued
             >= WATCH_EXACT times (default 6).

Crucially it maps container -> its own trial dir, so during a new trial's *setup*
phase (no agent output yet) it does nothing — a previous trial's looping file can
never get a fresh trial killed. Otherwise the trial runs to the 600s agent cap.

Env: WATCH_POLL (s, 10), WATCH_STALL (s, 180), WATCH_EXACT (6), WATCH_WINDOW (40).
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path

EAB = Path(__file__).resolve().parents[1]
RUNS = EAB / "runs" / "harbor"
LOG = EAB / "runs" / "loop-watchdog.log"

POLL = int(os.environ.get("WATCH_POLL", "10"))
STALL = int(os.environ.get("WATCH_STALL", "180"))
EXACT = int(os.environ.get("WATCH_EXACT", "6"))
WINDOW = int(os.environ.get("WATCH_WINDOW", "40"))
_TRIAL = re.compile(r"^(.*?)__(?:env-main|main)")


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def _running_container() -> str | None:
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout
    for name in out.splitlines():
        if "__env-main" in name or "__main" in name:
            return name
    return None


def _agent_for_container(name: str) -> Path | None:
    m = _TRIAL.match(name)
    if not m:
        return None
    key = m.group(1)                      # "<task>__<hash>"
    for f in glob.glob(str(RUNS / "eab-*" / key / "agent" / "*.txt")):
        return Path(f)
    return None


def _tail(path: Path, max_bytes: int = 200_000) -> list[str]:
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > max_bytes:
            fh.seek(size - max_bytes)
            data = fh.read().decode("utf-8", "replace")
            data = data.split("\n", 1)[1] if "\n" in data else data
        else:
            data = fh.read().decode("utf-8", "replace")
    return data.splitlines()


def _norm(cmd: str) -> str:
    s = re.sub(r"https?://\S+", "<url>", cmd)
    s = re.sub(r"[A-Za-z0-9._%+-]{16,}", "<tok>", s)
    s = re.sub(r"\d{4}-\d{2}-\d{2}[T\d:]*", "<ts>", s)
    return re.sub(r"\s+", " ", s).strip()[:140]


def _commands(path: Path) -> list[str]:
    cmds: list[str] = []
    for line in _tail(path):
        if '"tool_execution_start"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        cmd = str((o.get("args") or {}).get("command") or "")
        if cmd:
            cmds.append(_norm(cmd))
    return cmds[-WINDOW:]


def main() -> int:
    _log(f"watchdog start poll={POLL}s stall>{STALL}s exact>={EXACT} window={WINDOW}")
    current: Path | None = None
    last_size = -1
    last_grow = time.time()
    while True:
        name = _running_container()
        if name is None:                  # no trial running
            current = None
            time.sleep(POLL)
            continue
        path = _agent_for_container(name)
        if path is None:                  # setup phase, no agent output yet
            current = None
            time.sleep(POLL)
            continue
        now = time.time()
        if path != current:               # new trial's file -> reset tracking
            current, last_size, last_grow = path, path.stat().st_size, now
            time.sleep(POLL)
            continue
        size = path.stat().st_size
        if size > last_size:
            last_size, last_grow = size, now

        # 1) stall: no output for STALL seconds
        if now - last_grow > STALL:
            subprocess.run(["docker", "kill", name], capture_output=True)
            _log(f"STALL (no output for {int(now - last_grow)}s) -> killed {name}")
            current = None
            time.sleep(POLL)
            continue

        # 2) loop: the same normalized command repeated >= EXACT times
        cmds = _commands(path)
        worst, n = (Counter(cmds).most_common(1)[0] if cmds else ("", 0))
        if n >= EXACT:
            subprocess.run(["docker", "kill", name], capture_output=True)
            _log(f"LOOP (same command x{n}: {worst[:70]}) -> killed {name}")
            current = None
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
