"""Best-effort live CMR service discovery.

Signals used:
  - collections feed entry `has_transforms` -> S1 (Harmony-enabled)
  - UMM-C RelatedUrls:
      harmony.earthdata.nasa.gov        -> S1
      opendap with dmrpp                -> S3
      opendap                           -> S2
      appeears                          -> S4
      giovanni                          -> S5
      s3:// (GET DATA VIA DIRECT ACCESS)-> direct S3 note
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Optional

CMR_BASE = "https://cmr.earthdata.nasa.gov/search"

_URL_RULES: list[tuple[str, str]] = [
    (r"harmony\.earthdata\.nasa\.gov", "S1"),
    (r"opendap.*dmrpp|dmrpp", "S3"),
    (r"opendap", "S2"),
    (r"appeears", "S4"),
    (r"giovanni", "S5"),
]


def _cmr_get(url: str, accept: str, timeout: float = 30.0) -> bytes:
    """GET a CMR URL with the EDL token, returning parsed JSON."""
    request = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def find_collections(short_name: str, timeout: float = 30.0) -> list[dict]:
    """Search CMR collections by free text; return hits."""
    url = f"{CMR_BASE}/collections?" + urllib.parse.urlencode({"short_name": short_name})
    payload = json.loads(_cmr_get(url, "application/json", timeout=timeout))
    return (payload.get("feed") or {}).get("entry") or []


_SERVICE_SUBTYPES = {"APPEEARS", "GIOVANNI", "OPENDAP", "HARMONY", "ESI", "SUBSETTER"}


def services_from_related_urls(umm_c: dict) -> dict[str, dict]:
    """Infer access services from a collection's related URLs."""
    found: dict[str, dict] = {}
    for url_entry in umm_c.get("RelatedUrls", []):
        url = url_entry.get("URL", "")
        url_type = url_entry.get("Type", "")
        subtype = url_entry.get("Subtype", "")
        description = url_entry.get("Description", "")
        if url_type == "GET DATA VIA DIRECT ACCESS" and url.startswith("s3://"):
            found.setdefault(
                "direct_s3",
                {"available": True, "endpoint": url, "source": "cmr:RelatedUrls"},
            )
            continue
        looks_like_service = (
            "service" in url_type.lower()
            or "service" in str(subtype).lower()
            or str(subtype).upper() in _SERVICE_SUBTYPES
        )
        if not looks_like_service:
            continue
        for pattern_regex, pattern_id in _URL_RULES:
            if re.search(pattern_regex, url, flags=re.IGNORECASE):
                found.setdefault(
                    pattern_id,
                    {
                        "available": True,
                        "endpoint": url,
                        "description": description,
                        "subtype": subtype,
                        "source": "cmr:RelatedUrls",
                    },
                )
                break
    return found


def fetch_services(short_name: str, provider: Optional[str] = None,
                   timeout: float = 30.0) -> dict:
    """Fetch the service associations for a collection."""
    entries = find_collections(short_name, timeout=timeout)
    if provider:
        entries = [e for e in entries if e.get("id", "").endswith(f"-{provider}")]
    if not entries:
        return {"short_name": short_name, "concept_id": None, "patterns": {}}

    cloud = [e for e in entries if e.get("cloud_hosted")]
    primary = (cloud or entries)[0]
    concept_id = primary.get("id")

    patterns: dict[str, dict] = {}
    if any(e.get("has_transforms") for e in entries):
        patterns["S1"] = {
            "available": True,
            "source": "cmr:has_transforms",
            "note": "Harmony-enabled collection",
        }

    url = f"{CMR_BASE}/concepts/{concept_id}"
    body = _cmr_get(url, "application/vnd.nasa.cmr.umm+json", timeout=timeout)
    umm_c = json.loads(body)
    for pattern_id, info in services_from_related_urls(umm_c).items():
        patterns.setdefault(pattern_id, info)

    return {
        "short_name": short_name,
        "concept_id": concept_id,
        "providers": [e.get("id") for e in entries],
        "cloud_hosted": bool(primary.get("cloud_hosted")),
        "patterns": patterns,
    }
