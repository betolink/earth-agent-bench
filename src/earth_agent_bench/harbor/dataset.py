"""Publish the generated task packages as a Harbor dataset.

A Harbor dataset is a ``dataset.toml`` manifest that pins each task package by
content digest, plus dataset-level files (the metric). Publishing it means any
Harbor install can ``harbor datasets download eab/earth-agent-bench`` and run
the suite without cloning this repo.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .config import DEFAULT_OUT, HARBOR_DIR
from .packages import generate_package

DATASET_NAME = "eab/earth-agent-bench"
DATASET_VERSION = "0.1.0"
METRIC_SOURCE = HARBOR_DIR / "metric.py"


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_dataset(
    task_paths: list[Path],
    *,
    condition: str = "baseline",
    out_root: Path = DEFAULT_OUT,
    dataset_path: Path = HARBOR_DIR / "dataset.toml",
) -> Path:
    """Generate packages, then write a digest-pinned dataset.toml and metric.py."""
    from harbor.models.dataset.manifest import (
        DatasetFileRef,
        DatasetInfo,
        DatasetManifest,
        DatasetTaskRef,
    )
    from harbor.publisher.packager import Packager

    packages = [generate_package(task, condition, out_root) for task in task_paths]

    tasks = []
    for package in packages:
        content_hash, _ = Packager.compute_content_hash(package)
        tasks.append(DatasetTaskRef(
            name=f"earth-agent-bench/{package.name}",
            digest=f"sha256:{content_hash}",
        ))

    metric = dataset_path.parent / "metric.py"
    if METRIC_SOURCE.exists() and METRIC_SOURCE.resolve() != metric.resolve():
        shutil.copy(METRIC_SOURCE, metric)
    files = [DatasetFileRef(path="metric.py", digest=_file_digest(metric))] if metric.exists() else []

    manifest = DatasetManifest(
        dataset=DatasetInfo(
            name=DATASET_NAME,
            version=DATASET_VERSION,
            description=(
                "NASA Earthdata access-pattern selection benchmark: did the agent "
                "choose and execute the best access route for a named collection?"
            ),
            authors=[{"name": "earth-agent-bench contributors"}],
            keywords=["earthdata", "geospatial", "access-pattern", "harbor"],
        ),
        tasks=tasks,
        files=files,
    )
    dataset_path.write_text(manifest.to_toml())
    return dataset_path
