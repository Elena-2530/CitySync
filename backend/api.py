
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.geocoding import (
    build_search_query,
    search_nominatim,
)

from agents.janara_orchestrator_agent import handle_request


app = FastAPI(
    title="CitySync API",
    description="API per la geolocalizzazione e il coordinamento degli agenti CitySync",
    version="1.2.0",
)


# ---------------------------------------------------------
# 1. CONFIGURAZIONE CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:2222",
        "http://localhost:2222",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# 2. MODELLI DATI
# ---------------------------------------------------------

class ScenarioLocation(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=500)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    osm_type: str | None = None
    osm_id: int | None = None


class ScenarioRequest(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    location: ScenarioLocation


# ---------------------------------------------------------
# 3. ENDPOINT PRINCIPALE
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "application": "CitySync",
        "status": "online",
        "message": "Backend disponibile",
    }


# ---------------------------------------------------------
# 4. GEOCODIFICA
# ---------------------------------------------------------

@app.get("/api/geocode")
def geocode_location(
    q: str = Query(
        ...,
        min_length=2,
        description="Via, indirizzo, quartiere o città da cercare",
    )
):
    """
    Cerca una località e restituisce le possibili corrispondenze.
    Non seleziona automaticamente il primo risultato.
    """

    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Inserisci una località valida.",
        )

    try:
        search_query = build_search_query(query)
        results = search_nominatim(search_query, limit=5)

        candidates = []

        for item in results:
            candidates.append({
                "name": item.get("name"),
                "display_name": item.get("display_name"),
                "latitude": float(item["lat"]),
                "longitude": float(item["lon"]),
                "type": item.get("type"),
                "category": item.get("category"),
                "osm_type": item.get("osm_type"),
                "osm_id": item.get("osm_id"),
            })

        return {
            "query": query,
            "count": len(candidates),
            "results": candidates,
            "source": "OpenStreetMap Nominatim",
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Servizio di geolocalizzazione non disponibile.",
        )


# ---------------------------------------------------------
# 5. ANALISI SCENARI CON JANARA
# ---------------------------------------------------------

@app.post("/api/scenarios/analyze")
def analyze_scenario(scenario: ScenarioRequest):
    """
    Riceve uno scenario dal frontend e lo inoltra a Janara.
    Janara coordina gli agenti specializzati e restituisce
    il risultato dell'analisi.
    """

    scenario_id = str(uuid4())

    scenario_data = scenario.dict()

    janara_request = {
        "request_id": scenario_id,
        "sender": "operator",
        "request_type": "question",
        "question": scenario.description,
        "context": {
            "location": scenario.location.display_name,
            "name": scenario.location.name,
            "latitude": scenario.location.latitude,
            "longitude": scenario.location.longitude,
            "osm_type": scenario.location.osm_type,
            "osm_id": scenario.location.osm_id,
        },
    }

    try:
        janara_result = handle_request(janara_request)

        janara_status = (
            janara_result.get("status", "unknown")
            if isinstance(janara_result, dict)
            else "unknown"
        )

        return {
            "scenario_id": scenario_id,
            "status": janara_status,
            "message": "Scenario elaborato da Janara.",
            "janara": janara_result,
            "scenario": scenario_data,
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Errore durante il coordinamento degli agenti da parte di Janara.",
        )
