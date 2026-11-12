#!/usr/bin/env python3
"""Re-derive each task's access-pattern tiers from verified availability.

Policy (best -> worst): data virtualization -> Harmony -> OPeNDAP -> HTTP
subsetting/aggregation -> full download. AppEEARS/Giovanni are not "good".

Signals:
  * virtualization (C1)  <- EarthDataVirtualizabilityScore grade A/B
  * Harmony (S1)         <- CMR ``has_transforms``
  * OPeNDAP (S2)/DMR++ (S3) <- CMR UMM-C RelatedUrls
  * F*/M*                <- always possible (HTTPS filtered / full download)

Usage::

    python scripts/rederive_patterns.py            # dry run (table)
    python scripts/rederive_patterns.py --write     # edit pattern_tiers + gold
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

EAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EAB / "src"))

from earth_agent_bench.oracles.cmr import (  # noqa: E402
    CMR_BASE,
    _cmr_get,
    find_collections,
    services_from_related_urls,
)
from earth_agent_bench.oracles.virtualizability import VirtualizabilityOracle  # noqa: E402
from earth_agent_bench.tasks import load_task  # noqa: E402

TASKS = EAB / "benchmark" / "tasks" / "access-pattern"
ORACLE = VirtualizabilityOracle(EAB / "benchmark" / "data" / "virtualizability.parquet")


def availability(short_name: str) -> dict:
    """Return the available-pattern signals for one collection."""
    signals = {"C1": False, "S1": False, "S2": False, "S3": False, "S4": False}
    if ORACLE.virtualizable(short_name):
        signals["C1"] = True
    try:
        entries = find_collections(short_name)
    except Exception:
        entries = []
    if any(e.get("has_transforms") for e in entries):
        signals["S1"] = True
    if entries:
        cloud = [e for e in entries if e.get("cloud_hosted")]
        cid = (cloud or entries)[0]["id"]
        try:
            doc = _cmr_get(f"{CMR_BASE}/concepts/{cid}", "application/vnd.nasa.cmr.umm+json")
            import json
            svc = services_from_related_urls(json.loads(doc))
            for p in ("S2", "S3", "S4"):
                signals[p] = signals[p] or p in svc
        except Exception:
            pass
    return signals


def tiers_for(avail: dict) -> dict:
    """Map availability to pattern_tiers per the policy."""
    if avail["C1"]:
        return {"best": ["C1"], "acceptable": ["S1", "S3", "S2"],
                "marginal": ["F1", "F2"], "inefficient": ["M1", "M2"]}
    if avail["S1"]:
        return {"best": ["S1"], "acceptable": ["S3", "S2"],
                "marginal": ["F1", "F2"], "inefficient": ["M1", "M2"]}
    if avail["S3"] or avail["S2"]:
        best = ["S3", "S2"] if avail["S3"] else ["S2"]
        return {"best": best, "acceptable": ["F1", "F2"],
                "marginal": ["T3"], "inefficient": ["M1", "M2"]}
    return {"best": ["F1", "F2"], "acceptable": ["F3", "F4"],
            "marginal": ["T3"], "inefficient": ["M1", "M2"]}


def _replace_block(text: str, key: str, block: str) -> str:
    """Replace a top-level ``key:`` block (until the next top-level key)."""
    pattern = re.compile(rf"^{key}:.*?(?=^\S|\Z)", re.MULTILINE | re.DOTALL)
    return pattern.sub(block + "\n", text, count=1)


def render(tiers: dict, reason: str) -> tuple[str, str]:
    """Render the pattern_tiers and gold YAML blocks."""
    pt = ["pattern_tiers:"]
    for tier in ("best", "acceptable", "marginal", "inefficient"):
        pt.append(f"  {tier}: [{', '.join(tiers[tier])}]")
    gold = ["gold:", f"  primary_patterns: [{', '.join(tiers['best'])}]",
            f"  acceptable_patterns: [{', '.join(tiers['acceptable'])}]",
            "  reasoning: >", f"    {reason}"]
    return "\n".join(pt), "\n".join(gold)


def main() -> int:
    """Re-derive and (with --write) update each task's tiers + gold."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    for path in sorted(glob.glob(str(TASKS / "*" / "*.yaml"))):
        task = load_task(path)
        pref = [c for c in task.collections if c.tier == "preferred"]
        merged = {"C1": False, "S1": False, "S2": False, "S3": False, "S4": False}
        for c in pref:
            a = availability(c.short_name)
            for k in merged:
                merged[k] = merged[k] or a[k]
        tiers = tiers_for(merged)
        reason = ("Verified availability — "
                  + ", ".join(f"{k}={'y' if v else 'n'}" for k, v in merged.items())
                  + ". Preference: virtualization > Harmony > OPeNDAP > "
                  + "HTTP-subset > download; AppEEARS/Giovanni excluded.")
        print(f"{task.task_id.split('/')[-1][:32]:32s} best={tiers['best']} "
              f"acc={tiers['acceptable']}  [{reason.split(':')[1].strip()}]")
        if args.write:
            pt, gold = render(tiers, reason)
            text = Path(path).read_text()
            text = _replace_block(text, "pattern_tiers", pt)
            text = _replace_block(text, "gold", gold)
            Path(path).write_text(text)
    print(f"\n{'wrote' if args.write else 'dry run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
