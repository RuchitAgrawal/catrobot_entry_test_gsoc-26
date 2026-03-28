"""
models.py - Pydantic v2 schemas for the Ecosystem Narrator.

Data contracts for:
  EcosystemEvent   - single sensor reading from the agro grid
  EcosystemDataset - collection of events + computed metadata
  AnalysisInsights - results of the statistical pre-processing pass
  NarrationOutput  - structured LLM response (2-4 sentences enforced)
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


# Raw sensor event

class EcosystemEvent(BaseModel):
    """A single timestamped sensor reading from the agricultural grid."""

    timestamp: datetime
    sensor_zone: Annotated[str, Field(description="Named grid zone, e.g. Zone-A")]
    soil_moisture_pct: Annotated[
        float, Field(ge=0.0, le=100.0, description="Soil moisture as a percentage 0-100")
    ]
    drone_active: bool
    crop_health_index: Annotated[
        float, Field(ge=0.0, le=10.0, description="Crop health index 0 (dead) to 10 (excellent)")
    ]
    irrigation_triggered: bool
    temperature_celsius: float
    rainfall_mm: Annotated[float, Field(ge=0.0, default=0.0)]

    @field_validator("sensor_zone")
    @classmethod
    def zone_must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("sensor_zone must not be empty")
        return v.strip()


# Dataset container

class EcosystemDataset(BaseModel):
    """Container for a collection of ecosystem events with metadata."""

    events: list[EcosystemEvent] = Field(..., min_length=1)
    source_file: str = Field(default="unknown")
    loaded_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def zones(self) -> list[str]:
        return sorted({e.sensor_zone for e in self.events})

    @property
    def time_range_hours(self) -> float:
        timestamps = [e.timestamp for e in self.events]
        delta = max(timestamps) - min(timestamps)
        return round(delta.total_seconds() / 3600, 2)


# Statistical insights (pre-processed, ready for prompt injection)

class ZoneAnalysis(BaseModel):
    """Per-zone statistical summary."""

    zone: str
    moisture_start_pct: float
    moisture_end_pct: float
    moisture_delta_pct: float  # negative = dropped
    moisture_drop_rate_per_hour: float
    min_moisture_pct: float
    max_moisture_pct: float
    drone_deployments: int
    irrigation_events: int
    crop_health_mean: float
    crop_health_delta: float
    peak_temperature_celsius: float
    anomaly_flags: list[str] = Field(default_factory=list)


class AnalysisInsights(BaseModel):
    """Aggregate statistical insights across all zones."""

    analysis_window_hours: float
    total_events: int
    zones_analyzed: list[str]
    zone_analyses: list[ZoneAnalysis]
    overall_moisture_trend: str          # "declining" | "stable" | "recovering"
    total_drone_deployments: int
    total_irrigation_events: int
    critical_zones: list[str]            # zones with moisture < 55%
    global_anomalies: list[str]          # cross-zone observations
    summary_bullets: list[str]           # bullet points injected into the LLM prompt

    # Severity-adaptive tone derived from the composite severity score
    severity_score: Annotated[
        float,
        Field(default=0.0, ge=0.0, le=1.0,
              description="Composite severity 0 (normal) to 1 (full crisis)"),
    ] = 0.0
    tone_register: str = Field(
        default="routine",
        description="Auto-derived tone: 'routine' | 'advisory' | 'emergency'",
    )


# LLM structured output

class NarrationOutput(BaseModel):
    """
    Structured output enforced from the LLM response.
    sentence_count is validated against the actual narration string.
    """

    sentence_count: Annotated[
        int,
        Field(ge=2, le=4, description="Number of sentences in the narration (must be 2-4)"),
    ]
    narration: Annotated[
        str,
        Field(
            min_length=40,
            description="2-4 sentence ecosystem summary produced by the narrator",
        ),
    ]
    anomalies_detected: list[str] = Field(
        default_factory=list,
        description="List of specific anomalies the narration covers",
    )
    confidence: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Model confidence in the narration (0-1)"),
    ] = 1.0

    @model_validator(mode="after")
    def validate_sentence_count_matches_narration(self) -> "NarrationOutput":
        """
        Cross-validates sentence_count against the actual sentence count
        in the narration string. Auto-corrects if they diverge.
        """
        import re
        # Split on . ! ? followed by whitespace or end-of-string
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", self.narration.strip())
            if s.strip()
        ]
        actual = len(sentences)
        if actual != self.sentence_count:
            # sentence_count drifts from the actual count; fix it rather than raise
            object.__setattr__(self, "sentence_count", actual)
        return self
