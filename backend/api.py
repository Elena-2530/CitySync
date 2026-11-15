
import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.scenario_simulation_agent import simulate_scenario
from services.geocoding import build_search_query, search_nominatim
from services.database import init_db, get_connection
from services.social_collector import start_collector


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citysync.api")

collector_task = None


app = FastAPI(
    title="CitySync API",
    description="API per simulazione e monitoraggio urbano CitySync",
    version="1.3.0",
)


# ---------------------------------------------------------
# CORS
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
        "https://whimsical-paprenjak-fda1db.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# AVVIO E ARRESTO DEL MONITORAGGIO
# ---------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global collector_task

    init_db()
    logger.info("Database CitySync inizializzato.")

    collector_task = asyncio.create_task(start_collector())

    logger.info("Monitoraggio Bluesky avviato.")


@app.on_event("shutdown")
async def shutdown_event():
    global collector_task

    if collector_task:
        collector_task.cancel()

        with suppress(asyncio.CancelledError):
            await collector_task

        collector_task = None

    logger.info("Monitoraggio CitySync arrestato.")


# ---------------------------------------------------------
# MODELLI
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
# FUNZIONI DI SUPPORTO MONITORAGGIO
# ---------------------------------------------------------

def get_event_guidance(event_type, verification_status):
    event_type = (event_type or "").casefold()

    guidance = {
        "mobility": [
            "Evita, se possibile, il tratto stradale interessato.",
            "Controlla gli aggiornamenti dei gestori del trasporto e delle autorità locali."
        ],
        "environment": [
            "Evita di avvicinarti all'area segnalata.",
            "Segui gli aggiornamenti della Protezione Civile e delle autorità locali."
        ],
        "civil_protection": [
            "Non avvicinarti all'area potenzialmente interessata.",
            "Segui esclusivamente le indicazioni delle autorità competenti."
        ],
        "tourism": [
            "Verifica eventuali comunicazioni degli organizzatori.",
            "Controlla gli aggiornamenti sulla viabilità e sull'accessibilità dell'area."
        ]
    }

    result = guidance.get(event_type, [
        "Verifica la segnalazione attraverso fonti ufficiali.",
        "Segui gli aggiornamenti delle autorità locali."
    ])

    if verification_status == "unverified":
        result.insert(
            0,
            "La segnalazione non è ancora verificata: non considerarla una conferma dell'evento."
        )

    elif verification_status == "partially_confirmed":
        result.insert(
            0,
            "Sono presenti riscontri parziali. La situazione richiede ulteriori verifiche."
        )

    elif verification_status == "conflicting":
        result.insert(
            0,
            "Le fonti disponibili sono in conflitto. La situazione non è conclusiva."
        )

    elif verification_status in ("contested", "contradicted"):
        result.insert(
            0,
            "Le informazioni disponibili contestano la segnalazione."
        )

    return result


def verification_label(status):
    labels = {
        "unverified": "Segnalazione da verificare",
        "partially_confirmed": "Riscontri parziali",
        "confirmed": "Evento confermato",
        "contested": "Segnalazione contestata",
        "contradicted": "Segnalazione contraddetta",
        "conflicting": "Fonti in conflitto"
    }

    return labels.get(status, "Stato non disponibile")


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "application": "CitySync",
        "status": "online",
        "message": "Backend disponibile"
    }


# ---------------------------------------------------------
# GEOCODIFICA
# ---------------------------------------------------------

@app.get("/api/geocode")
def geocode_location(
    q: str = Query(..., min_length=2)
):
    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Inserisci una località valida."
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
                "osm_id": item.get("osm_id")
            })

        return {
            "query": query,
            "count": len(candidates),
            "results": candidates,
            "source": "OpenStreetMap Nominatim"
        }

    except Exception:
        logger.exception("Errore geocodifica.")

        raise HTTPException(
            status_code=503,
            detail="Servizio di geolocalizzazione non disponibile."
        )


# ---------------------------------------------------------
# SIMULAZIONE IPOTETICA
# ---------------------------------------------------------

@app.post("/api/scenarios/analyze")
def analyze_scenario(scenario: ScenarioRequest):
    scenario_id = str(uuid4())

    scenario_data = scenario.dict()

    location_data = {
        "name": scenario.location.name,
        "display_name": scenario.location.display_name,
        "latitude": scenario.location.latitude,
        "longitude": scenario.location.longitude,
        "osm_type": scenario.location.osm_type,
        "osm_id": scenario.location.osm_id
    }

    try:
        simulation_result = simulate_scenario(
            description=scenario.description,
            location=location_data
        )

        return {
            "scenario_id": scenario_id,
            "status": "completed",
            "message": "Simulazione ipotetica completata.",
            "simulation": simulation_result,
            "scenario": scenario_data
        }

    except Exception:
        logger.exception("Errore durante la simulazione.")

        raise HTTPException(
            status_code=500,
            detail="Errore durante l'elaborazione della simulazione."
        )


# ---------------------------------------------------------
# MONITORAGGIO EVENTI REALI
# ---------------------------------------------------------

@app.get("/api/monitoring/events")
def get_monitoring_events():
    """
    Restituisce gli incidenti recenti raccolti da Bluesky.

    Le segnalazioni social non sono automaticamente eventi
    confermati: viene restituito il loro stato di verifica.
    """

    connection = get_connection()

    try:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=24)
        ).isoformat()

        rows = connection.execute(
            """
            SELECT
                i.id,
                i.event_type,
                i.description,
                i.location,
                i.latitude,
                i.longitude,
                i.priority,
                i.verification_status,
                i.created_at,
                i.updated_at,
                COUNT(sr.id) AS report_count,
                MAX(sr.received_at) AS last_report_at
            FROM incidents i
            INNER JOIN social_reports sr
                ON sr.incident_id = i.id
            WHERE i.status = 'open'
            AND sr.received_at >= ?
            GROUP BY i.id
            ORDER BY last_report_at DESC
            LIMIT 30
            """,
            (cutoff,)
        ).fetchall()

        events = []

        for row in rows:
            status = row["verification_status"] or "unverified"

            events.append({
                "id": row["id"],
                "event_type": row["event_type"],
                "description": row["description"],
                "location": row["location"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "priority": row["priority"],
                "verification_status": status,
                "verification_label": verification_label(status),
                "report_count": row["report_count"],
                "created_at": row["created_at"],
                "last_report_at": row["last_report_at"],
                "source": "Bluesky - segnalazioni social",
                "guidance": get_event_guidance(
                    row["event_type"],
                    status
                )
            })

        return {
            "status": "ok",
            "source": "Bluesky",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "count": len(events),
            "events": events
        }

    except Exception:
        logger.exception("Errore recupero eventi monitoraggio.")

        raise HTTPException(
            status_code=500,
            detail="Impossibile recuperare gli eventi monitorati."
        )

    finally:
        connection.close()
