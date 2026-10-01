from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .oracles.cmr import fetch_services
from .oracles.service_matrix import build_matrix
from .oracles.services import ServiceCatalog
from .oracles.virtualizability import VirtualizabilityOracle
from .scoring import score_run
from .schemas import RunObservation
from .tasks import DEFAULT_TASKS_DIR, load_all, load_task, render_instruction

app = typer.Typer(help="earth-agent-bench: access-pattern selection benchmark tooling")
harbor_app = typer.Typer(help="Generate Harbor task packages and run them")
app.add_typer(harbor_app, name="harbor")
console = Console()

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARQUET = REPO_ROOT / "benchmark" / "data" / "virtualizability.parquet"
DEFAULT_SERVICES = REPO_ROOT / "benchmark" / "oracles" / "services.yaml"


def _oracle(parquet: Path) -> VirtualizabilityOracle:
    try:
        return VirtualizabilityOracle(parquet)
    except FileNotFoundError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1)


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
    task: Path = typer.Argument(..., help="Path to a task YAML file"),
    model: str = typer.Option(..., help="Model id from experiments/models.yaml"),
    harness: str = typer.Option(..., help="opencode | codex | claude-code | pi"),
    condition: str = typer.Option("baseline", help="baseline | mcp | skills | mcp-skills"),
    trial: int = typer.Option(1),
    runs_root: Path = typer.Option(REPO_ROOT / "runs", help="Where run workspaces live"),
    dry_run: bool = typer.Option(False, help="Print workspace/env/command only"),
) -> None:
    """Direct single-run trial (no Harbor). Builds a workspace and launches the harness."""
    from .runner import RunSpec, execute

    spec = RunSpec(
        task_path=task, model_id=model, harness=harness,
        condition=condition, trial=trial, runs_root=runs_root,
    )
    raise typer.Exit(code=execute(spec, dry_run=dry_run))


@harbor_app.command("generate")
def harbor_generate(
    tasks: str = typer.Argument("all", help="Task ids: cryo-1,atmo-2 | all | pilot"),
    condition: str = typer.Option("baseline", help="baseline | mcp | skills | mcp-skills"),
    out: Path = typer.Option(REPO_ROOT / "harbor" / "generated"),
) -> None:
    """Generate Harbor task packages from benchmark tasks."""
    from .harbor_adapter import generate_package, resolve_tasks

    for task_path in resolve_tasks(tasks):
        package = generate_package(task_path, condition, out)
        console.print(f"[green]generated[/green] {package}")


@harbor_app.command("run")
def harbor_run(
    tasks: str = typer.Argument(..., help="Task ids: cryo-1,atmo-2 | pilot"),
    model: str = typer.Option(..., help="Model id from experiments/models.yaml"),
    harness: str = typer.Option(..., help="opencode | codex | claude-code | pi"),
    condition: str = typer.Option("baseline"),
    out: Path = typer.Option(REPO_ROOT / "harbor" / "generated"),
    dry_run: bool = typer.Option(False, help="Print the harbor command only"),
) -> None:
    """Generate packages, then invoke the harbor CLI for each task."""
    from .harbor_adapter import resolve_tasks, run_harbor

    code = 0
    for task_path in resolve_tasks(tasks):
        code = run_harbor(task_path, model, harness, condition, out, dry_run) or code
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
    for task in load_all(tasks_dir):
        if task.task_id == task_id:
            return task
    console.print(f"[red]Task '{task_id}' not found under {tasks_dir}[/red]")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
