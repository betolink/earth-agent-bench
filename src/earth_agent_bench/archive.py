"""Archive a run's artifacts out of the active tree.

A run is identified by its stamp (``YYYYMMDD-HHMMSS``). Archiving moves its
Harbor job directories (and any run log/manifest) into
``runs/archive/<name>/`` so the index/report only show active runs::

    eab archive --name run-20261011-incomplete --stamp 20261011-005413

The move is reversible (everything lands under ``runs/archive/<name>/``).
"""

from __future__ import annotations

import glob
import re
import shutil
from pathlib import Path

from . import trajectory as tj
from .runs import parse_job_dir

REPO_ROOT = tj.REPO_ROOT
RUNS = REPO_ROOT / "runs"
ARCHIVE = RUNS / "archive"
_STAMP = re.compile(r"-(\d{8}-\d{6})$")


def latest_stamp() -> str:
    """Stamp of the newest Harbor job directory, or ''."""
    stamps = []
    for path in glob.glob(str(RUNS / "harbor" / "eab-*")):
        ref = parse_job_dir(Path(path).name)
        if ref.stamp:
            stamps.append(ref.stamp)
    return max(stamps) if stamps else ""


def _job_dirs_since(stamp: str) -> list[str]:
    """Harbor job dirs whose per-job stamp is >= ``stamp`` (the run start)."""
    out = []
    for path in glob.glob(str(RUNS / "harbor" / "eab-*")):
        ref = parse_job_dir(Path(path).name)
        if ref.stamp and ref.stamp >= stamp:
            out.append(path)
    return sorted(out)


def archive_run(name: str, stamp: str, dry_run: bool = False) -> dict:
    """Move a run's job dirs, log and manifest under ``runs/archive/<name>/``.

    Returns a summary ``{"name", "stamp", "dest", "moved": [paths]}``.
    """
    if not name or "/" in name:
        raise ValueError("archive name must be a non-empty path segment")
    dest = ARCHIVE / name
    moved: list[Path] = []

    def take(paths, subdir: str):
        for src in paths:
            target = dest / subdir / Path(src).name
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(target))
            moved.append(target)

    take(_job_dirs_since(stamp), "harbor")
    take(sorted(glob.glob(str(RUNS / f"eab-full-{stamp}.log"))), "logs")
    take(sorted(glob.glob(str(RUNS / "manifests" / f"*-{stamp}.json"))), "manifests")
    return {"name": name, "stamp": stamp, "dest": dest, "moved": moved}
