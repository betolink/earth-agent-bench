"""Combined per-collection service availability matrix and selection ladder."""

from __future__ import annotations

from typing import Optional

from ..patterns import SELECTION_LADDER
from .services import ServiceCatalog
from .virtualizability import VirtualizabilityOracle, VirtualizabilityRecord

VIRTUALIZABLE_GRADES = {"A", "B"}


def build_matrix(
    short_name: str,
    virt: VirtualizabilityOracle,
    catalog: Optional[ServiceCatalog] = None,
    live_cmr_patterns: Optional[dict[str, dict]] = None,
) -> dict:
    record: Optional[VirtualizabilityRecord] = virt.get(short_name)
    matrix: dict[str, dict] = {}

    if record is None:
        matrix["C1"] = {
            "available": False,
            "source": "edvs-parquet",
            "reason": "not sampled in EDVS; C1 not creditable without manual verification",
        }
    else:
        matrix["C1"] = {
            "available": record.virtualizable,
            "source": "edvs-parquet",
            "grade": record.grade,
            "deciding_criterion": record.deciding_criterion,
            "reason": None if record.virtualizable else record.deciding_criterion,
        }
        if record.dmrpp:
            matrix.setdefault("S3", {
                "available": True,
                "source": "edvs-parquet:dmrpp",
            })

    if catalog is not None:
        for pattern_id, info in catalog.pattern_availability(short_name).items():
            existing = matrix.get(pattern_id)
            if existing is None or not existing.get("source", "").startswith("edvs"):
                matrix[pattern_id] = info

    if live_cmr_patterns:
        for pattern_id, info in live_cmr_patterns.items():
            info = dict(info)
            info["verified"] = True
            matrix[pattern_id] = info

    if catalog is not None and catalog.verified(short_name):
        for pattern_id in matrix:
            if pattern_id != "C1":
                matrix[pattern_id].setdefault("verified", True)

    recommended = [
        pattern_id
        for pattern_id in SELECTION_LADDER
        if matrix.get(pattern_id, {}).get("available")
    ]
    return {
        "short_name": short_name,
        "virtualization_outlook": virt.virtualization_outlook(short_name),
        "patterns": matrix,
        "recommended_patterns": recommended,
        "best_pattern": recommended[0] if recommended else None,
    }


class ServiceAvailabilityMatrix:
    def __init__(self, virt: VirtualizabilityOracle, catalog: Optional[ServiceCatalog] = None):
        self.virt = virt
        self.catalog = catalog
        self._live_cache: dict[str, dict] = {}

    def add_live(self, short_name: str, patterns: dict[str, dict]) -> None:
        self._live_cache[short_name.upper()] = patterns

    def get_matrix(self, short_name: str) -> dict:
        return build_matrix(
            short_name,
            self.virt,
            self.catalog,
            self._live_cache.get(short_name.upper()),
        )

    def best_pattern(self, short_name: str) -> Optional[str]:
        return self.get_matrix(short_name)["best_pattern"]
