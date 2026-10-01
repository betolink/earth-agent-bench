from __future__ import annotations

from ..schemas import EfficiencyMetrics, Envelope, Task

DEFAULT_ENVELOPES: dict[str, Envelope] = {
    "C1": Envelope(max_bytes=100_000_000, max_objects=50, max_runtime_s=300),
    "C2": Envelope(max_bytes=100_000_000, max_objects=50, max_runtime_s=300),
    "C3": Envelope(max_bytes=250_000_000, max_objects=80, max_runtime_s=600),
    "C4": Envelope(max_bytes=150_000_000, max_objects=40, max_runtime_s=300),
    "C5": Envelope(max_bytes=200_000_000, max_objects=60, max_runtime_s=600),
    "S1": Envelope(max_bytes=500_000_000, max_objects=10, max_runtime_s=600),
    "S2": Envelope(max_bytes=800_000_000, max_objects=20, max_runtime_s=900),
    "S3": Envelope(max_bytes=500_000_000, max_objects=50, max_runtime_s=600),
    "S4": Envelope(max_bytes=300_000_000, max_objects=5, max_runtime_s=900),
    "S5": Envelope(max_bytes=150_000_000, max_objects=3, max_runtime_s=600),
    "S6": Envelope(max_bytes=1_000_000_000, max_objects=100, max_runtime_s=900),
    "T1": Envelope(max_bytes=800_000_000, max_objects=30, max_runtime_s=900),
    "T2": Envelope(max_bytes=500_000_000, max_objects=50, max_runtime_s=600),
    "T3": Envelope(max_bytes=500_000_000, max_objects=50, max_runtime_s=600),
    "F1": Envelope(max_bytes=5_000_000_000, max_objects=500, max_runtime_s=1800),
    "F2": Envelope(max_bytes=5_000_000_000, max_objects=500, max_runtime_s=1800),
    "F3": Envelope(max_bytes=5_000_000_000, max_objects=500, max_runtime_s=1800),
    "F4": Envelope(max_bytes=5_000_000_000, max_objects=500, max_runtime_s=1800),
    "M1": Envelope(max_bytes=50_000_000_000, max_objects=5000, max_runtime_s=7200),
    "M2": Envelope(max_bytes=500_000_000_000, max_objects=50000, max_runtime_s=72000),
}


def score_against_envelope(value: float, limit: float) -> float:
    if value <= limit:
        return 1.0
    falloff = 1.0 - (value / limit - 1.0) / 3.0
    return max(0.0, falloff)


def envelope_for(task: Task, pattern_id: str) -> Envelope:
    override = task.efficiency_envelopes.get(pattern_id)
    if override is not None:
        return override
    primary = task.gold.primary_patterns[0] if task.gold.primary_patterns else "M1"
    return task.efficiency_envelopes.get(primary, DEFAULT_ENVELOPES.get(pattern_id, DEFAULT_ENVELOPES["M1"]))


def score_efficiency(task: Task, metrics: EfficiencyMetrics,
                     observed_patterns: list[str]) -> float:
    if not observed_patterns:
        return 0.0
    scores = []
    for pattern_id in observed_patterns:
        envelope = envelope_for(task, pattern_id)
        scores.extend([
            score_against_envelope(metrics.bytes_read, envelope.max_bytes),
            score_against_envelope(metrics.objects_read, envelope.max_objects),
            score_against_envelope(metrics.runtime_seconds, envelope.max_runtime_s),
        ])
    return sum(scores) / len(scores)
