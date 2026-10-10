"""Harness-side code executor: run an agent's deliverable under a hard budget.

Gives every run an explicit outcome instead of an ambiguous 0/1:

    ok        — exited 0 within the wall/CPU/memory budget
    error     — exited non-zero (the deliverable raised)
    timeout   — exceeded the wall-clock budget (killed)
    oom       — exceeded the memory budget (RLIMIT_AS MemoryError / SIGKILL 137)

Optionally profiles the run (scalene/memray) to produce line-level artifacts.
Correctness is graded by the caller (task tests / typed-equality); this module
only owns *execution* and resource attribution.
"""

from __future__ import annotations

import json
import os
import resource
import signal
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .profiler import ProfilerError, build_profile_command, profile_available

TIMEOUT_EXIT = 124


@dataclass
class ExecResult:
    status: str = "ok"            # ok | error | timeout | oom
    returncode: int | None = None
    wall_s: float = 0.0
    cpu_s: float = 0.0
    peak_rss_mb: float = 0.0
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    command: list[str] = field(default_factory=list)
    profile: dict | None = None   # {"kind": str, "path": str} when profiling

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _limits(mem_mb: int | None, cpu_s: int | None):
    def apply() -> None:  # runs in the child, before exec
        os.setsid()
        if mem_mb:
            limit = mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        if cpu_s:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    return apply


def _classify(returncode: int | None, timed_out: bool, stderr: str) -> str:
    if timed_out:
        return "timeout"
    if returncode in (-signal.SIGKILL, -9, 137) or "MemoryError" in stderr \
            or "Cannot allocate memory" in stderr:
        return "oom"
    if returncode != 0:
        return "error"
    return "ok"


def run_script(
    script: str | Path,
    *,
    args: list[str] | None = None,
    workdir: str | Path | None = None,
    timeout_s: float = 60.0,
    mem_mb: int | None = None,
    cpu_s: int | None = None,
    env: dict | None = None,
    python: str | None = None,
    profile: str | None = None,
    profile_out: str | Path | None = None,
) -> ExecResult:
    """Execute a Python script under the budget; classify and (optionally) profile."""
    script = Path(script).resolve()
    py = python or sys.executable
    base = [py, str(script), *(args or [])]

    profile_meta: dict | None = None
    command = base
    if profile and profile != "none":
        if not profile_available(profile):
            raise ProfilerError(f"profiler '{profile}' is not installed in this environment")
        out = Path(profile_out or (Path(workdir or ".") / f"profile.{profile}"))
        command = build_profile_command(profile, base, out)
        profile_meta = {"kind": profile, "path": str(out)}

    child_env = dict(os.environ)
    if env:
        child_env.update(env)

    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    timed_out = False
    import time
    t0 = time.monotonic()
    proc = subprocess.Popen(
        command, cwd=str(workdir) if workdir else None, env=child_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        preexec_fn=_limits(mem_mb, cpu_s), start_new_session=False,
    )
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
    wall = time.monotonic() - t0

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    peak_kb = max(usage.ru_maxrss, before)
    return ExecResult(
        status=_classify(proc.returncode, timed_out, err or ""),
        returncode=proc.returncode,
        wall_s=round(wall, 3),
        cpu_s=round(usage.ru_utime + usage.ru_stime, 3),
        peak_rss_mb=round(peak_kb / 1024, 1),
        timed_out=timed_out,
        stdout=out or "",
        stderr=err or "",
        command=command,
        profile=profile_meta,
    )


def status_report(result: ExecResult) -> dict:
    """Compact correct/incorrect/timeout/oom view for the caller to grade against."""
    return {
        "exec_status": result.status,     # ok|error|timeout|oom
        "returncode": result.returncode,
        "wall_s": result.wall_s,
        "peak_rss_mb": result.peak_rss_mb,
        "profile": result.profile,
    }
