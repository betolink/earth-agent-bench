# /// script
# dependencies = []
# ///
"""Harbor dataset metric: report the all-or-nothing `pass` headline.

Benchmark tasks write several numeric keys to reward.json (pass, score, and the
per-component scores). Harbor's default metric expects exactly one key, so this
dataset-level metric selects `pass` (and falls back to `reward`) instead.
"""

import argparse
import json
from pathlib import Path


def _reward(entry) -> float:
    if entry is None:
        return 0.0
    if not isinstance(entry, dict):
        return float(entry)
    for key in ("pass", "reward"):
        if key in entry:
            return float(entry[key])
    return 0.0


def main(input_path: Path, output_path: Path) -> None:
    values = [
        _reward(json.loads(line))
        for line in input_path.read_text().splitlines()
        if line.strip()
    ]
    mean = sum(values) / len(values) if values else 0.0
    output_path.write_text(json.dumps({"mean": mean}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-path", type=Path, required=True)
    parser.add_argument("-o", "--output-path", type=Path, required=True)
    args = parser.parse_args()
    main(args.input_path, args.output_path)
