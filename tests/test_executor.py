from __future__ import annotations

from pathlib import Path

from earth_agent_bench.harbor.runtime import profiler
from earth_agent_bench.harbor.runtime.executor import run_script, status_report


def _script(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "deliverable.py"
    p.write_text(body)
    return p


def test_ok(tmp_path: Path) -> None:
    res = run_script(_script(tmp_path, "print('hi')\n"), workdir=tmp_path)
    assert res.status == "ok" and res.returncode == 0
    assert "hi" in res.stdout


def test_error(tmp_path: Path) -> None:
    res = run_script(_script(tmp_path, "raise ValueError('boom')\n"), workdir=tmp_path)
    assert res.status == "error" and res.returncode != 0
    assert "ValueError" in res.stderr


def test_timeout(tmp_path: Path) -> None:
    res = run_script(_script(tmp_path, "import time; time.sleep(30)\n"),
                     workdir=tmp_path, timeout_s=0.5)
    assert res.status == "timeout" and res.timed_out


def test_oom(tmp_path: Path) -> None:
    res = run_script(_script(tmp_path, "x = bytearray(600 * 1024 * 1024)\n"),
                     workdir=tmp_path, mem_mb=128)
    assert res.status == "oom"


def test_status_report_shape(tmp_path: Path) -> None:
    res = run_script(_script(tmp_path, "pass\n"), workdir=tmp_path)
    report = status_report(res)
    assert set(report) == {"exec_status", "returncode", "wall_s", "peak_rss_mb", "profile"}


def test_profile_command_shapes() -> None:
    base = ["/usr/bin/python", "s.py", "--arg"]
    scal = profiler.build_profile_command("scalene", base, Path("out"))
    assert scal[1:4] == ["-m", "scalene", "run"] and scal[-2:] == ["s.py", "--arg"]
    assert scal[scal.index("--outfile") + 1].endswith(".json")
    mem = profiler.build_profile_command("memray", base, Path("out"))
    assert mem[1:4] == ["-m", "memray", "run"]
    assert mem[mem.index("-o") + 1].endswith(".bin")


def test_available_keys() -> None:
    assert set(profiler.available()) == set(profiler.KINDS)
