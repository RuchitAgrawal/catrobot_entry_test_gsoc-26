# 🌾 Ecosystem Narrator

> **Gemini-Powered Agricultural Ecosystem Narration System**
> GSoC '26 Entry Task — CatRobot Organization

A production-quality pipeline that ingests agricultural sensor data (soil moisture, drone
activity, crop health, irrigation events) and produces a **deterministic 2–4 sentence
natural-language narration** powered by the Gemini API.

---

## ✨ What Makes This Different

| Feature | This Project |
|---|---|
| **Theme** | Automated Agricultural Ecosystem (not marine life) |
| **Data validation** | Pydantic v2 strict schemas — not raw CSV string parsing |
| **Math** | Pre-computed by `analyzer.py` before any LLM call |
| **Sentence enforcement** | JSON schema + `response_schema` SDK + Pydantic validator |
| **Fallback** | `MockClient` with color-coded terminal warning |
| **Dependency mgmt** | `uv` + `pyproject.toml` (production-ready) |
| **CLI** | Rich tables, per-zone panels, markdown narration |
| **Backend** | FastAPI with `/narrate`, `/analyze`, `/upload-csv` |
| **Frontend** | React + Vite + Tailwind + **Web Worker CSV parsing** |

---

## 📁 Project Structure

```
entry_test/
├── ecosystem_narrator/          # Core Python package
│   ├── __init__.py
│   ├── models.py                # Pydantic v2 schemas
│   ├── analyzer.py              # Statistical pre-processing engine
│   ├── narrator.py              # EcosystemNarrator + GeminiClient + MockClient
│   ├── cli.py                   # Rich-powered CLI
│   └── api.py                   # FastAPI backend
├── frontend/                    # React + Vite + Tailwind dashboard
│   └── src/
│       ├── workers/csvParser.worker.js   # Web Worker (off-thread CSV parsing)
│       └── components/
├── data/
│   └── agro_ecosystem_sample.csv        # 30-row sample dataset
├── sample_outputs/
│   └── sample_narration.json            # Pre-generated output (no API key needed)
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
GEMINI_MODEL=gemini-2.0-flash
```

---

## 🖥️ CLI Usage

```bash
# Basic usage (real Gemini API)
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv

# Force mock mode (no API key required)
uv run python -m ecosystem_narrator.cli --data data/agro_ecosystem_sample.csv --mock

# Save output to JSON
uv run python -m ecosystem_narrator.cli \
  --data data/agro_ecosystem_sample.csv \
  --output sample_outputs/my_narration.json

# Skip the data table (faster)
uv run python -m ecosystem_narrator.cli \
  --data data/agro_ecosystem_sample.csv \
  --no-table
```

### CLI Output Preview

The terminal renders:
- 📊 **Data table** — color-coded by moisture/health thresholds
- 📈 **Per-zone insight panels** — moisture delta, drone count, anomaly flags
- ⚠ **Global anomaly list** — cross-zone observations
- 🌿 **Narration panel** — markdown-rendered AI summary
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

### Example: POST /api/narrate

```bash
curl -X POST http://127.0.0.1:8000/api/narrate \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "timestamp": "2024-06-15T10:00:00",
        "sensor_zone": "Zone-A",
        "soil_moisture_pct": 53.4,
        "drone_active": true,
        "crop_health_index": 7.3,
        "irrigation_triggered": true,
        "temperature_celsius": 30.5,
        "rainfall_mm": 0.0
      }
    ]
  }'
```

---

## 🖼️ Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Frontend Features
- **File Upload** — drag & drop your CSV
- **Web Worker** — CSV parsing runs off the main thread via `csvParser.worker.js`, keeping the UI completely non-blocking (a deliberate performance architecture choice)
- **Stats Panel** — moisture trend, drone count, health index per zone
- **Narration Card** — animated reveal of the AI narration
- **Mock indicator** — badge shown when running without API key

---

## 🤖 Mock Mode (No API Key Needed)

If `GEMINI_API_KEY` is not set (or is the placeholder value), the system **automatically**
switches to `MockClient`. You'll see a bold red warning in the terminal:

```
╭─────────────────────────────────────────╮
│          Mock Client Warning            │
│                                         │
│  ⚠  MOCK MODE ACTIVE  ⚠                │
│                                         │
│  No GEMINI_API_KEY found. Returning     │
│  hardcoded mock NarrationOutput.        │
╰─────────────────────────────────────────╯
```

The `sample_outputs/sample_narration.json` file contains a pre-generated output you can
inspect without running anything.

---

## 🏗️ Architecture Deep-Dive

### Phase 1 — Data Validation (models.py)
Pydantic v2 validates every field strictly:
- `soil_moisture_pct`: must be 0.0–100.0
- `crop_health_index`: must be 0.0–10.0
- `sentence_count`: cross-validated against actual sentence count in narration

### Phase 2 — Pre-Processing (analyzer.py)
Before any LLM call:
- Per-zone moisture trend & drop rate (per hour)
- Drone spike detection (threshold: ≥3 deployments)
- Crop health delta, critical zone detection (<55% moisture)
- Irrigation correlation analysis
- Summary bullets injected directly into the prompt

### Phase 3 — Deterministic LLM (narrator.py)
```
LLMClientProtocol (Protocol)
    ├── GeminiClient   →  response_schema enforcement + temperature=0.4
    └── MockClient     →  hardcoded valid NarrationOutput + color warning
```
Auto-selects based on `.env` — no code changes needed.

### Phase 4 — CLI + API + Frontend
- **CLI**: `rich` tables, panels, spinners, markdown
- **API**: FastAPI, async, CORS-configured for Vite dev server
- **Frontend**: React + Vite + Tailwind, Web Worker handles CSV parsing
  off the main thread → non-blocking UI → reduced server load

---

## 📤 Sample Output

See `sample_outputs/sample_narration.json` for a full example. Narration excerpt:

> *"The agricultural sensor grid recorded a significant soil moisture decline today,
> with Zone-A dropping 13.8% and Zone-B dropping 13.0% over a 4.5-hour monitoring
> window, triggering automated drone deployments and irrigation responses in both
> critical zones. Zone-C remained stable with a moderate 10.9% moisture reduction
> and no automated intervention required. Overall, the ecosystem's automated
> stabilization protocols responded effectively to the dual-zone stress event."*

---

## 📄 License

MIT — see [LICENSE](LICENSE)
