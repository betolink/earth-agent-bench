"""Parquet-backed EarthDataVirtualizabilityScore oracle.

Source data: https://github.com/alex-s-gardner/EarthDataVirtualizabilityScore
Built locally by scripts/build_virtualizability_parquet.py into
benchmark/data/virtualizability.parquet.

Grade semantics for this benchmark:
    A        -> C1 (earthaccess virtualization) available, top priority
    B        -> C1 available (blockers are repairable at store-build time)
    C / D    -> C1 unavailable; deciding_criterion names the blocker
    missing  -> C1 not creditable (unknown)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

VIRTUALIZABLE_GRADES = {"A", "B"}

_COLUMN_ALIASES: dict[str, set[str]] = {
    "grade": {"grade", "score", "virtualizability_score", "virtualizabilityscore"},
    "short_name": {"short_name", "shortname", "product", "collection", "collection_id", "dataset"},
    "sensor": {"sensor"},
    "level": {"level"},
    "format": {"format"},
    "provider": {"daac", "provider"},
    "region": {"region", "s3_region"},
    "consolidated_md": {"consolidated_md", "consolidatedmetadata", "consolidated_md_available"},
    "grid_aligned": {"grid_aligned", "gridaligned"},
    "chunk_aligned": {"chunk_aligned", "chunkaligned"},
    "time_dim": {"time_dim", "timedim", "time_dimension"},
    "chunk_shape": {"chunk_shape", "chunkshape"},
    "chunk_mb": {"chunk_mb", "chunkmb", "chunk_size_mb"},
    "granules": {"granules", "granule_count", "n_granules"},
    "volume_tb": {"volume_tb", "volume", "volume_tb_total"},
    "dmrpp": {"dmrpp", "dmrpp_available", "dmrpp_cols", "dmrpp_available_cols"},
    "deciding_criterion": {"deciding_criterion", "decidingcriterion", "blocker", "evidence"},
}


def _norm(column: str) -> str:
    """Normalise a string for matching."""
    return "".join(ch for ch in column.strip().lower() if ch.isalnum() or ch == "_").strip("_")


def normalize_grade(raw) -> Optional[str]:
    """Map a raw grade label to the canonical grade."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip().upper()
    for letter in ("A", "B", "C", "D", "E", "F"):
        if text.startswith(letter):
            return letter
    return text or None


def _as_bool(raw) -> Optional[bool]:
    """Coerce a value to bool."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in {"yes", "y", "true", "1"}:
        return True
    if text in {"no", "n", "false", "0"}:
        return False
    return None


@dataclass(frozen=True)
class VirtualizabilityRecord:
    """One collection's virtualizability verdict."""
    short_name: str
    grade: Optional[str]
    sensor: Optional[str] = None
    level: Optional[str] = None
    format: Optional[str] = None
    provider: Optional[str] = None
    region: Optional[str] = None
    consolidated_md: Optional[bool] = None
    grid_aligned: Optional[bool] = None
    chunk_aligned: Optional[bool] = None
    time_dim: Optional[bool] = None
    chunk_shape: Optional[str] = None
    chunk_mb: Optional[float] = None
    granules: Optional[int] = None
    volume_tb: Optional[float] = None
    dmrpp: Optional[bool] = None
    deciding_criterion: Optional[str] = None

    @property
    def virtualizable(self) -> bool:
        return self.grade in VIRTUALIZABLE_GRADES

    @property
    def in_oracle(self) -> bool:
        return self.grade is not None


class VirtualizabilityOracle:
    """Lookup interface over the virtualizability parquet."""
    def __init__(self, parquet_path: str | Path):
        self.path = Path(parquet_path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"Virtualizability parquet not found at {self.path}. "
                "Run `uv run python scripts/build_virtualizability_parquet.py` first."
            )
        self._df = pd.read_parquet(self.path)
        self._df.columns = [self._resolve_column(c) for c in self._df.columns]
        self._index = {
            str(row.get("short_name") or "").strip().upper(): row
            for _, row in self._df.iterrows()
        }

    def _resolve_column(self, column: str) -> str:
        normalized = _norm(column)
        for canonical, aliases in _COLUMN_ALIASES.items():
            if normalized in aliases:
                return canonical
        return normalized

    def _lookup(self, short_name: str):
        return self._index.get(short_name.strip().upper())

    def get(self, short_name: str) -> Optional[VirtualizabilityRecord]:
        row = self._lookup(short_name)
        if row is None:
            return None

        def opt(key, cast=str):
            value = row.get(key)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            if value == "nan" or value == "":
                return None
            try:
                return cast(value)
            except (TypeError, ValueError):
                return None

        return VirtualizabilityRecord(
            short_name=str(row.get("short_name") or short_name),
            grade=normalize_grade(row.get("grade")),
            sensor=opt("sensor"),
            level=opt("level"),
            format=opt("format"),
            provider=opt("provider"),
            region=opt("region"),
            consolidated_md=opt("consolidated_md", _as_bool),
            grid_aligned=opt("grid_aligned", _as_bool),
            chunk_aligned=opt("chunk_aligned", _as_bool),
            time_dim=opt("time_dim", _as_bool),
            chunk_shape=opt("chunk_shape"),
            chunk_mb=opt("chunk_mb", float),
            granules=opt("granules", int),
            volume_tb=opt("volume_tb", float),
            dmrpp=opt("dmrpp", _as_bool),
            deciding_criterion=opt("deciding_criterion"),
        )

    def grade(self, short_name: str) -> Optional[str]:
        record = self.get(short_name)
        return record.grade if record else None

    def virtualizable(self, short_name: str) -> bool:
        record = self.get(short_name)
        return bool(record and record.virtualizable)

    def criterion(self, short_name: str) -> Optional[str]:
        record = self.get(short_name)
        return record.deciding_criterion if record else None

    def dmrpp(self, short_name: str) -> bool:
        record = self.get(short_name)
        return bool(record and record.dmrpp)

    def virtualization_outlook(self, short_name: str) -> dict:
        record = self.get(short_name)
        if record is None:
            return {
                "short_name": short_name,
                "in_oracle": False,
                "grade": None,
                "c1_available": False,
                "deciding_criterion": None,
                "note": "not sampled in EDVS; C1 not creditable without manual verification",
            }
        return {
            "short_name": record.short_name,
            "in_oracle": True,
            "grade": record.grade,
            "c1_available": record.virtualizable,
            "deciding_criterion": record.deciding_criterion,
            "note": (
                "virtualization achievable (grade A/B)"
                if record.virtualizable
                else "virtualization blocked by the recorded criterion"
            ),
        }

    def collections(self) -> list[str]:
        return sorted(self._index.keys())
