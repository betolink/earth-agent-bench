"""Grade the single clean value the agent wrote to output/answer.txt.

Deterministic and LLM-free: the gold and its type come from tests/gold.json and
are compared with earth_agent_bench.evals.grade. Writes Harbor's reward files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from earth_agent_bench.evals import EvalGold, grade
from earth_agent_bench.harbor_verify import find, roots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="/app")
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--gold", default=str(HERE / "gold.json"))
    parser.add_argument("--logs", default="/logs/verifier")
    args = parser.parse_args()

    gold = EvalGold.model_validate(json.loads(Path(args.gold).read_text()))
    answer = find(roots(args.workspace, args.search_root), "output/answer.txt")
    produced = answer.read_text().strip() if answer else None
    result = grade(gold, produced)

    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.json").write_text(json.dumps({"reward": result.reward}))
    (logs / "reward.txt").write_text(f"{result.reward}\n")
    (logs / "details.json").write_text(json.dumps(result.model_dump(), indent=2))

    print(json.dumps(result.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
