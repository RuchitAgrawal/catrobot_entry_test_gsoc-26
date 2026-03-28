# Prompt Engineering Documentation

## Overview

This document describes the exact prompt template used by the Ecosystem Narrator,
the design rationale behind each decision, and why this approach produces reliable,
hallucination-resistant narrations.

---

## Core Design Principle: Pre-Computed Context

The most common failure mode of LLM summarization is **numeric hallucination** — the model
inventing plausible-sounding statistics that don't match the source data. To eliminate this,
we follow a two-step pipeline:

1. **`analyzer.py`** runs pure-Python statistics on the dataset _before_ any API call
2. The computed insights are injected into the prompt as **ground truth bullets**
3. The model is explicitly instructed _not to invent numbers_

This means the LLM is acting as a **language layer**, not a math layer.

---

## The Prompt Template

```
You are an expert agricultural ecosystem analyst monitoring a smart sensor grid.
Your task is to write a concise, accurate narration of today's ecosystem health.

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
{
  "sentence_count": <integer 2–4>,
  "narration": "<your 2–4 sentence narration here>",
  "anomalies_detected": ["<anomaly 1>", "<anomaly 2>"],
  "confidence": <float 0.0–1.0>
}
```

---

## Template Variables

| Variable | Source | Description |
|---|---|---|
| `{bullets}` | `analyzer.py → AnalysisInsights.summary_bullets` | Pre-computed bullet list of moisture trends, drone activity, anomaly flags |
| `{snapshot}` | Last 5 events from `EcosystemDataset.events` | Raw tabular snapshot of recent readings |
| `{min_s}` | `EcosystemNarrator.MIN_SENTENCES` (= 2) | Lower bound |
| `{max_s}` | `EcosystemNarrator.MAX_SENTENCES` (= 4) | Upper bound |

---

## Enforcement Stack (Why 2–4 Sentences is Guaranteed)

A naive prompt asking for "2-4 sentences" will occasionally produce 1 or 5. We use
three layers of enforcement:

### Layer 1 — Prompt Instruction
The prompt explicitly states "EXACTLY 2–4 sentences" twice and includes it as a numbered rule.

### Layer 2 — Structured Output Schema
We use the `google-genai` SDK's `response_schema` feature with `response_mime_type="application/json"`.
This forces the model to output a valid JSON object matching the `NarrationOutput` schema —
it cannot return free-form text.

### Layer 3 — Pydantic Validator
`NarrationOutput` has a `@model_validator` that counts actual sentences in the narration
string using regex splitting on `.!?` and auto-corrects `sentence_count` if it drifts.

---

## Example Input → Output

### Input Bullets (from analyzer.py)
```
• Overall soil moisture trend: DECLINING (mean change: -12.6% over 4.5h)
• Zone-A: moisture 72.4% → 58.6% (-13.8%), crop health mean 7.8/10, peak temp 30.8°C
• Zone-B: moisture 68.1% → 55.1% (-13.0%), crop health mean 7.3/10, peak temp 30.6°C
• Zone-C: moisture 80.3% → 69.4% (-10.9%), crop health mean 8.3/10, peak temp 30.4°C
• CRITICAL: Zones Zone-A, Zone-B dropped below 55.0% moisture
• Total drone deployments: 9 — automated stress-response protocol active
• Irrigation system triggered 4 time(s) — ecosystem attempting to self-stabilize
```

### Output JSON
```json
{
  "sentence_count": 3,
  "narration": "The agricultural sensor grid recorded a significant soil moisture decline today, with Zone-A dropping 13.8% and Zone-B dropping 13.0% over a 4.5-hour monitoring window, triggering automated drone deployments and irrigation responses in both critical zones. Zone-C remained stable with a moderate 10.9% moisture reduction and no automated intervention required, maintaining a crop health index above 8.0 throughout. Overall, the ecosystem's automated stabilization protocols responded effectively to the dual-zone stress event, and moisture levels are projected to normalize within the next monitoring cycle.",
  "anomalies_detected": [
    "Zone-A moisture dropped 13.8% — fell below 55% critical threshold",
    "Zone-B moisture dropped 13.0% — fell below 55% critical threshold",
    "9 total drone deployments triggered by soil stress protocol",
    "4 irrigation events activated in response to critical moisture levels"
  ],
  "confidence": 0.93
}
```

---

## Why This Design Wins Over a Naive Implementation

| Naive Approach | This Implementation |
|---|---|
| Raw CSV string dumped into prompt | Statistical insights pre-computed, injected as ground truth |
| "Write 2-4 sentences" in system prompt | JSON schema enforcement + Pydantic validator |
| `requirements.txt` | `pyproject.toml` with `uv` |
| Single script | Modular package: models → analyzer → narrator → cli/api |
| No fallback | MockClient with color-coded terminal warning |
| Script only | FastAPI backend + React dashboard + Web Worker |
