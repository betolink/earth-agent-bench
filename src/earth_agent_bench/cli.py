from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import mcp as mcp_mod
from . import report as report_mod
from .evals import EvalResult, grade, load_suite, summarize
from .models import discover_models, doctor_models, reconcile_models
from .oracles.cmr import fetch_services
from .oracles.service_matrix import build_matrix
from .oracles.services import ServiceCatalog
from .oracles.virtualizability import VirtualizabilityOracle
from .schemas import RunObservation
from .scoring import score_run
from .sweep import SweepSpec, run_sweep
from .tasks import DEFAULT_TASKS_DIR, load_all, load_task, render_instruction

app = typer.Typer(help="earth-agent-bench: access-pattern selection benchmark tooling")
harbor_app = typer.Typer(help="Generate Harbor task packages and run them")
eval_app = typer.Typer(help="Grade the single-clean-value correctness eval suite")
models_app = typer.Typer(help="Query and reconcile the LiteLLM model roster")
mcp_app = typer.Typer(help="Probe the MCP servers declared for the mcp conditions")
app.add_typer(harbor_app, name="harbor")
app.add_typer(eval_app, name="eval")
app.add_typer(models_app, name="models")
app.add_typer(mcp_app, name="mcp")
console = Console()

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARQUET = REPO_ROOT / "benchmark" / "data" / "virtualizability.parquet"
DEFAULT_SERVICES = REPO_ROOT / "benchmark" / "oracles" / "services.yaml"
DEFAULT_EVAL_SUITE = REPO_ROOT / "experiments" / "evals" / "suite.yaml"


def _load_env() -> None:
    """Populate os.environ from <repo>/.env and $PWD/.env (existing vars win).

    Convenience so `eab …` picks up LITE_LLM_ENDPOINT / LITE_LLM_API_KEY /
    EARTHDATA_TOKEN without a manual `set -a; . ./.env`. Real environment
    variables always take precedence (setdefault).
    """
    import os

    seen: set[Path] = set()
    for path in (REPO_ROOT / ".env", Path.cwd() / ".env"):
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key:
                os.environ.setdefault(key, val.strip().strip('"').strip("'"))


@app.callback()
def _startup() -> None:
    """earth-agent-bench CLI (loads <repo>/.env into the environment first)."""
    _load_env()



def _oracle(parquet: Path) -> VirtualizabilityOracle:
    """Build a VirtualizabilityOracle from the parquet path (exits on missing file)."""
    try:
        return VirtualizabilityOracle(parquet)
    except FileNotFoundError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command()
def validate(
    tasks_dir: Path = typer.Option(DEFAULT_TASKS_DIR, help="Directory of task YAML files"),
) -> None:
    """Validate every task YAML against the schema."""
    tasks = load_all(tasks_dir)
    if not tasks:
        console.print(f"[red]No task files found under {tasks_dir}[/red]")
        raise typer.Exit(code=1)
    table = Table(title=f"Tasks ({len(tasks)})")
    table.add_column("task_id")
    table.add_column("sphere")
    table.add_column("gold")
    table.add_column("collections")
    for task in tasks:
        preferred = [c.short_name for c in task.collections if c.tier == "preferred"]
        table.add_row(
            task.task_id,
            task.science_sphere,
            "+".join(task.gold.primary_patterns),
            ", ".join(preferred),
        )
    console.print(table)


@app.command()
def run(
    task: Optional[Path] = typer.Argument(
        None, help="Task .yaml/.md for a single run; omit to run the full sweep."),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Experiment name (used as the run identity)."),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Run-config YAML (default experiments/run.yaml); a bare name resolves under experiments/."),
    model: Optional[str] = typer.Option(None, help="Model id (single-run only)."),
    harness: Optional[str] = typer.Option(None, help="Harness (single-run only)."),
    condition: str = typer.Option("baseline", help="baseline | mcp | skills | mcp-skills"),
    trial: int = typer.Option(1),
    runs_root: Path = typer.Option(REPO_ROOT / "runs", help="Where run workspaces live"),
    timeout: int = typer.Option(600, help="Per-run timeout in seconds (default 600 = 10 min)"),
    dry_run: bool = typer.Option(False, help="Print workspace/env/command only"),
) -> None:
    """Run a single task, or (no task) the full EAB sweep under --name.

    \b
      eab run --name experiment-1               # full sweep, named
      eab run --name smart-ext --config smart-external.yml
      eab run task.yaml --model m --harness pi  # one task
    """
    if task is None:  # full sweep
        import os
        import subprocess

        from .runconfig import run_config_path

        env = dict(os.environ)
        if name:
            env["EAB_RUN_NAME"] = name
        if config:
            env["EAB_RUN_CONFIG"] = str(run_config_path(config))
        console.print(f"[green]full sweep[/green] name={name or '(run.yaml default)'} "
                      f"config={config or '(default)'}")
        raise typer.Exit(code=subprocess.call(
            ["bash", "scripts/eab-full-run.sh"], cwd=REPO_ROOT, env=env))
    if not model or not harness:
        console.print("[red]--model and --harness are required for a single run[/red]")
        raise typer.Exit(code=1)
    from .runner import RunSpec, execute

    spec = RunSpec(
        task_path=task, model_id=model, harness=harness,
        condition=condition, trial=trial, runs_root=runs_root,
        timeout_s=timeout,
    )
    raise typer.Exit(code=execute(spec, dry_run=dry_run))


@app.command()
def sweep(
    tasks: str = typer.Argument(..., help="Comma-separated task paths/dirs/globs, or 'all'"),
    models: str = typer.Option("all", help="Comma-separated model ids or 'all'"),
    harnesses: str = typer.Option("all", help="Comma-separated harnesses or 'all'"),
    conditions: str = typer.Option("all", help="Comma-separated conditions or 'all'"),
    trial: int = typer.Option(1),
    runs_root: Path = typer.Option(REPO_ROOT / "runs", help="Where run workspaces live"),
    timeout: int = typer.Option(600, help="Per-run timeout in seconds (default 600 = 10 min)"),
    dry_run: bool = typer.Option(False, help="Print every cell without executing"),
    continue_on_error: bool = typer.Option(True, help="Keep going after a failed cell"),
) -> None:
    """Run the cartesian product of tasks x models x harnesses x conditions."""
    spec = SweepSpec(
        tasks=tasks, models=models, harnesses=harnesses, conditions=conditions,
        trial=trial, runs_root=runs_root, dry_run=dry_run,
        continue_on_error=continue_on_error, timeout_s=timeout,
    )
    raise typer.Exit(code=run_sweep(spec))


@harbor_app.command("generate")
def harbor_generate(
    tasks: str = typer.Argument(
        "all",
        help="Comma-separated paths / eval ids / benchmark ids / sphere aliases, or 'all' / 'pilot'",
    ),
    condition: str = typer.Option("baseline", help="baseline | mcp | skills | mcp-skills"),
    out: Path = typer.Option(REPO_ROOT / "harbor" / "generated"),
) -> None:
    """Generate real Harbor task packages (task.toml layout) for each task."""
    from .harbor import generate_package, resolve_tasks

    for task_path in resolve_tasks(tasks):
        package = generate_package(task_path, condition, out)
        console.print(f"[green]generated[/green] {package}")


@harbor_app.command("run")
def harbor_run(
    tasks: str = typer.Argument(
        ..., help="Paths / ids / sphere aliases, or 'pilot'"
    ),
    model: str = typer.Option(..., help="Model id from experiments/models.yaml"),
    harness: str = typer.Option(..., help="pi | opencode | codex-cli | claude-code"),
    condition: str = typer.Option("baseline"),
    out: Path = typer.Option(REPO_ROOT / "harbor" / "generated"),
    jobs_dir: Path = typer.Option(REPO_ROOT / "runs" / "harbor"),
    job_name: Optional[str] = typer.Option(
        None, "--job-name", help="Fixed job directory name (default: unique per run)"
    ),
    force: bool = typer.Option(
        False, "--force", help="Delete an existing job directory of the same name first"
    ),
    dry_run: bool = typer.Option(False, help="Print the harbor command only"),
) -> None:
    """Generate packages and a JobConfig, then invoke the harbor CLI."""
    from .harbor import resolve_tasks, run_harbor

    code = 0
    for task_path in resolve_tasks(tasks):
        code = (
            run_harbor(
                task_path, model, harness, condition, out, jobs_dir, dry_run,
                job_name=job_name, force=force,
            )
            or code
        )
        if code != 0:
            break
    raise typer.Exit(code=code)


@app.command()
def instruction(
    task_path: Path = typer.Argument(..., help="Path to a task YAML file"),
) -> None:
    """Render the agent-facing instruction for a task."""
    console.print(render_instruction(load_task(task_path)))


@app.command()
def matrix(
    short_name: str = typer.Argument(..., help="Collection short name"),
    parquet: Path = typer.Option(DEFAULT_PARQUET, help="Virtualizability parquet"),
    services: Path = typer.Option(DEFAULT_SERVICES, help="Curated services YAML"),
    cmr: bool = typer.Option(False, help="Merge live CMR service discovery"),
) -> None:
    """Show the service availability matrix for a collection."""
    virt = _oracle(parquet)
    catalog = ServiceCatalog(services) if services.exists() else None
    live = None
    if cmr:
        with console.status(f"querying CMR for {short_name}..."):
            live = fetch_services(short_name).get("patterns") or None
    result = build_matrix(short_name, virt, catalog, live)
    console.print_json(json.dumps(result, default=str))


@app.command()
def collections(
    parquet: Path = typer.Option(DEFAULT_PARQUET, help="Virtualizability parquet"),
    grade: Optional[str] = typer.Option(None, help="Filter by grade (A/B/C/D)"),
) -> None:
    """List collections known to the EDVS parquet oracle."""
    virt = _oracle(parquet)
    rows = [(name, virt.grade(name)) for name in virt.collections()]
    if grade:
        rows = [row for row in rows if row[1] == grade.upper()]
    table = Table(title=f"EDVS oracle collections ({len(rows)})")
    table.add_column("short_name")
    table.add_column("grade")
    for name, collection_grade in rows:
        style = "green" if collection_grade in {"A", "B"} else "yellow"
        table.add_row(name, f"[{style}]{collection_grade}[/{style}]")
    console.print(table)


@app.command()
def score(
    observation_path: Path = typer.Argument(..., help="Run observation JSON"),
    tasks_dir: Path = typer.Option(DEFAULT_TASKS_DIR, help="Directory of task YAML files"),
) -> None:
    """Score a run observation against its task's gold standard."""
    observation_data = json.loads(observation_path.read_text())
    observation = RunObservation.model_validate(observation_data)
    task = _find_task(observation.task_id, tasks_dir)
    result = score_run(task, observation)
    console.print_json(result.model_dump_json())


def _find_task(task_id: str, tasks_dir: Path):
    """Locate a task YAML by id under the tasks directory."""
    for task in load_all(tasks_dir):
        if task.task_id == task_id:
            return task
    console.print(f"[red]Task '{task_id}' not found under {tasks_dir}[/red]")
    raise typer.Exit(code=1)


@eval_app.command("grade")
def eval_grade(
    task_id: str = typer.Argument(..., help="Eval task id, e.g. 01_hls_open_vs_download"),
    answer_file: Path = typer.Argument(..., help="Path to the produced ./output/answer.txt"),
    suite: Path = typer.Option(DEFAULT_EVAL_SUITE, help="Eval suite manifest"),
    tool_calls: Optional[int] = typer.Option(None, help="Instrumented tool-call count"),
) -> None:
    """Grade one produced answer against its gold (deterministic, no LLM)."""
    gold = _find_gold(task_id, suite)
    produced = answer_file.read_text().strip() if answer_file.exists() else None
    console.print_json(grade(gold, produced, tool_calls).model_dump_json())


@eval_app.command("report")
def eval_report(
    results_dir: Path = typer.Argument(..., help="Directory of per-attempt result JSON files"),
    out: Optional[Path] = typer.Option(None, help="Write summary.json here (default: results_dir)"),
) -> None:
    """Aggregate per-attempt results into pass@1 / coverage / tool-call summary."""
    files = sorted(results_dir.glob("*.json"))
    results = [EvalResult.model_validate(json.loads(p.read_text())) for p in files]
    summary = summarize(results)
    console.print_json(json.dumps(summary))
    if out is None:
        out = results_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2))
    console.print(f"[green]wrote[/green] {out}")


def _find_gold(task_id: str, suite: Path):
    """Locate a task's gold-standard entry within an eval suite."""
    for gold in load_suite(suite):
        if gold.task_id == task_id:
            return gold
    console.print(f"[red]Eval task '{task_id}' not found in {suite}[/red]")
    raise typer.Exit(code=1)


@models_app.command("discover")
def models_discover() -> None:
    """List model ids served by the LiteLLM gateway (/v1/models)."""
    try:
        records = discover_models()
    except Exception as error:  # noqa: BLE001
        console.print(f"[red]gateway query failed: {error}[/red]")
        raise typer.Exit(code=1) from error
    table = Table(title=f"Gateway models ({len(records)})")
    table.add_column("id")
    for record in sorted(records, key=lambda r: r["id"]):
        table.add_row(record["id"])
    console.print(table)


@models_app.command("reconcile")
def models_reconcile() -> None:
    """Check which roster entries resolve to a gateway model name."""
    try:
        reconciled = reconcile_models()
    except Exception as error:  # noqa: BLE001
        console.print(f"[red]gateway query failed: {error}[/red]")
        raise typer.Exit(code=1) from error
    table = Table(title="Roster -> gateway reconciliation")
    table.add_column("roster id")
    table.add_column("gateway model")
    for model_id, gateway_model in reconciled.items():
        if gateway_model:
            table.add_row(model_id, f"[green]{gateway_model}[/green]")
        else:
            table.add_row(model_id, "[red]MISSING[/red]")
    console.print(table)


@models_app.command("doctor")
def models_doctor(
    models: str = typer.Option("all", "--models", "-m", help="Comma list of roster ids or 'all'."),
    timeout: int = typer.Option(180, "--timeout", help="Per-probe timeout (s)."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Preflight roster models: served on the gateway + can do a tool call + valid JSON.

    Run this before any Harbor/benchmark run so a model that cannot serve (wrong
    context, no tool calling, empty turns) is caught up front instead of silently
    scoring 0.
    """
    try:
        rows = doctor_models(models, timeout=timeout)
    except SystemExit as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    if as_json:
        console.print_json(json.dumps(rows))
        return
    table = Table(title=f"Model doctor ({len(rows)})")
    for col in ("model", "served", "tool", "json", "latency_s", "note"):
        table.add_column(col)
    for r in rows:
        mark = lambda ok: "[green]ok[/green]" if ok else "[red]FAIL[/red]"  # noqa: E731
        table.add_row(r["model"], mark(r["served"]), mark(r["tool_ok"]),
                      mark(r["json_ok"]), str(r["latency_s"] or "-"), r["note"])
    console.print(table)
    failed = [r["model"] for r in rows if not (r["served"] and r["tool_ok"] and r["json_ok"])]
    if failed:
        console.print(f"[red]not ready:[/red] {', '.join(failed)}")
        raise typer.Exit(code=1)


@app.command()
def report(
    root: Path = typer.Option(report_mod.DEFAULT_HARBOR_RUNS, "--root", help="Harbor runs dir."),
    by: str = typer.Option("model", "--by", help="Comma group-by keys: model,condition,harness,task."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
    out: Optional[Path] = typer.Option(None, "--out", help="Write the markdown table here."),
) -> None:
    """Aggregate Harbor runs into a per-model reward + token report."""
    rows = report_mod.collect(Path(root))
    keys = tuple(k.strip() for k in by.split(",") if k.strip())
    if as_json:
        console.print_json(json.dumps(report_mod.summarize(rows, by=keys)))
        return
    markdown = report_mod.to_markdown(rows, by=keys)
    if out:
        Path(out).write_text(markdown + "\n")
        console.print(f"wrote {out}")
    console.print(markdown)


@mcp_app.command("doctor")
def mcp_doctor(
    timeout: int = typer.Option(20, "--timeout", help="Per-server timeout (s)."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Probe the MCP servers declared in mcp/manifest.yaml (mcp conditions)."""
    rows = mcp_mod.doctor_servers(timeout=timeout)
    if as_json:
        console.print_json(json.dumps(rows))
        return
    table = Table(title=f"MCP doctor ({len(rows)})")
    for col in ("server", "declared", "reachable", "http", "note"):
        table.add_column(col)
    for r in rows:
        mark = "[green]ok[/green]" if r["reachable"] else "[yellow]not reachable[/yellow]"
        table.add_row(r["server"], r["declared"], mark, str(r["http"] or "-"), r["note"])
    console.print(table)


@app.command("exec")
def exec_cmd(
    script: Path = typer.Argument(..., help="Python deliverable to execute."),
    timeout: float = typer.Option(60.0, help="Wall-clock budget (seconds)."),
    mem_mb: int = typer.Option(0, help="Memory budget in MB (0 = unlimited)."),
    cpu_s: int = typer.Option(0, help="CPU-time budget in seconds (0 = unlimited)."),
    profile: str = typer.Option("none", help="none | scalene | memray."),
    out: Optional[Path] = typer.Option(None, "--out", help="Profile output path."),
    as_json: bool = typer.Option(False, "--json", help="Emit the result as JSON."),
) -> None:
    """Run a deliverable under a hard budget; report ok/error/timeout/oom (+profile).

    This is the harness-side execution layer: it makes 'timeout' and 'oom' explicit
    outcomes instead of an ambiguous failure, and can profile the run for line-level
    time/memory (best used on an already-correct artifact).
    """
    from .harbor.runtime.executor import run_script
    from .harbor.runtime.profiler import ProfilerError

    try:
        res = run_script(
            script, timeout_s=timeout, mem_mb=mem_mb or None, cpu_s=cpu_s or None,
            profile=None if profile == "none" else profile, profile_out=out,
        )
    except ProfilerError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=2) from error

    if as_json:
        console.print_json(res.to_json())
    else:
        color = {"ok": "green", "error": "red", "timeout": "yellow", "oom": "magenta"}.get(res.status, "white")
        table = Table(title=f"{script.name} — [{color}]{res.status}[/{color}]")
        for col in ("status", "rc", "wall_s", "cpu_s", "peak_rss_mb", "profile"):
            table.add_column(col)
        table.add_row(res.status, str(res.returncode), f"{res.wall_s:.2f}",
                      f"{res.cpu_s:.2f}", f"{res.peak_rss_mb:.1f}",
                      res.profile["kind"] if res.profile else "-")
        console.print(table)
        if res.status in ("error", "oom") and res.stderr:
            console.print(res.stderr.strip().splitlines()[-1][:400])

    raise typer.Exit(code=0 if res.status == "ok" else 1)


@app.command("postmortem")
def postmortem(
    model: str = typer.Argument(..., help="Roster model id, e.g. tiel-coder-35b."),
    harness: str = typer.Option("pi", help="Harness whose runs to inspect."),
    run_start: Optional[str] = typer.Option(None, "--run-start", help="Run stamp (YYYYMMDD-HHMMSS); default latest."),
    out: Path = typer.Option(REPO_ROOT / "improvements", help="Improvements root."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the skill instead of writing it."),
) -> None:
    """Generate a per-model self-improvement skill from its failure postmortem."""
    from .postmortem import build_digest, render_skill, write_skill

    digest = build_digest(model, harness=harness, run_start=run_start)
    if dry_run:
        console.print(render_skill(digest))
        return
    path = write_skill(digest, out)
    console.print(
        f"[green]wrote[/green] {path}  "
        f"(timeouts={len(digest.timeouts)} wrong={len(digest.wrong)} solved={len(digest.solved)})"
    )


@app.command("trajectory")
def trajectory(
    task: str = typer.Option(..., "--task", "-t", help="Task id or unique prefix (e.g. a3)."),
    model: str = typer.Option(..., "--model", "-m", help="Roster model id."),
    harness: str = typer.Option("pi", "--harness", "-H", help="Harness name."),
    condition: Optional[str] = typer.Option(None, "--condition", "-c", help="Condition filter."),
    fmt: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Single-artifact passthrough: atif|result|reward|details|stdout|raw|session. "
             "Default: full bundle (metadata + trajectory)."),
    latest: bool = typer.Option(True, "--latest/--all", help="Newest trial, or every match."),
    list_only: bool = typer.Option(False, "--list", help="List matching trials."),
    validate: bool = typer.Option(False, "--validate", help="Validate the ATIF trajectory."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Write to a file."),
) -> None:
    """Dump a cell's trajectory + metadata (model params, task, environment).

    \b
      eab trajectory -t a3 -m tiel-coder-35b -H pi            > traj.json   (bundle)
      eab trajectory -t a3 -m tiel-coder-35b -H pi -f atif    > t.json      (ATIF only)
      eab trajectory -t a3 -m tiel-coder-35b -H pi --list                   (what exists)
    """
    from .trajectory import (
        artifact,
        build_bundle,
        exception_of,
        find_trials,
        read_artifact,
        resolve_task_id,
        reward_of,
    )

    try:
        task_id = resolve_task_id(task)
    except LookupError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    trials = find_trials(task_id, model, harness, condition)
    if not trials:
        where = f"{task_id} / {model} / {harness}" + (f" / {condition}" if condition else "")
        console.print(f"[red]no trials[/red] for {where}")
        raise typer.Exit(code=1)

    if validate:
        from .trajectory import validate_atif

        table = Table(title=f"ATIF validation — {task_id} · {model} · {harness}")
        for col in ("stamp", "condition", "valid", "errors"):
            table.add_column(col)
        for t in trials:
            traj = t.dir / "agent" / "trajectory.json"
            if not traj.exists():
                table.add_row(t.stamp, t.condition, "-", "no trajectory")
                continue
            ok, errors = validate_atif(traj)
            table.add_row(t.stamp, t.condition, "✓" if ok else "✗",
                          "; ".join(errors[:2]) or "-")
        console.print(table)
        return

    if list_only:
        table = Table(title=f"{task_id} · {model} · {harness}")
        for col in ("stamp", "condition", "reward", "exception", "path"):
            table.add_column(col)
        for t in trials:
            r = reward_of(t)
            table.add_row(t.stamp, t.condition, f"{r:.2f}" if r is not None else "-",
                          exception_of(t) or "-",
                          str(t.dir.relative_to(REPO_ROOT)))
        console.print(table)
        return

    chosen = [trials[-1]] if latest else trials
    records: list = []
    for t in chosen:
        if fmt:
            try:
                path = artifact(t, fmt, harness)
            except ValueError as error:
                console.print(f"[red]{error}[/red]")
                raise typer.Exit(code=2) from error
            if path is None:
                console.print(f"[yellow]missing '{fmt}' in {t.dir.name}[/yellow]", err=True)
                continue
            records.append({"stamp": t.stamp, "condition": t.condition, "trial": t.name,
                            "artifact": str(path.relative_to(REPO_ROOT)),
                            "data": read_artifact(path)})
        else:
            records.append(build_bundle(t, task_id, model, harness))

    if not records:
        raise typer.Exit(code=1)
    if latest:
        rec = records[0]
        data = rec["data"] if fmt else rec
    else:
        data = records

    text = data if isinstance(data, str) else json.dumps(data, indent=2, default=str)
    if out:
        Path(out).write_text(text if text.endswith("\n") else text + "\n")
        console.print(f"[green]wrote[/green] {out}")
    else:
        print(text)


@app.command("index")
def index(
    out: Optional[Path] = typer.Option(None, "--out", "-o",
                                       help="Output path (default runs/index.jsonl)."),
    fmt: str = typer.Option("jsonl", "--format", "-f", help="jsonl | csv | json."),
    runs_dir: Optional[Path] = typer.Option(None, "--runs-dir", help="Harbor runs tree."),
) -> None:
    """Build a rebuildable per-trial metadata index (JSONL by default) from runs/.

    \b
      eab index                 # -> runs/index.jsonl  (one object per trial)
      eab index -f csv          # -> runs/index.csv    (flattened, for spreadsheets)
      jq 'select(.condition=="improve")' runs/index.jsonl
    """
    from .index import index_records, load_sampling, write_index

    records = index_records(runs_dir)
    if out is None:
        out = REPO_ROOT / "runs" / ("index." + ("jsonl" if fmt == "jsonl" else fmt))
    write_index(records, out, fmt)
    by_status: dict[str, int] = {}
    for r in records:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    summary = " · ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    sampling = load_sampling()
    console.print(f"[green]wrote[/green] {out}  ({len(records)} trials · {summary})")
    if sampling:
        console.print(f"[dim]sampling defaults: {sampling} (from models.yaml)[/dim]")


@app.command("archive")
def archive(
    name: Optional[str] = typer.Option(None, "--name", "-n",
                                       help="Archive folder name (default run-<date>-incomplete)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would move."),
) -> None:
    """Archive the active run (the newest one) under runs/archive/<name>/.

    The run is auto-detected from the newest ``runs/eab-full-*.log``; no stamp
    needed. Moves its job dirs, log and manifest out of the active tree.

    \b
      eab archive --dry-run                 # preview
      eab archive                           # -> runs/archive/run-<date>-incomplete
      eab archive --name pilot-1
    """
    from .archive import archive_run, latest_stamp
    from .runconfig import load_manifest_names

    stamp = latest_stamp()
    if not stamp:
        console.print("[red]no active run found (no runs/eab-full-*.log)[/red]")
        raise typer.Exit(code=1)
    name = name or load_manifest_names().get(stamp) or f"run-{stamp.split('-')[0]}-incomplete"
    result = archive_run(name, stamp, dry_run=dry_run)
    verb = "would archive" if dry_run else "archived"
    console.print(f"[green]{verb}[/green] {len(result['moved'])} items for "
                  f"{stamp} -> {result['dest']}")


@app.command("analyze")
def analyze(
    name: str = typer.Option(..., "--name", "-n", help="Run name to analyze."),
    judge: str = typer.Option("glm-5.3-flash", "--judge", "-j", help="Judge model (roster id or gateway id)."),
    harness: Optional[str] = typer.Option(None, "--harness", "-H",
                                          help="Filter to one harness."),
    output: Path = typer.Option(Path("."), "--output", "-o", help="Output directory."),
    batch: int = typer.Option(1, "--batch", "-b",
                              help="Rows (model×harness×condition) per judge call; a rolling postmortem is kept across batches."),
    max_cells: int = typer.Option(0, "--max-cells",
                                  help="Cap trajectories per call (0 = all); lower for speed."),
    max_steps: int = typer.Option(80, "--max-steps", help="Steps per trajectory (80 ~ all)."),
    width: int = typer.Option(240, "--width", help="Per-line truncation width."),
    max_tokens: int = typer.Option(32000, "--max-tokens",
                                   help="Judge reply budget (reasoning models need a lot)."),
    timeout: int = typer.Option(1200, "--timeout", help="Per-call socket timeout (s)."),
    reasoning_effort: str = typer.Option("low", "--reasoning-effort",
                                         help="low|medium|high (low disables GLM thinking, ~7x faster); 'none' leaves the model default."),
    verify_pass: bool = typer.Option(False, "--verify",
                                     help="Final fact-check pass (reasoning on) against the evidence index."),
    verify_effort: str = typer.Option("medium", "--verify-effort",
                                      help="Reasoning effort for the --verify pass (high over-reasons on glm flash)."),
    fresh: bool = typer.Option(False, "--fresh",
                               help="Ignore cached batches; restart from batch 1."),
    no_progress: bool = typer.Option(False, "--no-progress", help="Silence the heartbeat."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Write payloads only, no judge call."),
) -> None:
    """Analyze a run with a judge model: rolling summary + postmortem + results table.

    \b
      eab analyze --name local-pi --judge glm-5.3-flash --batch 1 --output ./
      eab analyze --name local-pi --judge glm-5.3-flash --max-steps 60 --width 200
      eab analyze --name local-pi --verify           # + fact-check pass
      eab analyze --name local-pi                    # resumes from the last batch
      eab analyze --name local-pi --dry-run          # write payloads, no judge call

    Interrupted runs resume automatically: a completed batch is a non-empty
    batch-NN.summary.md, and the rolling draft continues from it. Use --fresh to
    ignore the cache.
    """
    from .analyze import analyze as run_analyze

    res = run_analyze(name, judge, harness=harness, output=output, batch=batch,
                      max_steps=max_steps, width=width, max_cells=max_cells,
                      max_tokens=max_tokens, timeout=timeout,
                      reasoning_effort=None if reasoning_effort == "none" else reasoning_effort,
                      dry_run=dry_run, progress=not no_progress, resume=not fresh,
                      verify_pass=verify_pass,
                      verify_effort=None if verify_effort == "none" else verify_effort)
    console.print(f"[green]{res['rows']} rows → {res['batches']} batch(es)[/green]  "
                  f"({res['cells']} cells, {res['elapsed']:.0f}s)")
    if res.get("resumed_from"):
        console.print(f"[dim]resumed from batch {res['resumed_from']}[/dim]")
    console.print(f"[dim]payloads + per-batch drafts:[/dim] {res['dir']}")
    if res["analysis"]:
        console.print(f"[green]analysis[/green] {res['analysis']}  (judge={judge})")
    if res.get("verified"):
        console.print(f"[green]verified[/green] {res['verified']}")


@app.command("dashboard")
def dashboard(
    interval: int = typer.Option(300, help="Refresh interval in seconds."),
) -> None:
    """Launch the live Textual dashboard (coding suite + earth-agent-bench runs)."""
    try:
        from .dashboard import main as dash_main
    except Exception as error:  # textual not installed
        console.print(
            f"[red]dashboard unavailable:[/red] {error}\n"
            "Install the UI extra:  [bold]pip install 'textual>=0.80'[/bold]"
        )
        raise typer.Exit(code=2) from error
    dash_main(interval=interval)


@app.command("doctor")
def doctor(
    check_logs: bool = typer.Option(True, "--check-logs/--no-check-logs",
                                    help="Also probe LiteLLM spend/log endpoints."),
) -> None:
    """Validate the environment contract to run EAB.

    Required: EARTHDATA_TOKEN, LITE_LLM_ENDPOINT, LITE_LLM_API_KEY. Also probes the
    gateway and, optionally, whether the key may read LiteLLM logs (needed for
    token observability) — some keys are inference-only and get 401/403 there.
    """
    import os
    import urllib.error
    import urllib.request

    from .wiring import gateway_base, llm_api_key_name, missing_credentials

    endpoint = gateway_base()
    key_name = llm_api_key_name()
    key = os.environ.get("LITE_LLM_API_KEY") or os.environ.get("LITELLM_API_KEY") or ""

    def probe(path: str) -> str:
        req = urllib.request.Request(
            f"{endpoint}{path}",
            headers={"Authorization": f"Bearer {key}",
                     "User-Agent": "earth-agent-bench/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return str(resp.status)
        except urllib.error.HTTPError as err:
            return f"{err.code}"
        except Exception as err:  # noqa: BLE001
            return f"error: {err}"

    earthdata = "set" if os.environ.get("EARTHDATA_TOKEN") else (
        "set (user/pass)" if os.environ.get("EARTHDATA_USERNAME") else "MISSING")
    rows = [
        ("EARTHDATA_TOKEN", earthdata),
        ("LITE_LLM_ENDPOINT", endpoint or "MISSING"),
        (f"LITE_LLM_API_KEY ({key_name})", "set" if key else "MISSING"),
        ("gateway /v1/models", probe("/v1/models")),
    ]
    log_row = None
    if check_logs:
        statuses = {p: probe(p) for p in ("/spend/logs", "/global/spend/logs")}
        ok = any(s == "200" for s in statuses.values())
        log_row = ("gateway spend/logs", "200 (readable)" if ok else
                   "not readable — " + ", ".join(f"{p}->{s}" for p, s in statuses.items()))

    table = Table(title="EAB doctor")
    table.add_column("check")
    table.add_column("result")
    for name, val in rows + ([log_row] if log_row else []):
        color = "green" if val in ("set", "200 (readable)", "set (user/pass)") else (
            "red" if val == "MISSING" else "yellow")
        table.add_row(name, f"[{color}]{val}[/{color}]")
    console.print(table)

    if log_row and "not readable" in log_row[1]:
        console.print(
            "[yellow]note:[/yellow] token/spend observability needs a LiteLLM key with "
            "log/admin scope; an inference-only key returns 401/403 above. Use an admin "
            "key or set a separate one for reporting."
        )
    missing = missing_credentials()
    if missing:
        console.print(f"[red]missing: {', '.join(missing)}[/red]")
        raise typer.Exit(code=1)


@app.command("config")
def config(
    as_shell: bool = typer.Option(False, "--shell", help="Emit shell var assignments (for scripts)."),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Run-config YAML (default experiments/run.yaml); a bare name resolves under experiments/."),
) -> None:
    """Show/validate the benchmark run config (run config + env + roster)."""
    from .runconfig import load_run_config, resolve_run_stamp, resolve_run_tasks

    try:
        c = load_run_config(config)
    except FileNotFoundError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    if c["unknown_models"]:
        console.print(f"[red]unknown model ids (not in experiments/models.yaml): "
                      f"{c['unknown_models']}[/red]")
        console.print(f"[dim]roster: {', '.join(c['roster'])}[/dim]")
        raise typer.Exit(code=1)
    if as_shell:
        print(f'EAB_RUN_NAME="{c["name"]}"')
        print(f'RUN_START="{resolve_run_stamp(c["name"])}"')
        print(f'MODELS="{" ".join(c["models"])}"')
        print(f'HARNESSES="{" ".join(c["harnesses"])}"')
        print(f'CONDITIONS="{" ".join(c["conditions"])}"')
        print(f'CONCURRENCY={c["concurrency"]}')
        return
    n_tasks = len(resolve_run_tasks(c["tasks"]))
    rows = len(c["models"]) * len(c["harnesses"]) * len(c["conditions"])
    cells = rows * n_tasks * c["trials"]
    table = Table(title=f"EAB run config ({c['config_path']}, env-overridable)")
    table.add_column("field")
    table.add_column("value")
    table.add_row("run", c["name"] + "  (the whole experiment)")
    table.add_row("models", ", ".join(c["models"]))
    table.add_row("harnesses", ", ".join(c["harnesses"]))
    table.add_row("conditions", ", ".join(c["conditions"]))
    table.add_row("tasks", f"{n_tasks}  ({c['tasks']})")
    table.add_row("trials", str(c["trials"]))
    table.add_row("concurrency", f"{c['concurrency']}"
                  + ("  (sequential — right for a single local GPU)" if c["concurrency"] <= 1
                     else "  (parallel — for gateway/API models)"))
    table.add_row("rows", f"{rows}  (model × harness × condition)")
    table.add_row("cells", f"{cells}  (row × task × trial)")
    console.print(table)
    console.print("[dim]run = the named experiment · row = one model×harness×condition "
                  "· cell = one row×task · trial = a repeat of a cell[/dim]")
    console.print("[dim]add models in experiments/models.yaml; select them in "
                  "experiments/run.yaml (or EAB_MODELS=…)[/dim]")


if __name__ == "__main__":
    app()
