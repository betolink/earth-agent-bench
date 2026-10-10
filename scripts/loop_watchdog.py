#!/usr/bin/env python3
"""Loop watchdog: end a trial early when the agent repeats the same access attempt.

The agent has no way to be interrupted from inside Harbor, so this host-side
monitor tails the current trial's agent stream and kills its container when it
detects a loop — turning a 15-minute stall into a fast, analyzable `stuck` cell.

Triggers (either):
  * the same normalized tool command appears >= WATCH_EXACT times, or
  * the same access service (opendap/harmony/s3/dmrpp/giovanni/...) appears in
    >= WATCH_SERVICE tool calls.

This is a uniform environment policy (applied to every model x condition), not a
treatment. Env: WATCH_POLL, WATCH_EXACT, WATCH_SERVICE, WATCH_WINDOW.
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

POLL = int(os.environ.get("WATCH_POLL", "8"))
EXACT = int(os.environ.get("WATCH_EXACT", "3"))
SERVICE = int(os.environ.get("WATCH_SERVICE", "5"))
WINDOW = int(os.environ.get("WATCH_WINDOW", "40"))
SERVICES = ("opendap", "harmony", "dmrpp", "giovanni", "appeears",
            "virtualize", "earthaccess.open", "earthaccess.download", "s3")


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


def _signatures(path: Path) -> list[tuple[str, str | None]]:
    sigs: list[tuple[str, str | None]] = []
    for line in _tail(path):
        if '"tool_execution_start"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        cmd = str((o.get("args") or {}).get("command") or "")
        if not cmd:
            continue
        norm = re.sub(r"\s+", " ", cmd)[:140]
        low = cmd.lower()
        svc = next((s for s in SERVICES if s in low), None)
        sigs.append((norm, svc))
    return sigs[-WINDOW:]


def _running_container() -> str | None:
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout
    for name in out.splitlines():
        if "env-main" in name or "__main" in name:
            return name
    return None


def main() -> int:
    _log(f"watchdog start poll={POLL}s exact>={EXACT} service>={SERVICE} window={WINDOW}")
    last = None
    while True:
        path = _newest_agent()
        if path is None:
            time.sleep(POLL)
            continue
        # only act on a fresh file (an active trial) and once per file
        age = time.time() - path.stat().st_mtime
        if age > 180 or path == last:
            time.sleep(POLL)
            continue
        sigs = _signatures(path)
        exact = Counter(s for s, _ in sigs)
        svc = Counter(s for _, s in sigs if s)
        worst_exact, n_exact = exact.most_common(1)[0] if exact else ("", 0)
        worst_svc, n_svc = svc.most_common(1)[0] if svc else ("", 0)
        if n_exact >= EXACT or n_svc >= SERVICE:
            name = _running_container()
            reason = (f"exact x{n_exact}: {worst_exact[:80]}" if n_exact >= EXACT
                      else f"service '{worst_svc}' x{n_svc}")
            if name:
                subprocess.run(["docker", "kill", name], capture_output=True)
                _log(f"LOOP detected ({reason}) -> killed {name} for {path.parents[2].name}")
                last = path
            else:
                _log(f"LOOP detected ({reason}) but no container found")
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
