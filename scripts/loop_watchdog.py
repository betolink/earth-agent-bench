#!/usr/bin/env python3
"""Loop/stall watchdog: end a trial early only when the agent is truly stuck.

The agent has no way to be interrupted from inside Harbor, so this host-side
monitor tails the current trial's agent stream and kills its container when:

  * STALL  — the agent output hasn't grown for > WATCH_STALL seconds (default 180),
             i.e. it is doing nothing; or
  * LOOP   — the *same* command (URLs/tokens/timestamps normalized away) has been
             issued >= WATCH_EXACT times (default 5).

Otherwise the trial runs to the normal 10-minute agent cap. This is a uniform
environment policy (applied to every model x condition), not a treatment.

Env: WATCH_POLL (s, 10), WATCH_STALL (s, 180), WATCH_EXACT (5), WATCH_WINDOW (40).
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
EXACT = int(os.environ.get("WATCH_EXACT", "5"))
WINDOW = int(os.environ.get("WATCH_WINDOW", "40"))


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def _newest_agent() -> Path | None:
    files = glob.glob(str(RUNS / "eab-*" / "*" / "agent" / "*.txt"))
    return Path(max(files, key=os.path.getmtime)) if files else None


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
    s = re.sub(r"[A-Za-z0-9._%+-]{16,}", "<tok>", s)   # tokens / long ids
    s = re.sub(r"\d{4}-\d{2}-\d{2}[T\d:]*", "<ts>", s)  # timestamps
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


def _running_container() -> str | None:
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout
    for name in out.splitlines():
        if "env-main" in name or "__main" in name:
            return name
    return None


def _kill(reason: str, job: str) -> None:
    name = _running_container()
    if name:
        subprocess.run(["docker", "kill", name], capture_output=True)
        _log(f"{reason} -> killed {name} for {job}")
    else:
        _log(f"{reason} -> no container found")


def main() -> int:
    _log(f"watchdog start poll={POLL}s stall>{STALL}s exact>={EXACT} window={WINDOW}")
    current: Path | None = None
    last_size = -1
    last_grow = time.time()
    while True:
        path = _newest_agent()
        if path is None:
            time.sleep(POLL)
            continue
        now = time.time()
        if path != current:                 # new trial -> reset tracking
            current, last_size, last_grow = path, path.stat().st_size, now
            time.sleep(POLL)
            continue
        size = path.stat().st_size
        if size > last_size:
            last_size, last_grow = size, now
        else:
            last_grow = last_grow or now
        job = path.parents[2].name if len(path.parents) > 2 else str(path)

        # 1) stall: no output for STALL seconds
        if now - last_grow > STALL:
            _kill(f"STALL (no output for {int(now - last_grow)}s)", job)
            current = None
            time.sleep(POLL)
            continue

        # 2) loop: the same normalized command repeated >= EXACT times
        cmds = _commands(path)
        worst, n = (Counter(cmds).most_common(1)[0] if cmds else ("", 0))
        if n >= EXACT:
            _kill(f"LOOP (same command x{n}: {worst[:70]})", job)
            current = None
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
