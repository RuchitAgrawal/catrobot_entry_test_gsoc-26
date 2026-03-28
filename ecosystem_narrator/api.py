"""
api.py - FastAPI backend for the Ecosystem Narrator.

Endpoints:
  GET  /api/health          - health check + Gemini config status
  POST /api/narrate         - JSON events -> NarrationOutput + AnalysisInsights
  POST /api/analyze         - JSON events -> AnalysisInsights (no LLM call)
  POST /api/upload-csv      - CSV file upload -> NarrationOutput
  GET  /api/scenarios       - list available procedural scenario types
  GET  /api/scenario/{type} - generate a scenario and run the full pipeline

CORS is open for the Vite dev server on localhost:5173.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import EcosystemDataset, EcosystemEvent, NarrationOutput, AnalysisInsights
from .analyzer import analyze_dataset
from .narrator import EcosystemNarrator, MockClient, load_csv
from .scenario_generator import generate_scenario, SCENARIO_DESCRIPTIONS, ScenarioType

load_dotenv(override=True)

app = FastAPI(
    title="Ecosystem Narrator API",
    description="Gemini-Powered Agricultural Ecosystem Narration System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request / response models

class NarrateRequest(BaseModel):
    events: list[EcosystemEvent]
    source_file: str = "api_upload"
    force_mock: bool = False


class NarrateResponse(BaseModel):
    narration: NarrationOutput
    insights: AnalysisInsights
    mock_mode: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    gemini_configured: bool
    model: str


# Routes

@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check endpoint."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    configured = bool(api_key and api_key != "your_api_key_here")
    return HealthResponse(
        status="ok",
        version="0.1.0",
        gemini_configured=configured,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )


@app.post("/api/narrate", response_model=NarrateResponse, tags=["narration"])
async def narrate(request: NarrateRequest) -> NarrateResponse:
    """
    Full narration pipeline.

    Accepts a list of EcosystemEvent objects, runs statistical analysis,
    then returns an LLM-generated (or mock) NarrationOutput alongside
    the pre-computed AnalysisInsights.
    """
    if not request.events:
        raise HTTPException(status_code=400, detail="events list must not be empty")

    dataset = EcosystemDataset(
        events=request.events,
        source_file=request.source_file,
    )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    using_mock = request.force_mock or not (api_key and api_key != "your_api_key_here")

    client = MockClient() if using_mock else None
    narrator = EcosystemNarrator(client=client)

    try:
        output, insights = narrator.narrate(dataset)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Narration pipeline failed: {str(exc)}",
        ) from exc

    return NarrateResponse(
        narration=output,
        insights=insights,
        mock_mode=using_mock,
    )


@app.post("/api/analyze", response_model=AnalysisInsights, tags=["analysis"])
async def analyze(request: NarrateRequest) -> AnalysisInsights:
    """
    Statistics-only endpoint — runs the pre-processing engine without calling the LLM.
    Useful for the frontend to display insights before requesting narration.
    """
    if not request.events:
        raise HTTPException(status_code=400, detail="events list must not be empty")

    dataset = EcosystemDataset(
        events=request.events,
        source_file=request.source_file,
    )

    return analyze_dataset(dataset)


@app.post("/api/upload-csv", response_model=NarrateResponse, tags=["narration"])
async def upload_csv(file: UploadFile = File(...), force_mock: bool = False) -> NarrateResponse:
    """
    Upload a CSV file directly and receive a narration.
    The CSV is parsed server-side using the same Pydantic validation.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    import tempfile
    content = await file.read()
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="wb"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        dataset = load_csv(tmp_path)
        dataset = EcosystemDataset(
            events=dataset.events, source_file=file.filename or "upload.csv"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"CSV parsing failed: {str(exc)}"
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    using_mock = force_mock or not (api_key and api_key != "your_api_key_here")
    client = MockClient() if using_mock else None
    narrator = EcosystemNarrator(client=client)

    try:
        output, insights = narrator.narrate(dataset)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Narration failed: {str(exc)}"
        ) from exc

    return NarrateResponse(
        narration=output,
        insights=insights,
        mock_mode=using_mock,
    )


# Scenario endpoints

@app.get("/api/scenarios", tags=["scenarios"])
async def list_scenarios() -> dict:
    """List all available procedural scenario types with descriptions."""
    return {
        "scenarios": [
            {"type": k, "description": v}
            for k, v in SCENARIO_DESCRIPTIONS.items()
        ]
    }


@app.get("/api/scenario/{scenario_type}", response_model=NarrateResponse, tags=["scenarios"])
async def run_scenario(scenario_type: str, force_mock: bool = False) -> NarrateResponse:
    """
    Procedurally generate a scenario and run the full narration pipeline.
    No file upload required. Types: normal | drought | crisis | recovery
    """
    valid = {"normal", "drought", "crisis", "recovery"}
    if scenario_type not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{scenario_type}'. Valid: {sorted(valid)}",
        )

    dataset = generate_scenario(scenario_type)  # type: ignore[arg-type]

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    using_mock = force_mock or not (api_key and api_key != "your_api_key_here")
    client = MockClient() if using_mock else None
    narrator = EcosystemNarrator(client=client)

    try:
        output, insights = narrator.narrate(dataset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Narration failed: {str(exc)}") from exc

    return NarrateResponse(narration=output, insights=insights, mock_mode=using_mock)
