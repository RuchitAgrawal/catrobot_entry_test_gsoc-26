"""
tests/test_analyzer.py — Unit tests for the statistical pre-processing engine.

Tests verify that analyzer.py correctly computes all metrics from raw event
data, independent of any LLM call. These are pure-Python deterministic tests.

Run with:
    uv run pytest tests/ -v
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ecosystem_narrator.analyzer import analyze_dataset, _compute_severity
from ecosystem_narrator.models import EcosystemDataset, EcosystemEvent, ZoneAnalysis


# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_event(
    zone: str,
    moisture: float,
    health: float,
    drone: bool = False,
    irrigation: bool = False,
    offset_minutes: int = 0,
    temp: float = 25.0,
) -> EcosystemEvent:
    return EcosystemEvent(
        timestamp=datetime(2024, 6, 15, 6, 0, 0) + timedelta(minutes=offset_minutes),
        sensor_zone=zone,
        soil_moisture_pct=moisture,
        drone_active=drone,
        crop_health_index=health,
        irrigation_triggered=irrigation,
        temperature_celsius=temp,
        rainfall_mm=0.0,
    )


def _drought_dataset() -> EcosystemDataset:
    """Zone-A drops 20%, Zone-B drops 15%, Zone-C stays stable."""
    events = [
        # Zone-A: 72 → 52 (critical)
        _make_event("Zone-A", 72.0, 8.0, offset_minutes=0),
        _make_event("Zone-A", 66.0, 7.8, drone=True, offset_minutes=30),
        _make_event("Zone-A", 60.0, 7.6, drone=True, offset_minutes=60),
        _make_event("Zone-A", 54.0, 7.4, drone=True, offset_minutes=90),
        _make_event("Zone-A", 52.0, 7.2, drone=True, irrigation=True, offset_minutes=120),
        # Zone-B: 68 → 53 (critical)
        _make_event("Zone-B", 68.0, 7.8, offset_minutes=0),
        _make_event("Zone-B", 62.0, 7.6, drone=True, offset_minutes=30),
        _make_event("Zone-B", 57.0, 7.4, drone=True, offset_minutes=60),
        _make_event("Zone-B", 53.0, 7.1, drone=True, irrigation=True, offset_minutes=90),
        _make_event("Zone-B", 55.0, 7.0, drone=False, irrigation=True, offset_minutes=120),
        # Zone-C: 80 → 73 (no drone, no irrigation)
        _make_event("Zone-C", 80.0, 8.5, offset_minutes=0),
        _make_event("Zone-C", 78.0, 8.4, offset_minutes=30),
        _make_event("Zone-C", 76.0, 8.3, offset_minutes=60),
        _make_event("Zone-C", 74.0, 8.3, offset_minutes=90),
        _make_event("Zone-C", 73.0, 8.2, offset_minutes=120),
    ]
    return EcosystemDataset(events=events, source_file="test_drought")


def _normal_dataset() -> EcosystemDataset:
    """All zones healthy, no interventions."""
    events = [
        _make_event("Zone-A", 76.0, 8.4, offset_minutes=0),
        _make_event("Zone-A", 75.5, 8.4, offset_minutes=30),
        _make_event("Zone-A", 75.0, 8.3, offset_minutes=60),
        _make_event("Zone-B", 73.0, 8.1, offset_minutes=0),
        _make_event("Zone-B", 72.5, 8.1, offset_minutes=30),
        _make_event("Zone-B", 72.0, 8.0, offset_minutes=60),
    ]
    return EcosystemDataset(events=events, source_file="test_normal")


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMoistureMetrics:
    """Test that per-zone moisture statistics are computed correctly."""

    def test_moisture_delta_computed_correctly(self):
        """Zone-A drops from 72 to 52 — delta must be -20."""
        dataset = _drought_dataset()
        insights = analyze_dataset(dataset)

        zone_a = next(z for z in insights.zone_analyses if z.zone == "Zone-A")
        assert zone_a.moisture_start_pct == pytest.approx(72.0, abs=0.1)
        assert zone_a.moisture_end_pct == pytest.approx(52.0, abs=0.1)
        assert zone_a.moisture_delta_pct == pytest.approx(-20.0, abs=0.1)

    def test_critical_zone_detection(self):
        """Zones where moisture drops below 55% must appear in critical_zones."""
        dataset = _drought_dataset()
        insights = analyze_dataset(dataset)

        assert "Zone-A" in insights.critical_zones
        assert "Zone-B" in insights.critical_zones
        assert "Zone-C" not in insights.critical_zones

    def test_stable_zone_not_flagged_critical(self):
        """Zone-C stays above 65% — must not be in critical_zones."""
        dataset = _drought_dataset()
        insights = analyze_dataset(dataset)

        zone_c = next(z for z in insights.zone_analyses if z.zone == "Zone-C")
        assert zone_c.min_moisture_pct > 55.0
        assert "Zone-C" not in insights.critical_zones


class TestDroneAndIrrigationCounts:
    """Test event counting correctness."""

    def test_drone_deployment_count_per_zone(self):
        """Zone-A has 4 drone-active events; Zone-C has 0."""
        dataset = _drought_dataset()
        insights = analyze_dataset(dataset)

        zone_a = next(z for z in insights.zone_analyses if z.zone == "Zone-A")
        zone_c = next(z for z in insights.zone_analyses if z.zone == "Zone-C")
        assert zone_a.drone_deployments == 4
        assert zone_c.drone_deployments == 0

    def test_total_irrigation_events_summed_across_zones(self):
        """Zone-A has 1, Zone-B has 2 irrigation events → total = 3."""
        dataset = _drought_dataset()
        insights = analyze_dataset(dataset)

        assert insights.total_irrigation_events == 3


class TestSeverityScoring:
    """Test that the composite severity score and tone register are correct."""

    def test_drought_yields_advisory_or_emergency_tone(self):
        """A drought with 2 critical zones should produce advisory or emergency tone."""
        dataset = _drought_dataset()
        insights = analyze_dataset(dataset)

        assert insights.tone_register in ("advisory", "emergency")
        assert insights.severity_score > 0.30

    def test_normal_conditions_yield_routine_tone(self):
        """No critical zones, no drones → routine tone."""
        dataset = _normal_dataset()
        insights = analyze_dataset(dataset)

        assert insights.tone_register == "routine"
        assert insights.severity_score < 0.30

    def test_severity_bounds(self):
        """Severity score must always be in [0, 1]."""
        for dataset in [_drought_dataset(), _normal_dataset()]:
            insights = analyze_dataset(dataset)
            assert 0.0 <= insights.severity_score <= 1.0

    def test_compute_severity_all_critical_returns_high_score(self):
        """3/3 critical zones + high drone activity should push severity above 0.65."""
        zone_analyses = [
            ZoneAnalysis(
                zone="Zone-A", moisture_start_pct=60.0, moisture_end_pct=45.0,
                moisture_delta_pct=-15.0, moisture_drop_rate_per_hour=-4.0,
                min_moisture_pct=45.0, max_moisture_pct=60.0, drone_deployments=8,
                irrigation_events=3, crop_health_mean=6.5, crop_health_delta=-1.0,
                peak_temperature_celsius=35.0,
            ),
        ] * 3  # simulate 3 identical critical zones
        score, tone = _compute_severity(
            zone_analyses=zone_analyses,
            critical_zones=["Zone-A", "Zone-B", "Zone-C"],
            total_events=30,
            all_drone_deployments=24,
        )
        assert score >= 0.65
        assert tone == "emergency"
