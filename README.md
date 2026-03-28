# entry-test

> **Gemini-Powered Agricultural Ecosystem Narration System**
> GSoC '26 Entry Task — CatRobot Organization

A production-quality pipeline that ingests agricultural sensor data (soil moisture, drone activity, crop health, irrigation events) and produces a **deterministic 2–4 sentence natural-language narration** powered by the Gemini API.

---

## ✨ Key Features

- **Robust Data Validation**: Utilizes strict Pydantic v2 schemas to ensure data integrity before processing.
- **Statistical Pre-processing**: Computes mathematical insights and trends in `analyzer.py` to provide the LLM with concrete data, minimizing hallucinations.
- **Deterministic Output**: Enforces exact sentence counts and JSON structures using Gemini's `response_schema` and Pydantic validators.
- **Procedural Scenarios**: Includes a built-in physics-consistent scenario generator representing different ecosystem states (normal, drought, crisis, recovery) with simulated causal effects.
- **Seamless Mock Mode**: Automatically falls back to a deterministic mock client if an API key is missing or quotas are exceeded, ensuring the application remains testable and interactive.
- **Modern Full-Stack Architecture**: Powered by a FastAPI backend and a React/Vite frontend with Web Worker off-thread CSV parsing to maintain a fluid user experience.

---

## 📁 Project Structure

```
entry_test/
├── ecosystem_narrator/          # Core Python package
│   ├── __init__.py
│   ├── models.py                # Pydantic v2 schemas
│   ├── analyzer.py              # Statistical pre-processing engine
│   ├── narrator.py              # EcosystemNarrator + GeminiClient + MockClient
│   ├── scenario_generator.py    # Procedural dataset generator
│   ├── cli.py                   # Rich-powered CLI
│   └── api.py                   # FastAPI backend
├── frontend/                    # React + Vite + Tailwind dashboard
│   └── src/
│       ├── workers/csvParser.worker.js   # Web Worker (off-thread CSV parsing)
│       └── components/
├── data/
│   ├── agro_ecosystem_sample.csv        # Multi-zone sample dataset
│   └── generated_crisis.csv             # Procedurally generated crisis dataset
├── pyproject.toml               # uv project file
├── .env.example                 # Environment variable template
├── PROMPT.md                    # Prompt engineering documentation
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (install below)
- Node.js 18+ (for frontend only)

### 1. Install `uv`

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone & Install

```bash
cd entry_test
uv sync
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🖥️ CLI Usage

```bash
# Basic usage (real Gemini API)
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv

# Force mock mode (no API key required)
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv --mock

# Skip the data table (faster)
uv run python -m ecosystem_narrator.cli \
  --data data/agro_ecosystem_sample.csv \
  --no-table
```

### CLI Output Preview

The terminal renders:
- 📊 **Data table** — Color-coded by moisture/health thresholds
- 📈 **Per-zone insight panels** — Moisture delta, drone count, anomaly flags
- ⚠ **Global anomaly list** — Cross-zone observations
- 🌿 **Narration panel** — Markdown-rendered AI summary
- Metadata: sentence count, confidence, generation time

---

## 🌐 API Server

```bash
uv run uvicorn ecosystem_narrator.api:app --reload --host 127.0.0.1 --port 8000
```

Interactive docs: **http://127.0.0.1:8000/docs**

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check + Gemini config status |
| `POST` | `/api/narrate` | JSON events → NarrationOutput + Insights |
| `POST` | `/api/analyze` | JSON events → AnalysisInsights (no LLM) |
| `POST` | `/api/upload-csv` | Upload CSV file → NarrationOutput |
| `GET` | `/api/scenarios` | List available procedural scenarios |
| `GET` | `/api/scenario/{type}`| Generate procedural scenario data + Narration |

---

## 🖼️ Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Frontend Features
- **File Upload** — Drag & drop your CSV or use the provided test datasets.
- **Web Worker** — CSV parsing runs off the main thread via `csvParser.worker.js`, keeping the UI completely non-blocking (a deliberate performance architecture choice).
- **Interactive Scenarios** — Procedurally generate different agricultural scenarios (Normal, Drought, Crisis, Recovery) with a single click.
- **Dynamic Dashboard** — Real-time visualization of moisture trends, drone deployments, and health indices per zone.
- **Narration Card** — Clean presentation of the generated narrative and architectural insights.

---

## 🏗️ Architecture Deep-Dive

### Phase 1 — Data Validation (`models.py`)
Pydantic v2 validates every field strictly:
- `soil_moisture_pct`: Must be 0.0–100.0
- `crop_health_index`: Must be 0.0–10.0
- `sentence_count`: Cross-validated against actual sentence count in narration

### Phase 2 — Statistical Pre-Processing (`analyzer.py`)
Extracts raw insights before any LLM call:
- Per-zone moisture trends & drop rates.
- Drone spike detection (threshold: ≥3 deployments).
- Critical zone detection (<55% moisture).
- Irrigation correlation analysis.
- Summary bullets injected directly into the prompt.

### Phase 3 — Deterministic LLM Generation (`narrator.py`)
Utilizes `google-genai` SDK and explicit structured output configuration:
- Adjusts language register (routine, advisory, emergency) dynamically based on an auto-derived severity score.
- Enforces maximum output constraints and exact JSON schemas.
- Auto-selects `GeminiClient` or `MockClient` gracefully based on environment variables.

---

## 📄 License

MIT — see [LICENSE](LICENSE)
