#!/usr/bin/env python3
"""Verify each task collection against CMR (level, DOI, summary, services).

For every collection in ``benchmark/tasks/access-pattern/**/*.yaml`` resolve its concept_id and
pull the UMM-C record, then report:

  * processing level (``ProcessingLevel.Id``) — prefer L4 unless natively L2
  * ``cloud_hosted`` + ``has_transforms`` (Harmony)
  * access services inferred from RelatedUrls (S1 Harmony / S2 OPeNDAP /
    S3 DMR++ / S4 AppEEARS / S5 Giovanni / direct S3)
  * DOI and a summary snippet, to confirm the dataset matches the task intent

Usage::

    python scripts/verify_collections.py            # table
    python scripts/verify_collections.py --json out.json
"""
from __future__ import annotations

import argparse
import glob
import json
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
from earth_agent_bench.tasks import load_task  # noqa: E402

TASKS = EAB / "benchmark" / "tasks" / "access-pattern"


def resolve(short_name: str) -> dict | None:
    """Return the cloud-hosted (else first) CMR entry for a short name."""
    try:
        entries = find_collections(short_name)
    except Exception as error:
        print(f"  ! {short_name}: {error}", file=sys.stderr)
        return None
    cloud = [e for e in entries if e.get("cloud_hosted")]
    return (cloud or entries)[0] if entries else None


def umm(concept_id: str) -> dict:
    """Fetch the UMM-C JSON for a concept id ({} on failure)."""
    try:
        return json.loads(_cmr_get(f"{CMR_BASE}/concepts/{concept_id}",
                                   "application/vnd.nasa.cmr.umm+json"))
    except Exception as error:
        print(f"  ! umm {concept_id}: {error}", file=sys.stderr)
        return {}


def info(short_name: str) -> dict:
    """Resolve + summarise one collection: level, doi, services, summary."""
    entry = resolve(short_name)
    if not entry:
        return {"short_name": short_name, "concept_id": None}
    cid = entry["id"]
    doc = umm(cid)
    services = sorted(services_from_related_urls(doc).keys())
    if entry.get("has_transforms") and "S1" not in services:
        services.insert(0, "S1")
    doi = (doc.get("DOI") or {}).get("DOI") or ""
    return {
        "short_name": entry.get("short_name", short_name),
        "concept_id": cid,
        "level": (doc.get("ProcessingLevel") or {}).get("Id", "?"),
        "cloud": bool(entry.get("cloud_hosted")),
        "harmony": bool(entry.get("has_transforms")),
        "services": services,
        "doi": doi,
        "summary": " ".join((doc.get("Summary") or "").split())[:160],
    }


def main() -> int:
    """Print a per-collection verification table (and optionally JSON)."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="write the full report as JSON")
    args = ap.parse_args()

    report = []
    for path in sorted(glob.glob(str(TASKS / "*" / "*.yaml"))):
        task = load_task(path)
        print(f"\n### {task.task_id.split('/')[-1]}")
        for c in task.collections:
            r = info(c.short_name)
            r["tier"] = c.tier
            r["task"] = task.task_id
            report.append(r)
            svc = ",".join(r.get("services") or []) or "-"
            print(f"  [{r['tier']:11s}] {c.short_name[:38]:38s} "
                  f"lvl={r.get('level','?'):3s} cloud={int(bool(r.get('cloud')))} "
                  f"svc={svc}")
            if r.get("doi"):
                print(f"        doi: {r['doi']}")
            if r.get("summary"):
                print(f"        {r['summary']}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
