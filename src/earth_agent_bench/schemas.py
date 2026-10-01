"""Task, oracle and result schemas for earth-agent-bench."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PatternId = Literal[
    "C1", "C2", "C3", "C4", "C5",
    "S1", "S2", "S3", "S4", "S5", "S6",
    "T1", "T2", "T3",
    "F1", "F2", "F3", "F4",
    "M1", "M2",
]


class SpatialExtent(BaseModel):
    type: Literal["bbox", "polygon", "point"]
    coordinates: list[float]


class TemporalExtent(BaseModel):
    start: date
    end: date


class AccessRequirement(BaseModel):
    description: str
    spatial_extent: SpatialExtent
    temporal_extent: TemporalExtent
    variables_of_interest: list[str]
    output_format: Literal["netcdf", "zarr", "csv", "geotiff", "parquet"]


class ServiceRef(BaseModel):
    pattern: PatternId
    available: bool = True
    grade: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None


class CollectionRef(BaseModel):
    short_name: str
    concept_id: Optional[str] = None
    tier: Literal["preferred", "acceptable", "discouraged", "unacceptable"]
    role: Optional[str] = None
    reason: Optional[str] = None
    services: list[ServiceRef] = Field(default_factory=list)


class Envelope(BaseModel):
    max_bytes: int
    max_objects: int
    max_runtime_s: int


class ValidationSpec(BaseModel):
    checks: list[str] = Field(default_factory=lambda: [
        "variable_present",
        "spatial_extent_correct",
        "temporal_extent_correct",
        "units_correct",
    ])
    units: Optional[str] = None
    aggregation: Optional[str] = None


class PatternTiers(BaseModel):
    best: list[PatternId] = Field(default_factory=list)
    acceptable: list[PatternId] = Field(default_factory=list)
    marginal: list[PatternId] = Field(default_factory=list)
    inefficient: list[PatternId] = Field(default_factory=list)


class GoldStandard(BaseModel):
    primary_patterns: list[PatternId]
    acceptable_patterns: list[PatternId] = Field(default_factory=list)
    reasoning: str = ""


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    science_sphere: str
    title: str
    discipline_workflow: list[str] = Field(default_factory=list)
    access_requirement: AccessRequirement
    collections: list[CollectionRef]
    pattern_tiers: PatternTiers
    efficiency_envelopes: dict[str, Envelope] = Field(default_factory=dict)
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    gold: GoldStandard
    notes: list[str] = Field(default_factory=list)


class EfficiencyMetrics(BaseModel):
    bytes_read: int = 0
    objects_read: int = 0
    runtime_seconds: float = 0.0


class RunObservation(BaseModel):
    task_id: str
    observed_patterns: list[PatternId] = Field(default_factory=list)
    collection_short_names: list[str] = Field(default_factory=list)
    discovered_services: list[str] = Field(default_factory=list)
    representation: Literal["lazy", "materialized", "unknown"] = "unknown"
    validation_passed: bool = False
    metrics: EfficiencyMetrics = Field(default_factory=EfficiencyMetrics)


class RunManifest(BaseModel):
    task_id: str
    model_id: str
    model_tier: Literal["local", "frontier_open", "closed_reference"]
    harness: str
    condition: Literal["baseline", "mcp", "skills", "mcp-skills"]
    trial: int = 1
    quantization: Optional[str] = None
    harness_version: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tokens_per_second: Optional[float] = None
    vram_gb: Optional[float] = None


class VerifierResult(BaseModel):
    reward: float
    collection_selection: float
    service_discovery: float
    access_pattern: float
    representation: float
    efficiency: float
    validation: float
    access_pattern_details: dict = Field(default_factory=dict)
    efficiency_metrics: dict = Field(default_factory=dict)
