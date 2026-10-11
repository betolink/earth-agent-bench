from __future__ import annotations

from typing import Iterable

SERVICE_ALIASES = {
    "virtual_zarr": {"c1", "virtual_zarr", "virtualizarr", "kerchunk", "earthaccess_virtualize", "earthaccess.open_virtual", "earthaccess.write_virtual", "virtualization"},
    "native_zarr": {"c2", "native_zarr", "zarr"},
    "cog": {"c3", "cog", "geotiff"},
    "harmony": {"s1", "harmony", "harmony-py", "harmony_py"},
    "opendap": {"s2", "opendap", "hyrax", "pydap", "dap2", "dap4"},
    "opendap_cloud": {"s3", "dmrpp", "dmr++", "opendap_cloud"},
    "appeears": {"s4", "appeears"},
    "giovanni": {"s5", "giovanni"},
    "filtered_download": {"f1", "f2", "f3", "f4", "filtered_download", "granule_filtering"},
    "full_download": {"m1", "m2", "full_download", "materialization"},
}


def _canonical(name: str) -> str | None:
    """Canonicalise a service name for matching."""
    token = name.strip().lower()
    for canonical, aliases in SERVICE_ALIASES.items():
        if token in aliases:
            return canonical
    return None


def score_service_discovery(discovered: Iterable[str], available: Iterable[str]) -> float:
    """Score discovered services against the gold set."""
    discovered_canonical = {_canonical(d) for d in discovered if _canonical(d)}
    available_canonical = {_canonical(a) for a in available if _canonical(a)}
    if not available_canonical:
        return 0.0
    return len(discovered_canonical & available_canonical) / len(available_canonical)
