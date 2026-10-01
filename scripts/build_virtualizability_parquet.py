"""Build benchmark/data/virtualizability.parquet from the EarthDataVirtualizabilityScore CSV.

Usage:
    uv run python scripts/build_virtualizability_parquet.py                 # fetch from GitHub
    uv run python scripts/build_virtualizability_parquet.py --csv local.csv # local copy
    uv run python scripts/build_virtualizability_parquet.py --empty         # schema-only parquet
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

import pandas as pd

EDVS_CSV_URL = (
    "https://raw.githubusercontent.com/alex-s-gardner/"
    "EarthDataVirtualizabilityScore/main/results/virtualizability.csv"
)

OUTPUT = Path(__file__).resolve().parents[1] / "benchmark" / "data" / "virtualizability.parquet"

COLUMNS = [
    "grade", "short_name", "sensor", "level", "format", "provider", "region",
    "consolidated_md", "grid_aligned", "chunk_aligned", "time_dim",
    "chunk_shape", "chunk_mb", "granules", "volume_tb", "dmrpp",
    "deciding_criterion",
]

ALIASES = {
    "grade": {"grade", "score", "virtualizabilityscore"},
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
    return "".join(ch for ch in str(column).strip().lower() if ch.isalnum() or ch == "_").strip("_")


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for column in df.columns:
        normalized = _norm(column)
        for canonical, aliases in ALIASES.items():
            if normalized in aliases:
                mapping[column] = canonical
                break
        else:
            mapping[column] = normalized
    df = df.rename(columns=mapping)
    missing = [c for c in ("grade", "short_name") if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV is missing required column(s): {missing}. Found: {list(df.columns)}")
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA
    return df[COLUMNS]


def build(csv_path: Path | None, empty: bool) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if empty:
        df = pd.DataFrame(columns=COLUMNS)
    else:
        if csv_path is None:
            print(f"Fetching {EDVS_CSV_URL}")
            with urllib.request.urlopen(EDVS_CSV_URL, timeout=60) as response:
                raw = response.read()
            df = pd.read_csv(pd.io.common.BytesIO(raw))
        else:
            df = pd.read_csv(csv_path)
        df = _map_columns(df)
    df.to_parquet(OUTPUT, index=False)
    print(f"Wrote {OUTPUT} ({len(df)} collections)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None, help="Local EDVS CSV path")
    parser.add_argument("--empty", action="store_true", help="Write schema-only parquet (offline)")
    args = parser.parse_args(argv)
    build(args.csv, args.empty)
    return 0


if __name__ == "__main__":
    sys.exit(main())
