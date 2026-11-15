
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.geocoding import (
    build_search_query,
    search_nominatim,
)


app = FastAPI(
    title="CitySync API",
    description="API per la geolocalizzazione e il coordinamento degli agenti CitySync",
    version="1.1.0",
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
# 2. MODELLI DATI DELLO SCENARIO
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

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Servizio di geolocalizzazione non disponibile: {error}",
        )


# ---------------------------------------------------------
# 5. RICEZIONE SCENARI PER JANARA
# ---------------------------------------------------------

@app.post("/api/scenarios/analyze")
def analyze_scenario(scenario: ScenarioRequest):
    """
    Riceve e valida uno scenario.
    Prepara i dati per il successivo coordinamento di Janara.
    In questa fase non avvia ancora gli agenti AI.
    """

    scenario_id = str(uuid4())

    scenario_data = scenario.dict()

    return {
        "scenario_id": scenario_id,
        "status": "received",
        "message": "Scenario ricevuto e validato correttamente.",
        "janara": {
            "status": "pending",
            "message": "Richiesta pronta per il coordinamento.",
        },
        "scenario": scenario_data,
    }
