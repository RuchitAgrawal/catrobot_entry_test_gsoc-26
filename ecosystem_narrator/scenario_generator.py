"""
scenario_generator.py - Procedural dataset generator for demo scenarios.

Generates physics-consistent CSV datasets for four scenario types:
  normal   - stable day, no interventions needed
  drought  - progressive moisture stress in two zones
  crisis   - rapid multi-zone failure, maximum intervention
  recovery - moisture rising after an earlier crisis event

Moisture, drone activity, and irrigation are causally linked:
  moisture decays → drones deploy → irrigation fires → moisture recovers.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from .models import EcosystemDataset, EcosystemEvent

ScenarioType = Literal["normal", "drought", "crisis", "recovery"]

SCENARIO_DESCRIPTIONS = {
    "normal":   "Stable day — all zones healthy, no interventions needed",
    "drought":  "Progressive moisture stress — two zones go critical, automated response activates",
    "crisis":   "Rapid multi-zone failure — all zones critical, maximum intervention",
    "recovery": "Post-intervention — moisture recovering after an earlier crisis event",
}

# Calibration constants
_DRONE_THRESHOLD      = 63.0   # moisture % below which drones deploy
_IRRIGATION_THRESHOLD = 54.0   # moisture % below which irrigation fires
_IRRIGATION_BOOST     = 3.5    # moisture % recovered per irrigated reading
_BASE_DATE  = datetime(2024, 6, 15, 6, 0, 0)
_INTERVAL   = timedelta(minutes=30)
_N_READINGS = 24               # readings per zone (12-hour window)

# Per-scenario physics parameters
_PARAMS: dict[str, dict] = {
    "normal": {
        "zones": [
            {"start_moisture": 76.2, "decline_rate": 0.72, "health_start": 8.4},
            {"start_moisture": 73.8, "decline_rate": 0.65, "health_start": 8.1},
            {"start_moisture": 79.5, "decline_rate": 0.58, "health_start": 8.7},
            {"start_moisture": 71.0, "decline_rate": 0.80, "health_start": 8.0},
        ],
        "base_temp": 22.0, "temp_rise": 0.55, "rainfall": 0.0,
    },
    "drought": {
        "zones": [
            {"start_moisture": 72.0, "decline_rate": 1.45, "health_start": 8.0},
            {"start_moisture": 68.0, "decline_rate": 1.35, "health_start": 7.7},
            {"start_moisture": 76.5, "decline_rate": 0.92, "health_start": 8.4},
            {"start_moisture": 65.0, "decline_rate": 1.60, "health_start": 7.5},
        ],
        "base_temp": 24.5, "temp_rise": 0.60, "rainfall": 0.0,
    },
    "crisis": {
        "zones": [
            {"start_moisture": 65.0, "decline_rate": 1.80, "health_start": 7.3},
            {"start_moisture": 62.0, "decline_rate": 1.95, "health_start": 7.0},
            {"start_moisture": 67.0, "decline_rate": 1.65, "health_start": 7.5},
            {"start_moisture": 60.0, "decline_rate": 2.10, "health_start": 6.8},
        ],
        "base_temp": 29.0, "temp_rise": 0.65, "rainfall": 0.0,
    },
    "recovery": {
        "zones": [
            {"start_moisture": 48.0, "decline_rate": -1.10, "health_start": 6.8},
            {"start_moisture": 46.5, "decline_rate": -0.98, "health_start": 6.5},
            {"start_moisture": 50.5, "decline_rate": -0.88, "health_start": 7.0},
            {"start_moisture": 44.0, "decline_rate": -1.25, "health_start": 6.3},
        ],
        "base_temp": 27.0, "temp_rise": 0.25, "rainfall": 0.0,
    },
}


def generate_scenario(scenario: ScenarioType) -> EcosystemDataset:
    """
    Procedurally generate a physics-consistent EcosystemDataset.

    Args:
        scenario: One of "normal", "drought", "crisis", "recovery"

    Returns:
        EcosystemDataset with 96 events (4 zones × 24 readings, 12-hour window)
    """
    params = _PARAMS[scenario]
    zone_params = params["zones"]
    base_temp = params["base_temp"]
    temp_rise = params["temp_rise"]
    rainfall = params["rainfall"]

    events: list[EcosystemEvent] = []
    zone_names = ["Zone-A", "Zone-B", "Zone-C", "Zone-D"]

    for zone_idx, zname in enumerate(zone_names):
        zp = zone_params[zone_idx]
        moisture = zp["start_moisture"]
        health = zp["health_start"]
        decline = zp["decline_rate"]  # negative = recovering/rising
        irrigation_active_prev = False

        for reading_idx in range(_N_READINGS):
            timestamp = _BASE_DATE + _INTERVAL * reading_idx
            temp = round(base_temp + temp_rise * reading_idx, 1)

            drone_active = moisture < _DRONE_THRESHOLD
            irrigation_triggered = moisture < _IRRIGATION_THRESHOLD

            # Irrigation partially offsets decline if it was active last reading
            if irrigation_active_prev and scenario in ("drought", "crisis"):
                moisture = min(moisture + _IRRIGATION_BOOST, 100.0)

            moisture = max(round(moisture, 1), 20.0)
            health = max(round(health, 1), 0.0)

            events.append(EcosystemEvent(
                timestamp=timestamp,
                sensor_zone=zname,
                soil_moisture_pct=moisture,
                drone_active=drone_active,
                crop_health_index=health,
                irrigation_triggered=irrigation_triggered,
                temperature_celsius=temp,
                rainfall_mm=rainfall,
            ))

            # Advance state for next reading
            if scenario == "recovery":
                moisture = min(moisture - decline, 95.0)  # decline is negative → adds
                health = min(health + 0.08, 10.0)
            else:
                moisture = max(moisture - decline, 20.0)
                if irrigation_triggered:
                    health = max(health - 0.06, 0.0)
                else:
                    health = max(health - 0.04, 0.0)

            irrigation_active_prev = irrigation_triggered

    return EcosystemDataset(
        events=events,
        source_file=f"generated:{scenario}",
    )


def scenario_to_csv(scenario: ScenarioType, output_path: Path | None = None) -> str:
    """
    Generate a scenario and serialize it to CSV.

    Args:
        scenario: scenario type
        output_path: if provided, write CSV to this path

    Returns:
        CSV string
    """
    dataset = generate_scenario(scenario)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "timestamp", "sensor_zone", "soil_moisture_pct",
        "drone_active", "crop_health_index", "irrigation_triggered",
        "temperature_celsius", "rainfall_mm",
    ])
    writer.writeheader()
    for e in sorted(dataset.events, key=lambda x: (x.sensor_zone, x.timestamp)):
        writer.writerow({
            "timestamp":            e.timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
            "sensor_zone":          e.sensor_zone,
            "soil_moisture_pct":    e.soil_moisture_pct,
            "drone_active":         str(e.drone_active).lower(),
            "crop_health_index":    e.crop_health_index,
            "irrigation_triggered": str(e.irrigation_triggered).lower(),
            "temperature_celsius":  e.temperature_celsius,
            "rainfall_mm":          e.rainfall_mm,
        })

    csv_text = buf.getvalue()
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(csv_text, encoding="utf-8")

    return csv_text
