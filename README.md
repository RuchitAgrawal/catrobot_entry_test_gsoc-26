# entry-test

> **Gemini-Powered Agricultural Ecosystem Narration System**  
> GSoC '26 Entry Task — CatRobot Organization

A pipeline that ingests agricultural sensor data (soil moisture, drone activity, crop health,
irrigation events) and produces a deterministic 2–4 sentence natural-language narration
powered by the Gemini API.

---

## Features

- **Strict data validation** via Pydantic v2 schemas (field ranges, cross-validators)
- **Statistical pre-processing** in `analyzer.py` — moisture trends, drone spike detection,
  irrigation correlation — computed before any LLM call to prevent hallucinated numbers
- **Structured output enforcement** using Gemini's `response_schema` + a Pydantic
  `@model_validator` that auto-corrects sentence count if it drifts
- **Severity-adaptive tone** — routine / advisory / emergency register derived automatically
  from a composite score, not from a user dropdown
- **Procedural scenario generator** — four physics-consistent scenarios (normal, drought,
  crisis, recovery) for offline testing without a real sensor feed
- **Mock mode** — falls back to a hardcoded response if no API key is present, with a
  clearly visible terminal warning banner
- **Full-stack demo** — FastAPI backend + React/Vite frontend with off-thread CSV parsing
  via a Web Worker

---

## Project Structure

```
entry_test/
├── ecosystem_narrator/          # Core Python package
│   ├── __init__.py
│   ├── models.py                # Pydantic v2 schemas
│   ├── analyzer.py              # Statistical pre-processing
│   ├── narrator.py              # GeminiClient, MockClient, EcosystemNarrator
│   ├── scenario_generator.py    # Procedural dataset generator
│   ├── cli.py                   # Rich-powered CLI
│   ├── api.py                   # FastAPI backend
│   └── report_generator.py      # Self-contained HTML report with SVG charts
├── frontend/                    # React + Vite + Tailwind dashboard
│   └── src/
│       ├── workers/csvParser.worker.js
│       └── components/
├── data/
│   ├── agro_ecosystem_sample.csv
│   └── generated_crisis.csv
├── tests/
│   └── test_analyzer.py
├── pyproject.toml
├── .env.example
├── PROMPT.md
└── README.md
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ (for the frontend)

### Install

```bash
# Install uv (Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
cd entry_test
uv sync
```

### Configure

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## CLI

```bash
# Run on a CSV file
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv

# Force mock mode (no API key needed)
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv --mock

# Generate a scenario without a file
uv run python -m ecosystem_narrator.cli --generate-scenario drought

# Export an HTML report
uv run python -m ecosystem_narrator.cli \
  --data data/agro_ecosystem_sample.csv --export-report report.html

# Watch mode — re-narrates on every file save
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv --watch
```

The CLI outputs a color-coded data table, per-zone insight panels, global anomaly list,
and the AI narration card using Rich.

---

## API Server

```bash
uv run uvicorn ecosystem_narrator.api:app --reload --host 127.0.0.1 --port 8000
```

Interactive docs: **http://127.0.0.1:8000/docs**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check + Gemini config status |
| `POST` | `/api/narrate` | JSON events → NarrationOutput + Insights |
| `POST` | `/api/analyze` | JSON events → AnalysisInsights (no LLM) |
| `POST` | `/api/upload-csv` | CSV file upload → NarrationOutput |
| `GET` | `/api/scenarios` | List procedural scenario types |
| `GET` | `/api/scenario/{type}` | Generate scenario + run narration |

---

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

Drag-and-drop a CSV or click one of the scenario buttons for an instant demo.
CSV parsing runs in a Web Worker so the main thread stays unblocked.

---

## Tests

```bash
uv run pytest tests/ -v
```

Tests cover moisture delta computation, critical zone detection, drone/irrigation counting,
and the composite severity score, all using hardcoded fixtures (no API calls needed).

---

## How it works

**Phase 1 — Validation** (`models.py`)  
Pydantic v2 validates every field: `soil_moisture_pct` must be 0–100,
`crop_health_index` 0–10, and `sentence_count` is cross-validated against the
actual sentence count in the narration string.

**Phase 2 — Pre-processing** (`analyzer.py`)  
Before any LLM call: per-zone moisture trends and drop rates, drone spike detection
(threshold ≥ 3 deployments), critical zone detection (< 55% moisture), irrigation
correlation, and a composite severity score that determines tone register.

**Phase 3 — Narration** (`narrator.py`)  
The prompt is built from the pre-computed bullets and sent to Gemini with a
`response_schema` that enforces valid JSON. A `@model_validator` in `NarrationOutput`
catches any sentence-count drift and corrects it automatically.

---

## License

MIT
