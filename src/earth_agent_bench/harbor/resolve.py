"""Resolve task references (paths, ids, sphere aliases, dirs, globs) to files."""

from __future__ import annotations

import glob
from pathlib import Path

from .config import BENCHMARK_TASKS_DIR, EVAL_TASKS_DIR

SPHERE_PREFIXES = {
    "atmo": "atmosphere", "a": "atmosphere",
    "cryo": "cryosphere", "c": "cryosphere",
    "bio": "biosphere", "b": "biosphere",
    "ocean": "ocean", "o": "ocean",
    "solid": "solid-earth", "se": "solid-earth", "s": "solid-earth",
    "land": "land-surface", "ls": "land-surface", "l": "land-surface",
}


def resolve_task(token: str) -> Path:
    """Resolve a single reference to a task file.

    Accepts a path to a ``.md``/``.yaml`` task, an eval task id, a benchmark id
    (``atmosphere/a1-...``), or a sphere alias (``cryo-1``).
    """
    token = token.strip()
    if not token:
        raise SystemExit("empty task token")
    if Path(token).is_file():
        return Path(token)

    if token.endswith(".md"):
        matches = list(EVAL_TASKS_DIR.rglob(Path(token).name))
        if len(matches) == 1:
            return matches[0]
        raise SystemExit(f"eval task '{token}' matched {len(matches)} files")

    if token.endswith(".yaml"):
        matches = list(BENCHMARK_TASKS_DIR.rglob(Path(token).name))
        if len(matches) == 1:
            return matches[0]
        raise SystemExit(f"task file '{token}' matched {len(matches)} files")

    eval_candidate = EVAL_TASKS_DIR / f"{token}.md"
    if eval_candidate.exists():
        return eval_candidate

    if "/" in token:
        target = BENCHMARK_TASKS_DIR / f"{token}.yaml"
        if target.exists():
            return target
        raise SystemExit(f"no task '{token}' under {BENCHMARK_TASKS_DIR}")

    sphere, _, code = token.rpartition("-")
    if sphere and sphere in SPHERE_PREFIXES:
        if not code.isdigit():
            raise SystemExit(f"task '{token}' needs a number, e.g. '{sphere}-1'")
        directory = SPHERE_PREFIXES[sphere]
        prefix = f"{directory[0]}{code}"
        matches = sorted((BENCHMARK_TASKS_DIR / directory).glob(f"{prefix}-*.yaml"))
        if len(matches) == 1:
            return matches[0]
        raise SystemExit(
            f"task '{token}' matched {len(matches)} files in {directory}: "
            f"{[m.name for m in matches]}"
        )

    exact = sorted(BENCHMARK_TASKS_DIR.rglob(f"{token}.yaml"))
    if len(exact) == 1:
        return exact[0]
    matches = sorted(BENCHMARK_TASKS_DIR.rglob(f"{token}-*.yaml"))
    if len(matches) == 1:
        return matches[0]
    candidates = sorted({m.parent.name for m in BENCHMARK_TASKS_DIR.rglob("*.yaml")})
    raise SystemExit(
        f"cannot resolve task '{token}'. Use a path, an eval id, 'cryo-1', "
        f"or a full benchmark id. Spheres: {candidates}"
    )


def _md(directory: Path) -> list[Path]:
    """Eval task files (``*.md``) under a directory, excluding ``README.md``."""
    return sorted(p for p in directory.rglob("*.md") if p.name.lower() != "readme.md")


def _yaml(directory: Path) -> list[Path]:
    """Grounded task files (``*.yaml``), excluding suite/manifest YAMLs."""
    return sorted(
        p for p in directory.rglob("*.yaml")
        if p.name.lower() not in {"suite.yaml", "dataset.yaml", "manifest.yaml"}
    )


def resolve_tasks(selection: str) -> list[Path]:
    """Expand a selection into task files.

    ``all`` -> the benchmark suite plus the eval suite; a directory or glob
    expands to the ``.yaml``/``.md`` tasks under it; otherwise a comma-separated
    list of references accepted by :func:`resolve_task`.
    """
    token = selection.strip()
    if token.lower() == "all":
        return [*_yaml(BENCHMARK_TASKS_DIR), *_md(EVAL_TASKS_DIR)]
    paths: list[Path] = []
    for part in token.split(","):
        part = part.strip()
        if not part:
            continue
        if any(char in part for char in "*?[") or Path(part).is_dir():
            matches = (
                [Path(m) for m in glob.glob(part, recursive=True)]
                if any(char in part for char in "*?[")
                else [Path(part)]
            )
            for match in matches:
                if match.is_dir():
                    paths.extend(_yaml(match))
                    paths.extend(_md(match))
                elif match.is_file():
                    paths.append(match)
        else:
            paths.append(resolve_task(part))

    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    if not ordered:
        raise SystemExit(f"no tasks matched '{selection}'")
    return ordered
