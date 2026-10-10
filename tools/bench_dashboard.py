#!/usr/bin/env python3
"""Live TUI dashboard for the betolink local-model benchmark runs (Textual).

Layout:
  left  · CODING SUITE (model x harness mean reward)
        · EAB — combos x 18 tasks (each row = one combo, one cell per task)
  right · CODING — per-task grid (latest)
        · EAB — recent log

Everything is logged to dashboard.log next to this file (lean: one line per
change, plus errors). Every refresh step is wrapped so a transient error is
surfaced in the status bar instead of crashing the app.

Keys: r refresh now · +/- interval ±30s · s toggle auto · q quit
Run:  python3 bench-dashboard/dashboard.py
Env:  DASH_INTERVAL (seconds, default 300) · DASH_LOG (log path)
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static

# ----------------------------------------------------------------- logging
LOG_PATH = Path(os.environ.get("DASH_LOG", Path(__file__).resolve().with_name("dashboard.log")))
log = logging.getLogger("dashboard")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    _h = RotatingFileHandler(str(LOG_PATH), maxBytes=256 * 1024, backupCount=2)
    _h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
    log.addHandler(_h)


def _excepthook(exc_type, exc, tb):
    log.error("UNCAUGHT: %s", "".join(traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = _excepthook

# ----------------------------------------------------------------- constants
ROOT = Path("/home/lopez/github/betolink")
MB = ROOT / "mini-benchmarks"
EAB = ROOT / "earth-agent-bench"

MODELS = ["tiel-coder-35b", "qwen3.8-27b-gsq", "ornith-1.5-9b", "muse-glimmer-30b",
          "gpt-oss-20b", "deepseek-qwen3.5-9b-mtp", "lfm2.5-2.6b"]
HARNESSES = ["claude-code", "codex-cli", "opencode", "pi"]
TASK_ORDER = ["TERM-01", "TERM-02", "TERM-03", "SCI-01", "SCI-02", "SCI-03",
              "SWE-01", "SWE-02", "SWE-03", "SWE-04"]

EAB_MODELS = ["tiel-coder-35b", "ornith-1.5-9b"]
EAB_HARNESSES = ["pi", "opencode", "codex-cli"]
EAB_CONDITIONS = ["baseline", "improve", "mcp", "skills", "mcp-skills"]
EAB_TASKS = 18

INTERVAL = int(os.environ.get("DASH_INTERVAL", "300"))
_STAMP = re.compile(r"-(\d{8}-\d{6})$")


def _eab_task_map() -> list[tuple[str, str]]:
    """[(full_task_name, short_code), ...] from benchmark/tasks/*/*.yaml."""
    out = []
    for f in sorted(glob.glob(str(EAB / "benchmark" / "tasks" / "*" / "*.yaml"))):
        name = Path(f).stem
        out.append((name, name.split("-")[0]))
    return out


EAB_CODE_MAP = _eab_task_map()
FULL2SHORT = {full: short for full, short in EAB_CODE_MAP}

# colour helpers -----------------------------------------------------------
GREEN, YELLOW, RED, NONE, RUN, IDLE = "green3", "yellow3", "red3", "grey37", "bold green", "grey50"
COND_STYLE = {"baseline": "grey58", "mcp": "cyan3", "skills": "magenta3", "mcp-skills": "bold green3"}


def _rw_style(v: float) -> str:
    return GREEN if v >= 0.8 else (YELLOW if v >= 0.5 else (RED if v > 0 else NONE))


def reward_text(v: float | None) -> Text:
    if v is None:
        return Text("—", style=NONE, justify="right")
    return Text(f"{v:.2f}", style=_rw_style(v), justify="right")


def reward_count_text(avg: float, n: int) -> Text:
    t = reward_text(avg)
    t.append(f" ({n})", style=NONE)
    return t


def task_text(v: float | None) -> Text:
    if v is None:
        return Text("·", style=NONE)
    if v >= 1.0:
        return Text("✓", style=GREEN)
    if v > 0:
        return Text(f"{v:.1f}", style=YELLOW)
    return Text("✗", style=RED)


def eab_task_text(status: str | None, reward: float | None) -> Text:
    if status is None:
        return Text("·", style=NONE)
    if status == "x":
        return Text("⏱", style=YELLOW)
    if reward is not None and reward >= 1.0:
        return Text("✓", style=GREEN)
    if reward:
        return Text(f"{reward:.1f}", style=YELLOW)
    return Text("✗", style=RED)


def bar_text(frac: float) -> Text:
    filled = int(round(frac * 10))
    style = GREEN if frac >= 0.999 else (YELLOW if frac > 0 else NONE)
    return Text("█" * filled, style=style) + Text("░" * (10 - filled), style=NONE)


def cond_text(c: str) -> Text:
    return Text(c, style=COND_STYLE.get(c, "white"))


# ----------------------------------------------------------------- collectors
def _pgrep(pattern: str) -> list[str]:
    out = subprocess.run(["pgrep", "-af", pattern], capture_output=True, text=True, timeout=10).stdout
    return [l for l in out.splitlines() if "pgrep" not in l and "dashboard.py" not in l]


def collect_processes() -> dict:
    runner = _pgrep("runner/run.py")
    driver = _pgrep("scripts/eab-full-run.sh")
    harbor = _pgrep("harbor run")
    current = ""
    for line in harbor:
        for tok in line.split():
            if not tok.endswith(".yaml"):
                continue
            stem = Path(tok).stem
            current = Path(tok).parent.name if stem in ("job", "job_config") else stem
    return {"coding": bool(runner), "eab_driver": bool(driver),
            "harbor": len(harbor), "current": current}


def collect_coding() -> dict:
    path = MB / "reports" / "results.jsonl"
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                log.warning("bad json line in %s", path)
                continue
            if r.get("status") != "dry":
                rows.append(r)
    latest = {(r.get("task"), r.get("model"), r.get("harness")): r for r in rows}
    models = [m for m in MODELS if any(k[1] == m for k in latest)]
    models += sorted({k[1] for k in latest if k[1] not in models})
    # mean reward per (model, harness) so views can rank best -> worst
    buckets: dict[tuple, list] = {}
    for (task, mo, hh), r in latest.items():
        if r.get("reward") is not None:
            buckets.setdefault((mo, hh), []).append(r["reward"])
    score_avg = {k: sum(v) / len(v) for k, v in buckets.items()}
    return {"latest": latest, "models": models, "n": len(latest), "score_avg": score_avg}


def _task_status(res: Path) -> tuple[str | None, float | None]:
    """Return (status, reward) for an EAB job dir.

    status: None=pending (no result), 'x'=uncovered (infra timeout), 'f'=fail,
            'p'=pass.  reward is the graded reward (may be partial).
    """
    try:
        j = json.loads(res.read_text())
    except Exception:
        log.warning("could not read %s", res)
        return (None, None)
    evals = j.get("stats", {}).get("evals", {})
    reward = None
    uncovered = False
    for ev in evals.values():
        if ev.get("exception_stats"):
            uncovered = True
        m = ev.get("metrics")
        if m:
            reward = m[0].get("mean", m[0].get("reward"))
    if uncovered and not reward:
        return ("x", None)
    if reward is None:
        return (None, None)
    return (("p" if reward >= 1.0 else "f"), reward)


def collect_eab() -> dict:
    """Per-combo task detail: each combo row carries the status of its 18 tasks.

    Only jobs from the current run are counted (job timestamp >= the run start
    parsed from the newest eab-full-*.log), so earlier studies don't leak in.
    """
    logs = sorted(glob.glob(str(EAB / "runs" / "eab-full-*.log")))
    run_start = ""
    if logs:
        mm = _STAMP.search(Path(logs[-1]).stem)
        run_start = mm.group(1) if mm else ""

    combos = []
    total_done = 0
    done_combos = 0
    for m in EAB_MODELS:
        for h in EAB_HARNESSES:
            for c in EAB_CONDITIONS:
                tasks = {short: (None, None) for _, short in EAB_CODE_MAP}
                marker = f"-{m}-{h}-{c}-"
                pat = str(EAB / "runs" / "harbor" / f"eab-*-{m}-{h}-{c}-*" / "result.json")
                for res in glob.glob(pat):
                    dirname = Path(res).parent.name
                    s = _STAMP.search(dirname)
                    if run_start and (not s or s.group(1) < run_start):
                        continue
                    try:
                        full = dirname[len("eab-"):dirname.index(marker)]
                    except ValueError:
                        continue
                    short = FULL2SHORT.get(full, full)
                    tasks[short] = _task_status(Path(res))
                done = sum(1 for st, _ in tasks.values() if st is not None)
                combos.append({"model": m, "harness": h, "condition": c,
                               "tasks": tasks, "done": done})
                total_done += done
                done_combos += done >= EAB_TASKS

    recent = []
    if logs:
        try:
            for ln in reversed(Path(logs[-1]).read_text(errors="replace").splitlines()):
                if ln.strip():
                    recent.append(ln)
                if len(recent) >= 60:
                    break
        except OSError as e:
            log.warning("could not read EAB log %s: %s", logs[-1], e)
    total = len(combos) * EAB_TASKS
    return {"combos": combos, "total_done": total_done, "done_combos": done_combos,
            "total": total, "run_start": run_start,
            "log": logs[-1] if logs else "(no log yet)", "recent": list(reversed(recent))}


# ----------------------------------------------------------------- app
class Dashboard(App):
    CSS = """
    Screen { layout: vertical; }
    #status { height: 5; padding: 0 1; background: $boost; }
    #body { height: 1fr; }
    #left { width: 64%; }
    #right { width: 36%; }
    .panel-title { text-style: bold; background: $panel; padding: 0 1; }
    DataTable { height: 1fr; }
    #coding { height: auto; max-height: 12; }
    #eabcombo { height: 1fr; }
    #codingtasks { height: 1fr; }
    #eablog { height: 12; border: round $primary; }
    """
    TITLE = "BetoLink · benchmark runs"
    SUB_TITLE = "coding suite + earth-agent-bench"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh now"),
        Binding("+", "faster", "Interval +"),
        Binding("-", "slower", "Interval -"),
        Binding("s", "toggle_auto", "Auto-refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.interval = INTERVAL
        self.auto = True
        self.next_refresh = time.time() + self.interval
        self.errors: list[str] = []
        self._last_summary = None
        self.pdata: dict = {"latest": {}, "models": [], "n": 0}
        self.edata: dict = {"combos": [], "total_done": 0, "done_combos": 0,
                            "total": 0, "recent": []}
        self.proc: dict = {"coding": False, "eab_driver": False, "harbor": 0, "current": ""}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("starting…", id="status")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Static("CODING SUITE — mean reward (tasks scored)", classes="panel-title")
                yield DataTable(id="coding")
                yield Static("EAB — combos × 18 tasks   ✓pass · part=yellow · ✗fail · ⏱timeout · ·pending",
                             classes="panel-title")
                yield DataTable(id="eabcombo")
            with Vertical(id="right"):
                yield Static("CODING — per-task grid (latest)", classes="panel-title")
                yield DataTable(id="codingtasks")
                yield Static("EAB — recent log", classes="panel-title")
                yield RichLog(id="eablog", highlight=False, markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        log.info("dashboard start; interval=%ss log=%s", self.interval, LOG_PATH)
        self.refresh_data()
        self.set_interval(1.0, self._tick)

    def _handle_exception(self, error: Exception) -> None:  # type: ignore[override]
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        log.error("APP EXCEPTION: %s", tb)
        self.errors.append(f"{type(error).__name__}: {error}")
        try:
            self._update_status(time.time())
        except Exception:
            pass

    def _safe(self, label: str, fn, default):
        try:
            return fn()
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            log.error("refresh step '%s' failed: %s", label, tb)
            self.errors.append(f"{label}: {type(e).__name__}: {e}")
            return default

    # ---- refresh ----
    def refresh_data(self) -> None:
        self.errors = []
        self.pdata = self._safe("coding", collect_coding, self.pdata)
        self.edata = self._safe("eab", collect_eab, self.edata)
        self.proc = self._safe("procs", collect_processes, self.proc)
        self._safe("render_coding", self._render_coding, None)
        self._safe("render_coding_tasks", self._render_coding_tasks, None)
        self._safe("render_eab_combo", self._render_eab_combo, None)
        self._safe("render_log", self._render_eab_log, None)
        self.next_refresh = time.time() + self.interval
        self._update_status(time.time())
        summary = (self.pdata.get("n", 0), self.edata.get("total_done", 0),
                   self.edata.get("total", 0), self.edata.get("done_combos", 0),
                   self.proc.get("coding"), self.proc.get("eab_driver"),
                   self.proc.get("current"))
        if summary != self._last_summary or self.errors:
            err = (" ERRORS: " + " | ".join(self.errors)) if self.errors else ""
            log.info("coding_cells=%d eab=%d/%d combos_done=%d runner=%s driver=%s current=%s%s",
                     *summary, err)
            self._last_summary = summary

    def _tick(self) -> None:
        now = time.time()
        if self.auto and now >= self.next_refresh:
            self.refresh_data()
        else:
            self._update_status(now)

    def _update_status(self, now: float) -> None:
        p, e = self.proc, self.edata
        pct = 100 * e.get("total_done", 0) // max(1, e.get("total", 1))
        t = Text()
        t.append("coding runner: ")
        t.append("RUNNING" if p.get("coding") else "idle", style=RUN if p.get("coding") else IDLE)
        t.append("   |   EAB driver: ")
        t.append("WAITING/RUNNING" if p.get("eab_driver") else "idle",
                 style=RUN if p.get("eab_driver") else IDLE)
        t.append(f"   |   harbor jobs: {p.get('harbor', 0)}\n")
        t.append("current: ", style="bold")
        t.append(f"{p.get('current') or '—'}\n")
        t.append("EAB progress: ")
        t.append(f"{e.get('total_done',0)}/{e.get('total',0)} tasks ({pct}%), "
                 f"{e.get('done_combos',0)}/{len(e.get('combos',[]))} combos", style=YELLOW)
        t.append(f"   updated {datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S')}"
                 f"   next in {max(0, int(self.next_refresh - now))}s"
                 f"   auto={'on' if self.auto else 'off'} ({self.interval}s)\n")
        if self.errors:
            t.append("⚠ " + " | ".join(self.errors[:2]), style="bold red")
        else:
            t.append("ok — see dashboard.log for details", style=NONE)
        self.query_one("#status", Static).update(t)

    # ---- render ----
    def _ranked_models(self) -> list[str]:
        """Models ordered best -> worst by mean reward across harnesses."""
        d = self.pdata
        totals: dict[str, list] = {}
        for (mo, _hh), avg in d.get("score_avg", {}).items():
            totals.setdefault(mo, []).append(avg)
        ranked = sorted(totals, key=lambda m: sum(totals[m]) / len(totals[m]), reverse=True)
        return ranked + [m for m in d["models"] if m not in ranked]

    def _ranked_pairs(self) -> list[tuple[str, str]]:
        """(model, harness) rows ordered best -> worst by mean reward."""
        sa = self.pdata.get("score_avg", {})
        pairs = [(m, h) for m in self.pdata["models"] for h in HARNESSES]
        pairs.sort(key=lambda p: sa.get(p, -1.0), reverse=True)
        return pairs

    def _render_coding(self) -> None:
        t = self.query_one("#coding", DataTable)
        t.clear(columns=True)
        t.add_columns("model", *HARNESSES, "avg")
        d = self.pdata
        for m in self._ranked_models():
            cells, allvals = [], []
            for h in HARNESSES:
                vals = [r["reward"] for (task, mo, hh), r in d["latest"].items()
                        if mo == m and hh == h and r.get("reward") is not None]
                if vals:
                    avg = sum(vals) / len(vals)
                    cells.append(reward_count_text(avg, len(vals)))
                    allvals += vals
                else:
                    cells.append(Text("—", style=NONE, justify="right"))
            avg = (sum(allvals) / len(allvals)) if allvals else None
            cells.append(reward_text(avg))
            t.add_row(Text(m, style="bold"), *cells)
        t.cursor_type = "row"

    def _render_coding_tasks(self) -> None:
        t = self.query_one("#codingtasks", DataTable)
        t.clear(columns=True)
        t.add_columns("model", "harness", *TASK_ORDER)
        for m, h in self._ranked_pairs():
            row = [task_text(self.pdata["latest"].get((task, m, h), {}).get("reward"))
                   for task in TASK_ORDER]
            t.add_row(Text(m[:9], style="bold"), h[:6], *row)
        t.cursor_type = "row"

    def _render_eab_combo(self) -> None:
        t = self.query_one("#eabcombo", DataTable)
        t.clear(columns=True)
        shorts = [short for _, short in EAB_CODE_MAP]
        t.add_columns("model", "harness", "cond", *shorts, "done")
        for combo in self.edata["combos"]:
            row = [Text(combo["model"][:9], style="bold"), combo["harness"][:6],
                   cond_text(combo["condition"])]
            row += [eab_task_text(*combo["tasks"].get(sh, (None, None))) for sh in shorts]
            row.append(Text(f"{combo['done']}/{EAB_TASKS}",
                            style=GREEN if combo["done"] >= EAB_TASKS else NONE))
            t.add_row(*row)
        t.cursor_type = "row"
        t.zebra_stripes = True

    def _render_eab_log(self) -> None:
        log_w = self.query_one("#eablog", RichLog)
        log_w.clear()
        for ln in self.edata.get("recent", [])[-14:]:
            log_w.write(ln)

    # ---- actions ----
    def action_refresh(self) -> None:
        log.info("manual refresh")
        self.refresh_data()

    def action_faster(self) -> None:
        self.interval = max(10, self.interval - 30)
        self.next_refresh = time.time() + self.interval
        log.info("interval -> %ss", self.interval)

    def action_slower(self) -> None:
        self.interval += 30
        self.next_refresh = time.time() + self.interval
        log.info("interval -> %ss", self.interval)

    def action_toggle_auto(self) -> None:
        self.auto = not self.auto
        log.info("auto -> %s", self.auto)


if __name__ == "__main__":
    Dashboard().run()
