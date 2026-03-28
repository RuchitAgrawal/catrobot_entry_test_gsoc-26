"""
narrator.py — EcosystemNarrator: LLM integration with bulletproof mock fallback.

Architecture:
  LLMClientProtocol    — interface (Protocol) both clients implement
  GeminiClient         — real client using google-genai SDK with JSON schema enforcement
  MockClient           — instant hardcoded response; prints color-coded warning
  EcosystemNarrator    — orchestrates dataset → analysis → client → NarrationOutput

The entire chain is deterministic: the 2–4 sentence constraint is enforced
at the schema level, not just hoped for in the prompt.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .analyzer import analyze_dataset
from .models import (
    AnalysisInsights,
    EcosystemDataset,
    EcosystemEvent,
    NarrationOutput,
)

load_dotenv()

logger = logging.getLogger(__name__)
console = Console()

# ─────────────────────────────────────────────────────────────────────────────
#  Tone-register instructions (injected based on auto-derived severity score)
# ─────────────────────────────────────────────────────────────────────────────

# Instead of a user-selected style dropdown, tone is derived from
# the statistical severity score computed by analyzer.py.
# The LLM adapts its language register based on actual data conditions.

TONE_INSTRUCTIONS: dict[str, str] = {
    "routine": (
        "Write in a calm, data-forward monitoring style. Use past tense. "
        "Emphasize measured observations and overall system stability. "
        "Tone: professional field log. No urgency."
    ),
    "advisory": (
        "Write in an elevated, action-oriented advisory style. Use present tense. "
        "Lead with the anomaly, describe the automated response, assess current status. "
        "Tone: field advisory memo. Measured urgency — informative but not alarming."
    ),
    "emergency": (
        "Write in an urgent, imperative emergency report style. Use present tense. "
        "Lead immediately with the crisis severity, specify affected zones, "
        "describe intervention status, and assess risk trajectory. "
        "Tone: emergency situation report. Urgent, direct, no filler phrases."
    ),
}

PROMPT_TEMPLATE = """\
You are an expert agricultural ecosystem analyst monitoring a smart sensor grid.
Your task is to write a concise, accurate narration of today's ecosystem health.

## WRITING REGISTER (auto-derived from severity score={severity_score:.2f}):
{tone_instruction}

## STATISTICAL INSIGHTS (pre-computed — treat these as ground truth):
{bullets}

## RAW DATA SNAPSHOT (5 most recent events):
{snapshot}

## INSTRUCTIONS:
Write a narration of EXACTLY {min_s}–{max_s} sentences describing:
1. The dominant moisture trend observed across zones
2. Any critical anomalies or stress events (drone activity, irrigation triggers)
3. The overall ecosystem status and outlook

RULES (strictly enforced):
- Narration must be {min_s}–{max_s} sentences — no more, no less.
- Reference specific percentages, zone names, and numbers from the insights above.
- Do NOT invent numbers not present in the statistical insights.
- Confidence should reflect how clearly the data tells a story (0.0–1.0).

Return ONLY a valid JSON object in this exact format:
{{
  "sentence_count": <integer 2–4>,
  "narration": "<your {min_s}–{max_s} sentence narration here>",
  "anomalies_detected": ["<anomaly 1>", "<anomaly 2>"],
  "confidence": <float 0.0–1.0>
}}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  LLM Client Protocol
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class LLMClientProtocol(Protocol):
    """Interface that every LLM client must satisfy."""

    def generate(self, prompt: str) -> NarrationOutput:
        """Send prompt, return a validated NarrationOutput."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
#  Gemini Client (real)
# ─────────────────────────────────────────────────────────────────────────────

class GeminiClient:
    """
    Real Gemini client using google-genai SDK.
    Enforces structured JSON output matching NarrationOutput schema.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
    ) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai not installed. Run: uv add google-genai"
            ) from exc

        self._genai = genai
        self._types = types
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> NarrationOutput:
        """Call Gemini with structured JSON output enforced via response_schema."""
        import typing

        # Build the response schema as a Pydantic model compatible dict
        response_schema = self._types.Schema(
            type=self._types.Type.OBJECT,
            properties={
                "sentence_count": self._types.Schema(
                    type=self._types.Type.INTEGER,
                    description="Number of sentences (2–4)",
                ),
                "narration": self._types.Schema(
                    type=self._types.Type.STRING,
                    description="2–4 sentence ecosystem narration",
                ),
                "anomalies_detected": self._types.Schema(
                    type=self._types.Type.ARRAY,
                    items=self._types.Schema(type=self._types.Type.STRING),
                    description="List of anomalies detected",
                ),
                "confidence": self._types.Schema(
                    type=self._types.Type.NUMBER,
                    description="Confidence score 0.0–1.0",
                ),
            },
            required=["sentence_count", "narration", "anomalies_detected", "confidence"],
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.4,
                max_output_tokens=512,
            ),
        )

        raw_text = response.text.strip()
        logger.debug("Raw Gemini response: %s", raw_text)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemini returned non-JSON output: {raw_text[:200]}"
            ) from exc

        return NarrationOutput(**data)


# ─────────────────────────────────────────────────────────────────────────────
#  Mock Client
# ─────────────────────────────────────────────────────────────────────────────

class MockClient:
    """
    Hardcoded mock that returns a valid NarrationOutput instantly.

    Prints a bold red warning banner so it's impossible to miss in the
    terminal that this is a mock response.
    """

    _MOCK_OUTPUT = NarrationOutput(
        sentence_count=3,
        narration=(
            "The agricultural sensor grid recorded a significant soil moisture decline "
            "today, with Zone-A dropping 18.8% and Zone-B dropping 18.8% over a 4.5-hour "
            "window, triggering automated drone deployments and irrigation responses in both "
            "critical zones. Zone-C remained stable with a gradual 10.9% moisture reduction "
            "and no intervention required. "
            "Overall, the ecosystem activated its automated stabilization protocols "
            "successfully, with confidence that stress levels will normalize within the next "
            "monitoring cycle."
        ),
        anomalies_detected=[
            "Zone-A moisture dropped 18.8% (critical: dipped below 55%)",
            "Zone-B moisture dropped 18.8% (critical: dipped below 55%)",
            "5 total drone deployments across critical zones",
            "2 irrigation events triggered by automated soil-stress response",
        ],
        confidence=0.91,
    )

    def generate(self, prompt: str) -> NarrationOutput:  # noqa: ARG002
        self._print_mock_warning()
        return self._MOCK_OUTPUT

    @staticmethod
    def _print_mock_warning() -> None:
        warning = Text()
        warning.append("⚠  MOCK MODE ACTIVE  ⚠", style="bold red blink")
        warning.append(
            "\n\nNo GEMINI_API_KEY found in environment.\n"
            "Returning hardcoded mock NarrationOutput.\n"
            "Set GEMINI_API_KEY in your .env file to use the real Gemini API.",
            style="yellow",
        )
        console.print(
            Panel(
                warning,
                title="[bold red]Mock Client Warning[/bold red]",
                border_style="red",
                padding=(1, 4),
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Data loader
# ─────────────────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> EcosystemDataset:
    """Parse and validate a CSV file into an EcosystemDataset."""
    raw = path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(raw))
    events: list[EcosystemEvent] = []
    for row in reader:
        events.append(
            EcosystemEvent(
                timestamp=row["timestamp"],
                sensor_zone=row["sensor_zone"],
                soil_moisture_pct=float(row["soil_moisture_pct"]),
                drone_active=row["drone_active"].strip().lower() == "true",
                crop_health_index=float(row["crop_health_index"]),
                irrigation_triggered=row["irrigation_triggered"].strip().lower() == "true",
                temperature_celsius=float(row["temperature_celsius"]),
                rainfall_mm=float(row.get("rainfall_mm", 0.0)),
            )
        )
    return EcosystemDataset(events=events, source_file=str(path))


# ─────────────────────────────────────────────────────────────────────────────
#  Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class EcosystemNarrator:
    """
    Orchestrates the full pipeline:
      load → validate → analyze → enrich prompt → LLM → validate output

    The client is injected via constructor (dependency injection), enabling
    easy testing with MockClient or any future alternative LLM backend.
    """

    MIN_SENTENCES = 2
    MAX_SENTENCES = 4

    def __init__(self, client: LLMClientProtocol | None = None) -> None:
        if client is None:
            client = self._auto_select_client()
        self.client = client

    @staticmethod
    def _auto_select_client() -> LLMClientProtocol:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key and api_key != "your_api_key_here":
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            logger.info("Using GeminiClient with model=%s", model)
            return GeminiClient(api_key=api_key, model=model)
        logger.warning("GEMINI_API_KEY not set — falling back to MockClient")
        return MockClient()

    def narrate(self, dataset: EcosystemDataset) -> tuple[NarrationOutput, AnalysisInsights]:
        """
        Full pipeline: dataset → statistical analysis → prompt → LLM → output.

        Returns:
            (NarrationOutput, AnalysisInsights) — both validated Pydantic models
        """
        insights = analyze_dataset(dataset)
        prompt = self._build_prompt(insights, dataset)
        logger.debug("Prompt sent to LLM:\n%s", prompt)
        output = self.client.generate(prompt)
        return output, insights

    def _build_prompt(
        self, insights: AnalysisInsights, dataset: EcosystemDataset
    ) -> str:
        bullet_str = "\n".join(f"• {b}" for b in insights.summary_bullets)

        # Last 5 events snapshot as compact JSON
        recent = sorted(dataset.events, key=lambda e: e.timestamp)[-5:]
        snapshot_lines = []
        for e in recent:
            snapshot_lines.append(
                f"  {e.timestamp.strftime('%H:%M')} | {e.sensor_zone} | "
                f"moisture={e.soil_moisture_pct:.1f}% | "
                f"health={e.crop_health_index:.1f} | "
                f"drone={'YES' if e.drone_active else 'no'} | "
                f"irrigation={'YES' if e.irrigation_triggered else 'no'}"
            )
        snapshot_str = "\n".join(snapshot_lines)

        # Tone register is auto-derived from severity score — no user input needed
        tone_register = insights.tone_register
        tone_instruction = TONE_INSTRUCTIONS.get(tone_register, TONE_INSTRUCTIONS["routine"])

        return PROMPT_TEMPLATE.format(
            bullets=bullet_str,
            snapshot=snapshot_str,
            min_s=self.MIN_SENTENCES,
            max_s=self.MAX_SENTENCES,
            tone_instruction=tone_instruction,
            severity_score=insights.severity_score,
        )
