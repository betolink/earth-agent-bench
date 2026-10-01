from dataclasses import dataclass


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    family: str
    tool_hints: tuple[str, ...] = ()


PATTERNS: dict[str, Pattern] = {
    p.id: p
    for p in [
        Pattern("C1", "Virtual Zarr via earthaccess virtualization", "cloud_native",
                ("earthaccess.virtualize", "earthaccess.open_virtual", "virtualizarr", "kerchunk")),
        Pattern("C2", "Native Zarr store", "cloud_native", ("zarr",)),
        Pattern("C3", "Cloud-Optimized GeoTIFF", "cloud_native", ("rioxarray", "rasterio")),
        Pattern("C4", "Parquet / Arrow", "cloud_native", ("pyarrow", "geopandas")),
        Pattern("C5", "Server-mediated cloud streaming", "cloud_native", ()),
        Pattern("S1", "Harmony subsetting", "subsetting", ("harmony-py", "harmony.client")),
        Pattern("S2", "OPeNDAP (Hyrax / Cloud)", "subsetting", ("pydap", "netCDF4", "xarray opendap")),
        Pattern("S3", "OPeNDAP-in-the-Cloud (DMR++)", "subsetting", ("pydap", "dmrpp")),
        Pattern("S4", "AppEEARS", "subsetting", ("appeears",)),
        Pattern("S5", "Giovanni", "subsetting", ("giovanni",)),
        Pattern("S6", "EDSC client-side subsetting", "subsetting", ()),
        Pattern("T1", "OPeNDAP streaming (DAP4)", "streaming", ("pydap dap4",)),
        Pattern("T2", "Zarr streaming", "streaming", ("xpublish", "zarrita")),
        Pattern("T3", "HTTP range streaming", "streaming", ("fsspec http", "aiohttp range")),
        Pattern("F1", "Spatial granule filtering", "filtered_download", ("earthaccess.search_data bbox",)),
        Pattern("F2", "Temporal granule filtering", "filtered_download", ("earthaccess.search_data temporal",)),
        Pattern("F3", "Variable-level download", "filtered_download", ()),
        Pattern("F4", "Quality-flag granule filtering", "filtered_download", ()),
        Pattern("M1", "Full granule download", "materialization", ("earthaccess.download", "wget")),
        Pattern("M2", "Full archive download", "materialization", ()),
    ]
}

CLOUD_NATIVE = [p for p in PATTERNS if p.startswith("C")]
SUBSETTING = [p for p in PATTERNS if p.startswith("S")]
STREAMING = [p for p in PATTERNS if p.startswith("T")]
FILTERED_DOWNLOAD = [p for p in PATTERNS if p.startswith("F")]
MATERIALIZATION = ["M1", "M2"]

SELECTION_LADDER = ["C1", "C2", "S3", "S2", "S1", "S4", "S5", "T1", "T2", "T3",
                    "F1", "F2", "F3", "F4", "M1"]


def validate_pattern(pattern_id: str) -> bool:
    return pattern_id in PATTERNS
