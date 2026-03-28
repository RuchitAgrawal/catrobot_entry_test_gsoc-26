"""
analyzer.py — Statistical Pre-Processing Engine.

Computes all mathematical insights from the ecosystem dataset BEFORE
sending anything to the Gemini API. This prevents the LLM from
hallucinating numeric trends and grounds the narration in real data.

Key outputs:
  - Per-zone moisture trend & drop rate (per hour)
  - Drone deployment spike detection
  - Crop health delta and anomaly flags
  - Irrigation event correlation
  - Cross-zone global anomaly list
  - Human-readable summary bullet points for prompt injection
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from .models import (
    AnalysisInsights,
    EcosystemDataset,
    EcosystemEvent,
    ZoneAnalysis,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Thresholds (tunable constants)
# ─────────────────────────────────────────────────────────────────────────────

MOISTURE_CRITICAL_PCT = 55.0        # Below this → critical zone
MOISTURE_DECLINING_THRESHOLD = -5.0 # Drop more than 5% over window → declining
MOISTURE_RECOVERING_THRESHOLD = 2.0 # Rise more than 2% → recovering
DRONE_SPIKE_THRESHOLD = 3           # More than 3 active events in a zone → spike
HEALTH_INDEX_WARNING = 7.0          # Below this → crop health warning


# ─────────────────────────────────────────────────────────────────────────────
#  Core analysis function
# ─────────────────────────────────────────────────────────────────────────────

def analyze_dataset(dataset: EcosystemDataset) -> AnalysisInsights:
    """
    Compute full statistical insights for the ecosystem dataset.

    Args:
        dataset: validated EcosystemDataset instance

    Returns:
        AnalysisInsights: all pre-computed statistics ready for prompt injection
    """
    events_by_zone: dict[str, list[EcosystemEvent]] = defaultdict(list)
    for event in sorted(dataset.events, key=lambda e: e.timestamp):
        events_by_zone[event.sensor_zone].append(event)

    zone_analyses: list[ZoneAnalysis] = []
    all_drone_deployments = 0
    all_irrigation_events = 0
    critical_zones: list[str] = []
    global_anomalies: list[str] = []

    for zone, events in sorted(events_by_zone.items()):
        za = _analyze_zone(zone, events)
        zone_analyses.append(za)
        all_drone_deployments += za.drone_deployments
        all_irrigation_events += za.irrigation_events
        if za.min_moisture_pct < MOISTURE_CRITICAL_PCT:
            critical_zones.append(zone)

    # ── Global trend ──────────────────────────────────────────────────────────
    all_deltas = [za.moisture_delta_pct for za in zone_analyses]
    mean_delta = statistics.mean(all_deltas) if all_deltas else 0.0

    if mean_delta <= MOISTURE_DECLINING_THRESHOLD:
        overall_trend = "declining"
    elif mean_delta >= MOISTURE_RECOVERING_THRESHOLD:
        overall_trend = "recovering"
    else:
        overall_trend = "stable"

    # ── Global anomalies ──────────────────────────────────────────────────────
    if critical_zones:
        global_anomalies.append(
            f"Critical moisture levels (<{MOISTURE_CRITICAL_PCT}%) detected in: "
            + ", ".join(critical_zones)
        )

    if all_drone_deployments >= DRONE_SPIKE_THRESHOLD * len(events_by_zone):
        global_anomalies.append(
            f"Elevated drone activity: {all_drone_deployments} total deployments across "
            f"{len(events_by_zone)} zones — possible large-scale stress event"
        )

    low_health_zones = [
        za.zone
        for za in zone_analyses
        if za.crop_health_mean < HEALTH_INDEX_WARNING
    ]
    if low_health_zones:
        global_anomalies.append(
            f"Below-threshold crop health (index < {HEALTH_INDEX_WARNING}) in: "
            + ", ".join(low_health_zones)
        )

    if all_irrigation_events > 0:
        global_anomalies.append(
            f"Automated irrigation triggered {all_irrigation_events} time(s) — "
            "ecosystem responded to moisture stress"
        )

    # ── Summary bullets (injected raw into the LLM prompt) ───────────────────
    summary_bullets = _build_summary_bullets(
        zone_analyses=zone_analyses,
        overall_trend=overall_trend,
        mean_delta=mean_delta,
        all_drone_deployments=all_drone_deployments,
        all_irrigation_events=all_irrigation_events,
        critical_zones=critical_zones,
        analysis_window_hours=dataset.time_range_hours,
    )

    # ── Severity score & tone register (data-driven, not user-selected) ───────
    severity_score, tone_register = _compute_severity(
        zone_analyses=zone_analyses,
        critical_zones=critical_zones,
        total_events=len(dataset.events),
        all_drone_deployments=all_drone_deployments,
    )

    return AnalysisInsights(
        analysis_window_hours=dataset.time_range_hours,
        total_events=len(dataset.events),
        zones_analyzed=dataset.zones,
        zone_analyses=zone_analyses,
        overall_moisture_trend=overall_trend,
        total_drone_deployments=all_drone_deployments,
        total_irrigation_events=all_irrigation_events,
        critical_zones=critical_zones,
        global_anomalies=global_anomalies,
        summary_bullets=summary_bullets,
        severity_score=severity_score,
        tone_register=tone_register,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Per-zone helpers
# ─────────────────────────────────────────────────────────────────────────────

def _analyze_zone(zone: str, events: list[EcosystemEvent]) -> ZoneAnalysis:
    """Compute statistics for a single sensor zone (events must be time-sorted)."""

    moistures = [e.soil_moisture_pct for e in events]
    health_indices = [e.crop_health_index for e in events]
    drone_deployments = sum(1 for e in events if e.drone_active)
    irrigation_events = sum(1 for e in events if e.irrigation_triggered)

    moisture_start = moistures[0]
    moisture_end = moistures[-1]
    moisture_delta = moisture_end - moisture_start  # negative = dropped

    # Time window in hours for rate calculation
    if len(events) > 1:
        time_delta_hours = (
            events[-1].timestamp - events[0].timestamp
        ).total_seconds() / 3600
        time_delta_hours = max(time_delta_hours, 0.001)  # avoid div by zero
    else:
        time_delta_hours = 1.0

    drop_rate_per_hour = moisture_delta / time_delta_hours

    anomaly_flags: list[str] = []

    drop_pct = abs(moisture_delta)
    if moisture_delta < 0 and drop_pct >= 10:
        anomaly_flags.append(
            f"Significant moisture drop: {drop_pct:.1f}% over {time_delta_hours:.1f}h "
            f"({abs(drop_rate_per_hour):.1f}%/h)"
        )

    if min(moistures) < MOISTURE_CRITICAL_PCT:
        anomaly_flags.append(
            f"Moisture fell below critical threshold ({MOISTURE_CRITICAL_PCT}%): "
            f"min recorded = {min(moistures):.1f}%"
        )

    if drone_deployments >= DRONE_SPIKE_THRESHOLD:
        anomaly_flags.append(
            f"Drone activity spike: {drone_deployments} deployments "
            f"({drone_deployments / len(events) * 100:.0f}% of readings)"
        )

    if irrigation_events > 0:
        anomaly_flags.append(
            f"Irrigation triggered {irrigation_events} time(s) in response to moisture stress"
        )

    health_delta = health_indices[-1] - health_indices[0]
    if health_delta < -0.5:
        anomaly_flags.append(
            f"Crop health declined by {abs(health_delta):.1f} index points"
        )

    return ZoneAnalysis(
        zone=zone,
        moisture_start_pct=round(moisture_start, 2),
        moisture_end_pct=round(moisture_end, 2),
        moisture_delta_pct=round(moisture_delta, 2),
        moisture_drop_rate_per_hour=round(drop_rate_per_hour, 3),
        min_moisture_pct=round(min(moistures), 2),
        max_moisture_pct=round(max(moistures), 2),
        drone_deployments=drone_deployments,
        irrigation_events=irrigation_events,
        crop_health_mean=round(statistics.mean(health_indices), 2),
        crop_health_delta=round(health_delta, 2),
        peak_temperature_celsius=round(max(e.temperature_celsius for e in events), 1),
        anomaly_flags=anomaly_flags,
    )


def _build_summary_bullets(
    zone_analyses: list[ZoneAnalysis],
    overall_trend: str,
    mean_delta: float,
    all_drone_deployments: int,
    all_irrigation_events: int,
    critical_zones: list[str],
    analysis_window_hours: float,
) -> list[str]:
    """Build a concise bullet list for LLM prompt injection."""
    bullets: list[str] = []

    bullets.append(
        f"Overall soil moisture trend: {overall_trend.upper()} "
        f"(mean change: {mean_delta:+.1f}% over {analysis_window_hours:.1f}h)"
    )

    for za in zone_analyses:
        bullets.append(
            f"{za.zone}: moisture {za.moisture_start_pct:.1f}% → {za.moisture_end_pct:.1f}% "
            f"({za.moisture_delta_pct:+.1f}%), "
            f"crop health mean {za.crop_health_mean:.1f}/10, "
            f"peak temp {za.peak_temperature_celsius}°C"
        )

    if critical_zones:
        bullets.append(
            f"CRITICAL: Zones {', '.join(critical_zones)} dropped below "
            f"{MOISTURE_CRITICAL_PCT}% moisture"
        )

    if all_drone_deployments > 0:
        bullets.append(
            f"Total drone deployments: {all_drone_deployments} — "
            "automated stress-response protocol active"
        )

    if all_irrigation_events > 0:
        bullets.append(
            f"Irrigation system triggered {all_irrigation_events} time(s) — "
            "ecosystem attempting to self-stabilize"
        )

    # Per-zone anomalies
    for za in zone_analyses:
        for flag in za.anomaly_flags:
            bullets.append(f"  [{za.zone}] {flag}")

    return bullets


# ─────────────────────────────────────────────────────────────────────────────
#  Severity scoring (data-driven tone derivation)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_severity(
    zone_analyses: list,
    critical_zones: list[str],
    total_events: int,
    all_drone_deployments: int,
) -> tuple[float, str]:
    """
    Compute a composite severity score [0.0, 1.0] from the statistical insights.
    Derives the appropriate tone register automatically — no user input needed.

    Formula:
      severity = 0.50 × critical_zone_ratio
               + 0.30 × normalized_avg_drop_rate   (capped at 5%/h = 1.0)
               + 0.20 × drone_intensity             (deployments / total events)

    Tone mapping:
      < 0.30  →  "routine"   (calm monitoring log)
      0.30–0.65 → "advisory" (elevated field advisory)
      ≥ 0.65  →  "emergency" (urgent emergency report)
    """
    n_zones = max(len(zone_analyses), 1)
    critical_ratio = len(critical_zones) / n_zones

    # Average absolute moisture drop rate across all zones
    avg_drop_rate = statistics.mean(
        abs(za.moisture_drop_rate_per_hour) for za in zone_analyses
    ) if zone_analyses else 0.0
    normalized_drop = min(avg_drop_rate / 5.0, 1.0)  # 5%/h = max

    drone_intensity = min(all_drone_deployments / max(total_events, 1) * 3, 1.0)

    severity = round(
        0.50 * critical_ratio +
        0.30 * normalized_drop +
        0.20 * drone_intensity,
        3,
    )
    severity = max(0.0, min(1.0, severity))

    if severity >= 0.65:
        tone = "emergency"
    elif severity >= 0.30:
        tone = "advisory"
    else:
        tone = "routine"

    return severity, tone
