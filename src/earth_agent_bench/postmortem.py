"""Generate a per-model self-improvement skill from a failure postmortem.

Reads that model's Harbor runs, classifies every cell (solved / partial / timeout /
fail), pulls failure signatures and trajectory tallies, and writes
``improvements/<model>/self-improvement/SKILL.md`` — the artifact mounted only by
the ``improve`` condition. This closes the eval loop: measure → teach → re-measure.

Deterministic by construction. ``--llm`` (future) can refine the prose with a
strong reference model, but the digest below is always produced.
"""

from __future__ import annotations

import glob
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .runconfig import harness_ids

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "runs" / "harbor"
IMPROVEMENTS_DIR = REPO_ROOT / "improvements"
_STAMP = re.compile(r"-(\d{8}-\d{6})$")
S3_PAT = re.compile(r"s3|amazonaws", re.IGNORECASE)


@dataclass
class Cell:
    """One evaluated cell (task/condition/status/reward/note)."""
    task: str
    condition: str
    status: str        # solved | partial | timeout | fail | error
    reward: float | None = None
    note: str = ""


@dataclass
class Digest:
    """Aggregated postmortem for a model: cells + trajectory tallies."""
    model: str
    run_start: str = ""
    harness: str = "pi"
    cells: list[Cell] = field(default_factory=list)
    trajectory: dict = field(default_factory=dict)  # curl/search_data/s3 tallies

    @property
    def timeouts(self) -> list[Cell]:
        return [c for c in self.cells if c.status == "timeout"]

    @property
    def wrong(self) -> list[Cell]:
        return [c for c in self.cells if c.status in ("fail", "error")]

    @property
    def solved(self) -> list[Cell]:
        return [c for c in self.cells if c.status == "solved"]


def _latest_run_start() -> str:
    """Stamp of the most recent runs/eab-full-*.log, or ''."""
    logs = sorted(glob.glob(str(REPO_ROOT / "runs" / "eab-full-*.log")))
    if not logs:
        return ""
    m = _STAMP.search(Path(logs[-1]).stem)
    return m.group(1) if m else ""


def _classify(result_path: Path) -> tuple[str, float | None, str]:
    """Classify a job result.json into solved|partial|fail|timeout|error."""
    try:
        j = json.loads(result_path.read_text())
    except Exception:
        return "error", None, "unreadable result.json"
    evals = list(j.get("stats", {}).get("evals", {}).values())
    if not evals:
        return "error", None, "no eval"
    ev = evals[0]
    reward = None
    metrics = ev.get("metrics")
    if metrics:
        reward = metrics[0].get("reward", metrics[0].get("mean"))
    if ev.get("exception_stats"):
        return "timeout", reward, ",".join(ev["exception_stats"].keys())
    if reward is None:
        return "error", None, "no reward"
    if reward >= 0.999:
        return "solved", reward, ""
    if reward > 0:
        return "partial", reward, ""
    return "fail", reward, ""


def _failure_signature(job_dir: Path) -> str:
    """First meaningful error line from the verifier stdout, if any."""
    for pat in ("**/verifier/test-stdout.txt", "**/verifier/test_output.txt"):
        for f in glob.glob(str(job_dir / pat), recursive=True):
            lines = [ln.strip() for ln in Path(f).read_text(errors="replace").splitlines()
                     if ln.strip()]
            for ln in reversed(lines):
                if re.search(r"Error|assert|KeyError|ValueError|mismatch|::.*FAIL", ln):
                    return ln[:160]
    return ""


def _trajectory_tally(model: str, harness: str) -> dict:
    """Count curl/search_data/s3/http + steps across a model's transcripts."""
    tally = {"curl": 0, "search_data": 0, "s3": 0, "http": 0, "steps": 0}
    harnesses = (harness_ids() or ["pi"]) if harness == "all" else [harness]
    for h in harnesses:
        for f in glob.glob(str(RUNS_DIR / f"eab-*-{model}-{h}-*" / "*" / "agent" / "*.txt")):
            txt = Path(f).read_text(errors="replace")
            tally["steps"] += txt.count('"type":"turn_start"') or txt.count('"type": "turn_start"')
            for key, needle in (("curl", "curl "), ("search_data", "search_data"),
                                ("s3", "s3"), ("http", "http")):
                tally[key] += txt.lower().count(needle)
    return tally


def build_digest(model: str, harness: str = "pi", run_start: str | None = None) -> Digest:
    """Assemble a model's Digest from its Harbor runs (harness or 'all')."""
    run_start = run_start if run_start is not None else _latest_run_start()
    harnesses = (harness_ids() or ["pi"]) if harness == "all" else [harness]
    d = Digest(model=model, run_start=run_start, harness=harness)
    seen: set[tuple[str, str]] = set()
    for h in harnesses:
        for result in sorted(glob.glob(str(RUNS_DIR / f"eab-*-{model}-{h}-*" / "result.json"))):
            dirname = Path(result).parent.name
            m = _STAMP.search(dirname)
            if run_start and (not m or m.group(1) < run_start):
                continue
            marker = f"-{model}-{h}-"
            if marker not in dirname:
                continue
            body = dirname[len("eab-"):dirname.index(marker)]
            cond = _STAMP.sub("", dirname.split(marker, 1)[1])
            key = (h, body)
            if cond in ("improve",) or key in seen:
                continue
            status, reward, note = _classify(Path(result))
            sig = _failure_signature(Path(result).parent)
            seen.add(key)
            d.cells.append(Cell(body, cond, status, reward, note or sig))
    d.trajectory = _trajectory_tally(model, harness)
    return d


def render_skill(d: Digest) -> str:
    """Render the Digest as a self-improvement SKILL.md."""
    lines = [
        "---",
        "name: self-improvement",
        "description: >",
        f"  Model-specific countermeasures distilled from {d.model}'s failure postmortem",
        "  on the earth-agent-bench run. READ THIS FIRST and follow it before doing",
        "  anything else; each rule maps to a failure this exact model actually made.",
        "generator: deterministic-digest",
        f"source_run: {d.run_start}",
        f"model: {d.model}",
        "---",
        "",
        f"# Self-improvement — {d.model}",
        "",
        f"> Generated from the {d.run_start or 'latest'} evaluation on harness `{d.harness}`.",
        "> Do these; they are the mistakes you made last time.",
        "",
        "## Hard rules (always)",
        "",
        "1. **Out-of-region -> HTTPS, never S3.** This runs outside AWS. `s3://...`,",
        "   `*.s3.amazonaws.com`, `s3_credentials`, `s3fs` will not work (hang/403). Use",
        "   the HTTPS object URL, or the HTTPS path `earthaccess.open()`/`download()` return.",
        "2. **Inspect the inputs before writing code.** Print the real schema (columns,",
        "   keys, units, dtypes) of every input file first. Never hardcode a column name.",
        "3. **Match the exact acceptance criterion.** Re-read the asked quantity and units.",
        "4. **Verify before you finish.** Run the task's own test/verifier or reproduce the",
        "   expected output and diff it. 'Looks right' is not done.",
        "5. **Be decisive — minimize iterations.** Prefer the answer the skills/MCP give;",
        "   avoid long live-probing loops. Every retry costs wall-clock and grows context.",
        "6. **Respect the output contract.** Write exactly the required artifact path(s).",
        "",
        "## Observed failures this run",
        "",
        "| task | condition | outcome | reward | note |",
        "|---|---|---|---|---|",
    ]
    for c in sorted(d.cells, key=lambda c: (c.status != "timeout", c.task)):
        rw = "—" if c.reward is None else f"{c.reward:.2f}"
        lines.append(f"| {c.task} | {c.condition} | {c.status} | {rw} | {c.note[:80]} |")
    if not d.cells:
        lines.append("| (no jobs found) | | | | |")

    lines += ["", "## What went wrong, and the fix", ""]
    if d.timeouts:
        lines.append(f"- **You timed out on {len(d.timeouts)}/{len(d.cells)} tasks.** The dominant cause is "
                     "over-exploring (repeated live probing). Answer from the skills/MCP, verify once, stop.")
    if d.wrong:
        tasks = ", ".join(sorted({c.task for c in d.wrong})[:8])
        lines.append(f"- **Wrong answers on:** {tasks}. Re-check the exact quantity/units and inspect inputs first.")
    if d.trajectory.get("s3", 0) > 20:
        lines.append(f"- **You touched S3 ~{d.trajectory['s3']} times** — out of region it cannot work; use HTTPS.")
    if d.trajectory.get("search_data", 0) > 50:
        lines.append(f"- **~{d.trajectory['search_data']} `search_data` calls** — collapse the search loop; the "
                     "skills/MCP already answer most of these.")
    if not d.timeouts and not d.wrong:
        lines.append("- No timeouts or wrong answers recorded; keep the hard rules and re-verify.")
    lines.append("")
    return "\n".join(lines)


def write_skill(d: Digest, out_dir: Path = IMPROVEMENTS_DIR) -> Path:
    """Write the rendered skill under improvements/<model>/."""
    dest = out_dir / d.model / "self-improvement" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_skill(d))
    return dest
