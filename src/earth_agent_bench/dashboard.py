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
Run:  eab dashboard   (or: python -m earth_agent_bench.dashboard)
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
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from .runconfig import condition_ids, load_run_config, task_ids
from .runs import parse_job_dir

# ----------------------------------------------------------------- logging
LOG_PATH = Path(os.environ.get(
    "DASH_LOG", Path(__file__).resolve().parents[2] / "runs" / "dashboard.log"))
log = logging.getLogger("dashboard")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    _h = RotatingFileHandler(str(LOG_PATH), maxBytes=256 * 1024, backupCount=2)
    _h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
    log.addHandler(_h)


def _excepthook(exc_type, exc, tb):
    """Log uncaught exceptions to the dashboard log instead of crashing."""
    log.error("UNCAUGHT: %s", "".join(traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = _excepthook

# ----------------------------------------------------------------- constants
# Repo roots. earth-agent-bench root (this file is src/earth_agent_bench/dashboard.py).
EAB = Path(os.environ.get("EAB_REPO_DIR", Path(__file__).resolve().parents[2]))
ROOT = EAB.parent
MB = Path(os.environ.get("EAB_MB_DIR", ROOT / "mini-benchmarks"))

INTERVAL = int(os.environ.get("DASH_INTERVAL", "300"))
_STAMP = re.compile(r"-(\d{8}-\d{6})$")


def _load_yaml(path: Path) -> dict:
    """Best-effort YAML load; returns {} (and logs) when missing/unreadable."""
    try:
        import yaml
        return yaml.safe_load(path.read_text()) or {}
    except Exception as error:
        log.warning("could not load %s: %s", path, error)
        return {}


# Coding suite (mini-benchmarks): its own manifest is the source of truth.
_MB = _load_yaml(MB / "manifest.yaml")
MODELS = list(_MB.get("models", []))
HARNESSES = list(_MB.get("harnesses", []))
TASK_ORDER = [t["id"] for t in _MB.get("tasks", []) if isinstance(t, dict)]

# Earth-agent-bench: the run matrix comes from the master config (run.yaml).
_CFG = load_run_config()
EAB_MODELS = list(_CFG["models"])
EAB_HARNESSES = list(_CFG["harnesses"])
EAB_CONDITIONS = list(_CFG["conditions"])
EAB_TASKS = len(task_ids())
EAB_CODE_MAP = [(t, t.split("-")[0]) for t in task_ids()]
FULL2SHORT = dict(EAB_CODE_MAP)

# colour helpers -----------------------------------------------------------
GREEN, YELLOW, RED, NONE, RUN, IDLE = "green3", "yellow3", "red3", "grey37", "bold green", "grey50"
_PALETTE = ["grey58", "cyan3", "magenta3", "bold green3", "yellow3", "blue3", "red3"]
COND_STYLE = {c: _PALETTE[i % len(_PALETTE)]
              for i, c in enumerate(condition_ids() or EAB_CONDITIONS)}


def _rw_style(v: float) -> str:
    """Colour for a reward (green >=0.8, yellow >=0.5, red >0, grey ==0)."""
    return GREEN if v >= 0.8 else (YELLOW if v >= 0.5 else (RED if v > 0 else NONE))


def reward_text(v: float | None) -> Text:
    """Render a reward as coloured text ('-' when unknown)."""
    if v is None:
        return Text("—", style=NONE, justify="right")
    return Text(f"{v:.2f}", style=_rw_style(v), justify="right")


def reward_count_text(avg: float, n: int) -> Text:
    """Render an 'n/total' count coloured by pass rate."""
    t = reward_text(avg)
    t.append(f" ({n})", style=NONE)
    return t


def task_text(v: float | None) -> Text:
    """Render a coding task cell (green when solved)."""
    if v is None:
        return Text("·", style=NONE)
    if v >= 1.0:
        return Text("✓", style=GREEN)
    if v > 0:
        return Text(f"{v:.1f}", style=YELLOW)
    return Text("✗", style=RED)


def eab_task_text(status: str | None, reward: float | None) -> Text:
    """Render an EAB task cell coloured by reward."""
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
    """Render a unicode progress bar for done/total."""
    filled = int(round(frac * 10))
    style = GREEN if frac >= 0.999 else (YELLOW if frac > 0 else NONE)
    return Text("█" * filled, style=style) + Text("░" * (10 - filled), style=NONE)


def cond_text(c: str) -> Text:
    """Render a condition name with its colour."""
    return Text(c, style=COND_STYLE.get(c, "white"))


# ----------------------------------------------------------------- collectors
def _pgrep(pattern: str) -> list[str]:
    """Return pgrep -af lines matching a pattern (excluding this dashboard)."""
    out = subprocess.run(["pgrep", "-af", pattern], capture_output=True, text=True, timeout=10).stdout
    return [line for line in out.splitlines()
            if "pgrep" not in line and "dashboard.py" not in line]


def collect_processes() -> dict:
    """Snapshot running benchmark processes + the current job."""
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
    """Latest coding-suite result per (task, model, harness) + rankings."""
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
    for (_task, mo, hh), r in latest.items():
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


# ----------------------------------------------------------------- live view
def _newest_agent_file() -> Path | None:
    """Path to the most recently modified agent transcript, or None."""
    files = glob.glob(str(EAB / "runs" / "harbor" / "eab-*" / "*" / "agent" / "*.txt"))
    if not files:
        return None
    return Path(max(files, key=lambda f: os.path.getmtime(f)))


def _tail(path: Path, max_bytes: int = 300_000, max_lines: int = 120) -> list[str]:
    """Last N lines of a (possibly large) text file, dropping a partial tail line."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > max_bytes:
            fh.seek(size - max_bytes)
            data = fh.read().decode("utf-8", "replace")
            data = data.split("\n", 1)[1] if "\n" in data else data  # drop partial first line
        else:
            data = fh.read().decode("utf-8", "replace")
    lines = data.splitlines()
    # drop a trailing line that is an incomplete JSON record still being written
    if lines and lines[-1].startswith("{") and not lines[-1].rstrip().endswith("}"):
        lines = lines[:-1]
    return lines[-max_lines:]


def _tool_detail(inp) -> str:
    """Short human detail (command/path/query) from a tool-call dict."""
    if isinstance(inp, str):
        return inp
    if not isinstance(inp, dict):
        return ""
    for k in ("command", "cmd", "file_path", "filePath", "path", "query",
              "pattern", "url", "description", "prompt"):
        v = inp.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _first_text(holder) -> str:
    """First non-empty text-ish field of an event dict ('' if none)."""
    if not isinstance(holder, dict):
        return ""
    for k in ("text", "thinking", "reasoning", "content", "aggregate_output",
              "aggregated_output", "output", "result", "message"):
        v = holder.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _condense(line: str, width: int = 150) -> str | None:
    """Condense one harness stream line into a short brain/tool/done line."""
    line = line.strip()
    if not line:
        return None
    if not line.startswith("{"):
        return line[:width]
    try:
        o = json.loads(line)
    except Exception:
        return None
    if not isinstance(o, dict):
        return None
    t = o.get("type", "")
    one = lambda s: " ".join(str(s).split())[:width]  # noqa: E731
    # pi (pi-mono) events
    if t == "tool_execution_start":
        a = o.get("args") or {}
        detail = a.get("command") or a.get("path") or a.get("query") or (json.dumps(a)[:80] if a else "")
        return f"▶ {o.get('toolName')}: {one(detail)}"
    if t == "tool_execution_end":
        return f"✓ {o.get('toolName')}"
    if t in ("message_end", "message_start"):
        msg = o.get("message") or {}
        if msg.get("role") == "assistant":
            for c in msg.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                    return f"✎ {one(c['text'])}"
                if isinstance(c, dict) and c.get("type") == "thinking" and c.get("thinking"):
                    return f"🧠 {one(c['thinking'])}"
    # opencode-family events: {"type": ..., "part": {...}}
    part = o.get("part")
    if isinstance(part, dict):
        if t == "text" and part.get("text"):
            return f"✎ {one(part['text'])}"
        if t == "reasoning" and part.get("text"):
            return f"🧠 {one(part['text'])}"
        if t == "tool_use":
            st = part.get("state") or {}
            inp = st.get("input") or {}
            detail = (inp.get("command") or inp.get("filePath") or inp.get("path")
                      or inp.get("query") or part.get("title") or "")
            mark = "✓" if st.get("status") == "completed" else "▶"
            return f"{mark} {part.get('tool')}: {one(detail)}"
    # codex (`codex exec --json`): {"type":"item.*","item":{...}}
    item = o.get("item")
    if isinstance(item, dict):
        it = item.get("type", "")
        if it in ("agent_message", "assistant_message") and item.get("text"):
            return f"✎ {one(item['text'])}"
        if it in ("reasoning", "reasoning_summary") and item.get("text"):
            return f"🧠 {one(item['text'])}"
        if it in ("command_execution", "local_shell_call", "exec", "shell"):
            cmd = item.get("command") or _tool_detail(item) or _tool_detail(item.get("arguments"))
            mark = "✓" if str(o.get("type", "")).endswith("completed") else "▶"
            return f"{mark} $ {one(cmd)}"
        if it in ("file_change", "patch", "apply_patch"):
            return f"▶ edit: {one(item.get('path') or item.get('changes') or '')}"
    # claude-code stream-json: {"type":"assistant"|"user","message":{"content":[...]}}
    if t in ("assistant", "user") and isinstance(o.get("message"), dict):
        for c in o["message"].get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text" and c.get("text"):
                return f"✎ {one(c['text'])}"
            if c.get("type") == "thinking" and c.get("thinking"):
                return f"🧠 {one(c['thinking'])}"
            if c.get("type") == "tool_use":
                return f"▶ {c.get('name')}: {one(_tool_detail(c.get('input') or {}))}"
            if c.get("type") == "tool_result":
                return None
    # generic fallback for any other harness schema
    for holder in (o, part or {}, item or {}):
        if not isinstance(holder, dict):
            continue
        tool = holder.get("tool") or holder.get("tool_name") or holder.get("name")
        inp = holder.get("arguments") or holder.get("input") or holder.get("args")
        if tool and inp:
            return f"▶ {tool}: {one(_tool_detail(inp))}"
    txt = _first_text(part or o) or _first_text(item or {})
    if txt:
        return f"✎ {one(txt)}"
    return None


def _job_info(job_dir: str) -> dict:
    """Parse a job dir name into task/model/harness/condition (blank if unknown)."""
    ref = parse_job_dir(job_dir)
    return {"job_dir": job_dir, "task": ref.task, "model": ref.model,
            "harness": ref.harness, "condition": ref.condition}


def collect_live() -> dict:
    """Tail the newest agent transcript and condense it for the LIVE view."""
    path = _newest_agent_file()
    if path is None:
        return {"lines": ["(no agent output yet)"], "header": "LIVE — current agent", "path": "", "task": ""}
    job_dir = path.parents[2].name if len(path.parents) > 2 else ""
    info = _job_info(job_dir)
    header = (f"LIVE — {info['task']} · {info['model']} · {info['harness']} · {info['condition']}"
              if info["task"] else "LIVE — current agent")
    try:
        lines = [x for x in (_condense(line) for line in _tail(path)) if x][-40:]
    except OSError as e:
        return {"lines": [f"(read error: {e})"], "header": header, "path": str(path), "task": info["task"]}
    return {"lines": lines or ["(waiting for output…)"], "header": header,
            "path": str(path), "task": info["task"]}


def collect_task(task: str) -> dict:
    """The instruction (what the agent must solve) for the current task."""
    if not task:
        return {"header": "CURRENT TASK", "lines": ["(no active task)"]}
    p = EAB / "harbor" / "generated" / task / "instruction.md"
    try:
        lines = (p.read_text(errors="replace").splitlines() if p.exists()
                 else [f"(no instruction found for {task})"])
    except OSError as e:
        lines = [f"(read error: {e})"]
    return {"header": f"CURRENT TASK — {task}", "lines": lines}


# ----------------------------------------------------------------- log popup
class LogScreen(ModalScreen):
    """Pop-up showing the tail of the EAB run log (toggle with Ctrl+L)."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("ctrl+l", "close", "Close"),
        Binding("q", "close", "Close"),
    ]
    CSS = """
    LogScreen { align: center middle; background: $background 60%; }
    #logbox { width: 92%; height: 84%; border: round $primary; background: $surface; }
    #logtitle { text-style: bold; background: $panel; padding: 0 1; }
    #logview { height: 1fr; }
    """

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        with Vertical(id="logbox"):
            yield Static("EAB run log  —  Esc / Ctrl+L to close", id="logtitle")
            yield RichLog(id="logview", highlight=False, markup=False, wrap=False)

    def on_mount(self) -> None:
        lv = self.query_one("#logview", RichLog)
        lines: list[str] = []
        try:
            p = Path(self.path) if self.path else None
            if p and p.exists():
                lines = p.read_text(errors="replace").splitlines()[-300:]
        except Exception:
            lines = ["(could not read log)"]
        for ln in lines or ["(empty)"]:
            lv.write(ln)

    def action_close(self) -> None:
        self.app.pop_screen()


# ----------------------------------------------------------------- app
class Dashboard(App):
    """The Textual app: coding matrix, EAB combos, live agent, current task."""
    CSS = """
    Screen { layout: vertical; }
    #status { height: 5; padding: 0 1; background: $boost; }
    #top { height: 1fr; }
    #bottom { height: 1fr; }
    #left { width: 60%; }
    #right { width: 40%; }
    #livebox { width: 70%; }
    #taskbox { width: 30%; }
    .panel-title { text-style: bold; background: $panel; padding: 0 1; }
    DataTable { height: 1fr; }
    #coding { height: auto; max-height: 12; }
    #eabcombo { height: 1fr; }
    #codingtasks { height: 1fr; }
    #live { height: 1fr; border: round $accent; }
    #task { height: 1fr; border: round $secondary; }
    """
    TITLE = "BetoLink · benchmark runs"
    SUB_TITLE = "coding suite + earth-agent-bench"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh now"),
        Binding("+", "faster", "Interval +"),
        Binding("-", "slower", "Interval -"),
        Binding("s", "toggle_auto", "Auto-refresh"),
        Binding("ctrl+l", "show_logs", "Logs"),
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
        self.ldata: dict = {"lines": [], "header": "LIVE — current agent", "task": ""}
        self.tdata: dict = {"lines": [], "header": "CURRENT TASK"}
        self._task_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("starting…", id="status")
        with Horizontal(id="top"):
            with Vertical(id="left"):
                yield Static("CODING SUITE — mean reward (tasks scored)", classes="panel-title")
                yield DataTable(id="coding")
                yield Static("EAB — combos × 18 tasks   ✓pass · part=yellow · ✗fail · ⏱timeout · ·pending",
                             classes="panel-title")
                yield DataTable(id="eabcombo")
            with Vertical(id="right"):
                yield Static("CODING — per-task grid (latest)", classes="panel-title")
                yield DataTable(id="codingtasks")
        with Horizontal(id="bottom"):
            with Vertical(id="livebox"):
                yield Static("LIVE — current agent   (Ctrl+L: logs)", id="live_title", classes="panel-title")
                yield RichLog(id="live", highlight=False, markup=False, wrap=True)
            with Vertical(id="taskbox"):
                yield Static("CURRENT TASK", id="task_title", classes="panel-title")
                yield RichLog(id="task", highlight=False, markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        log.info("dashboard start; interval=%ss log=%s", self.interval, LOG_PATH)
        self.refresh_data()
        self.set_interval(1.0, self._tick)
        self.set_interval(4.0, self._tick_live)  # live agent view refreshes fast

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
        self.ldata = self._safe("live_collect", collect_live, self.ldata)
        self._safe("render_live", self._render_live, None)
        self._safe("render_task", self._maybe_task, None)
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

    def _tick_live(self) -> None:
        # fast path: refresh only the live agent pane (and the current-job line)
        self.ldata = self._safe("live_collect", collect_live, self.ldata)
        self._safe("render_live", self._render_live, None)
        self._safe("task", self._maybe_task, None)
        self._safe("procs", lambda: self.proc.update(collect_processes()), None)
        self._update_status(time.time())

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

    def _render_live(self) -> None:
        self.query_one("#live_title", Static).update(self.ldata.get("header", "LIVE — current agent"))
        live = self.query_one("#live", RichLog)
        live.clear()
        for ln in self.ldata.get("lines", []):
            style = None
            if ln.startswith("▶"):
                style = "cyan3"
            elif ln.startswith("✓"):
                style = "green3"
            elif ln.startswith("✎"):
                style = "white"
            elif ln.startswith("🧠"):
                style = "grey58"
            live.write(Text(ln, style=style) if style else ln)

    def _maybe_task(self) -> None:
        task = self.ldata.get("task", "")
        if task == self._task_name:
            return
        self._task_name = task
        self.tdata = collect_task(task)
        self._render_task()

    def _render_task(self) -> None:
        self.query_one("#task_title", Static).update(self.tdata.get("header", "CURRENT TASK"))
        tv = self.query_one("#task", RichLog)
        tv.clear()
        for ln in self.tdata.get("lines", []):
            tv.write(ln)

    # ---- actions ----
    def action_show_logs(self) -> None:
        self.push_screen(LogScreen(self.edata.get("log", "")))

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


def main(interval: int | None = None) -> None:
    """Launch the live dashboard (blocking)."""
    global INTERVAL
    if interval:
        INTERVAL = int(interval)
    Dashboard().run()


if __name__ == "__main__":
    main()
