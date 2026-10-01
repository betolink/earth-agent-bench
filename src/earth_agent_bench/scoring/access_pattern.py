from __future__ import annotations

from typing import Iterable

from ..schemas import PatternTiers

TIER_SCORES = {"best": 1.0, "acceptable": 0.7, "marginal": 0.3}


def score_access_pattern(observed: str, tiers: PatternTiers) -> float:
    for tier, score in TIER_SCORES.items():
        if observed in getattr(tiers, tier):
            return score
    return 0.0


def classify_pattern(observed: str, tiers: PatternTiers) -> str:
    for tier in TIER_SCORES:
        if observed in getattr(tiers, tier):
            return tier
    if observed in tiers.inefficient:
        return "inefficient"
    return "unlisted"


def score_patterns_for_collections(observed: Iterable[str], tiers: PatternTiers) -> float:
    observed = list(observed)
    if not observed:
        return 0.0
    scores = [score_access_pattern(pattern, tiers) for pattern in observed]
    return sum(scores) / len(scores)
