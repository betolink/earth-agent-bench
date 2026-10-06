from __future__ import annotations

from ..schemas import RunObservation, Task, VerifierResult
from .access_pattern import classify_pattern, score_patterns_for_collections
from .efficiency import score_efficiency
from .service_discovery import score_service_discovery

WEIGHTS = {
    "collection_selection": 0.10,
    "service_discovery": 0.15,
    "access_pattern": 0.35,
    "representation": 0.15,
    "efficiency": 0.15,
    "validation": 0.10,
}


def _normalize_name(value: str) -> str:
    return "".join(char for char in str(value).lower() if char.isalnum())


def score_collection_selection(task: Task, observed_collections: list[str]) -> float:
    if not observed_collections:
        return 0.0
    tiers = {"preferred": 1.0, "acceptable": 0.7, "discouraged": 0.2, "unacceptable": 0.0}
    by_name = {_normalize_name(c.short_name): c for c in task.collections}
    by_concept = {c.concept_id: c for c in task.collections if c.concept_id}
    scores = []
    for name in observed_collections:
        token = str(name).strip()
        collection = by_name.get(_normalize_name(token)) or by_concept.get(token)
        if collection is None:
            normalized = _normalize_name(token)
            for key, candidate in by_name.items():
                if len(key) >= 4 and (key in normalized or normalized in key):
                    collection = candidate
                    break
        scores.append(tiers[collection.tier] if collection else 0.0)
    return sum(scores) / len(scores)


def score_representation(task: Task, representation: str) -> float:
    primary_lazy = any(p.startswith("C") or p.startswith(("S", "T")) for p in task.gold.primary_patterns)
    if representation == "lazy":
        return 1.0
    if representation == "materialized" and not primary_lazy:
        return 1.0
    if representation == "materialized":
        return 0.3
    return 0.0


def available_service_names(task: Task) -> list[str]:
    names = set()
    for collection in task.collections:
        if collection.tier in {"preferred", "acceptable"}:
            for service in collection.services:
                if service.available:
                    names.add(service.pattern)
    return sorted(names)


def score_run(task: Task, observation: RunObservation) -> VerifierResult:
    access = score_patterns_for_collections(observation.observed_patterns, task.pattern_tiers)
    collection = score_collection_selection(task, observation.collection_short_names)
    discovery = score_service_discovery(observation.discovered_services, available_service_names(task))
    representation = score_representation(task, observation.representation)
    efficiency = score_efficiency(task, observation.metrics, observation.observed_patterns)
    validation = 1.0 if observation.validation_passed else 0.0

    reward = (
        WEIGHTS["collection_selection"] * collection
        + WEIGHTS["service_discovery"] * discovery
        + WEIGHTS["access_pattern"] * access
        + WEIGHTS["representation"] * representation
        + WEIGHTS["efficiency"] * efficiency
        + WEIGHTS["validation"] * validation
    )

    observed = observation.observed_patterns[0] if observation.observed_patterns else None
    details = {
        "observed_patterns": observation.observed_patterns,
        "observed_classifications": [
            classify_pattern(p, task.pattern_tiers) for p in observation.observed_patterns
        ],
        "best_available": task.pattern_tiers.best,
        "primary_gold": task.gold.primary_patterns,
        "gap_reason": (
            None
            if observed in task.pattern_tiers.best
            else f"observed {observed}; best available {task.pattern_tiers.best}"
        ),
    }
    metrics = observation.metrics.model_dump()

    return VerifierResult(
        reward=round(reward, 4),
        collection_selection=round(collection, 4),
        service_discovery=round(discovery, 4),
        access_pattern=round(access, 4),
        representation=round(representation, 4),
        efficiency=round(efficiency, 4),
        validation=validation,
        access_pattern_details=details,
        efficiency_metrics=metrics,
    )
