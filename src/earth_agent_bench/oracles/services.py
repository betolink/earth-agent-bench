"""Curated service availability catalog (DAAC docs / manual curation).

YAML format (benchmark/oracles/services.yaml):

    collections:
      TEMPO_NO2_L3:
        verified: false
        services:
          harmony: {available: true, source: "curated; verify via CMR"}
          opendap: {available: false, reason: "no Hyrax endpoint"}

Service keys map to pattern ids via SERVICE_TO_PATTERN. The virtualizability
parquet (EDVS) is authoritative for C1 and DMR++ (S3); this catalog covers the
rest and records verification state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

SERVICE_TO_PATTERN = {
    "harmony": "S1",
    "opendap": "S2",
    "dmrpp": "S3",
    "appeears": "S4",
    "giovanni": "S5",
    "native_zarr": "C2",
    "cog": "C3",
    "direct_s3": "C5",
}


class ServiceCatalog:
    """Catalog of known Earthdata access services and patterns."""
    def __init__(self, yaml_path: str | Path):
        self.path = Path(yaml_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Service catalog not found at {self.path}")
        with self.path.open() as f:
            data = yaml.safe_load(f) or {}
        self._collections = {
            short_name.upper(): entry
            for short_name, entry in (data.get("collections") or {}).items()
        }

    def entry(self, short_name: str) -> Optional[dict]:
        return self._collections.get(short_name.strip().upper())

    def verified(self, short_name: str) -> bool:
        entry = self.entry(short_name)
        return bool(entry and entry.get("verified"))

    def services(self, short_name: str) -> dict[str, dict]:
        entry = self.entry(short_name)
        if not entry:
            return {}
        return dict(entry.get("services") or {})

    def pattern_availability(self, short_name: str) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for key, info in self.services(short_name).items():
            pattern = SERVICE_TO_PATTERN.get(key)
            if pattern is None:
                continue
            info = dict(info or {})
            info.setdefault("available", True)
            info.setdefault("source", f"catalog:{self.path.name}")
            result[pattern] = info
        return result

    def collections(self) -> list[str]:
        return sorted(self._collections)
