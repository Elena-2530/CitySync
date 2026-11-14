
import logging
from datetime import datetime, timezone

from services.database import get_connection

from agents.mobility.specialists import traffic_agent
from agents.mobility.specialists import public_transport_agent
from agents.mobility.specialists import route_planning_agent
from agents.mobility.specialists import mobility_impact_agent
from agents.mobility.specialists import mobility_assistance_agent


logger = logging.getLogger("neurapolis.mobility")


def load_incident(incident_id):
    """
    Recupera un incidente e le segnalazioni associate
    dal database NEURAPOLIS.
    """

    connection = get_connection()

    try:
        incident = connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,)
        ).fetchone()

        if incident is None:
            return None

        reports = connection.execute(
            """
            SELECT
                id,
                source,
                author_did,
                text,
                categories,
                locations,
                published_at,
                received_at
            FROM social_reports
            WHERE incident_id = ?
            ORDER BY published_at ASC
            """,
            (incident_id,)
        ).fetchall()

        return {
            "incident": dict(incident),
            "reports": [dict(report) for report in reports]
        }

    finally:
        connection.close()


def validate_request(request):
    """
    Controlla la struttura minima della richiesta.
    """

    if not isinstance(request, dict):
        raise ValueError("La richiesta deve essere un dizionario.")

    sender = request.get("sender")

    if sender not in ["janara", "user", "operator"]:
        raise ValueError(
            "Mittente non valido: janara, user oppure operator."
        )

    request_type = request.get("request_type")

    allowed_types = [
        "incident_analysis",
        "route_request",
        "question"
    ]

    if request_type not in allowed_types:
        raise ValueError("Tipologia di richiesta non riconosciuta.")

    if not isinstance(request.get("context") or {}, dict):
        raise ValueError("Il campo context deve essere un dizionario.")

    if request_type == "incident_analysis":
        if request.get("incident_id") is None:
            raise ValueError(
                "Per analizzare un incidente è necessario incident_id."
            )

    return True


def analyze_mobility_request(request):
    """
    Punto di ingresso del Mobility System.

    Riceve richieste da Janara, operatori e utenti.
    Attiva gli specialisti necessari.
    Integra i risultati e restituisce una risposta strutturata.
    """

    validate_request(request)

    request_id = request.get("request_id")
    sender = request["sender"]
    request_type = request["request_type"]

    context = request.get("context") or {}
    question = request.get("question")

    incident = None
    reports = []

    # --------------------------------------------------------
    # 1. RECUPERO DEI DATI DELL'INCIDENTE
    # --------------------------------------------------------

    incident_id = request.get("incident_id")

    if incident_id is not None:

        incident_data = load_incident(incident_id)

        if incident_data is None:
            return {
                "agent": "mobility_agent",
                "request_id": request_id,
                "status": "incident_not_found",
                "response": (
                    f"Non è stato trovato l'incidente {incident_id}."
                )
            }

        incident = incident_data["incident"]
        reports = incident_data["reports"]

    # --------------------------------------------------------
    # 2. ATTIVAZIONE DEGLI SPECIALISTI
    # --------------------------------------------------------

    traffic_result = None
    transport_result = None
    route_result = None
    impact_result = None

    if request_type == "incident_analysis":

        traffic_result = traffic_agent.analyze(
            incident,
            reports,
            context
        )

        transport_result = public_transport_agent.analyze(
            incident,
            reports,
            context
        )

        impact_result = mobility_impact_agent.analyze(
            incident,
            traffic_result,
            transport_result
        )

        # Il pianificatore viene attivato solo se
        # sono disponibili partenza e destinazione.
        if context.get("origin") and context.get("destination"):
            route_result = route_planning_agent.analyze(context)

    elif request_type == "route_request":

        transport_result = public_transport_agent.analyze(
            incident,
            reports,
            context
        )

        route_result = route_planning_agent.analyze(context)

    elif request_type == "question":

        question_text = (question or "").lower()

        if any(word in question_text for word in [
            "traffico", "incidente", "strada", "viabilità"
        ]):
            traffic_result = traffic_agent.analyze(
                incident,
                reports,
                context
            )

        if any(word in question_text for word in [
            "autobus", "bus", "tram", "metro",
            "metropolitana", "treno", "mezzi"
        ]):
            transport_result = public_transport_agent.analyze(
                incident,
                reports,
                context
            )

        if context.get("origin") and context.get("destination"):
            route_result = route_planning_agent.analyze(context)

        if incident:
            impact_result = mobility_impact_agent.analyze(
                incident,
                traffic_result or {},
                transport_result or {}
            )

    # --------------------------------------------------------
    # 3. VALUTAZIONE DELL'AFFIDABILITÀ E DELL'URGENZA
    # --------------------------------------------------------

    verification_status = (
        incident.get("verification_status")
        if incident else None
    )

    urgency = "not_assessed"
    urgency_reason = None

    if incident:

        description = (
            incident.get("description") or ""
        ).lower()

        urgent_terms = [
            "feriti",
            "crollo",
            "esplosione",
            "incendio",
            "fuga di gas",
            "strada completamente bloccata"
        ]

        if any(term in description for term in urgent_terms):
            urgency = "urgent_human_review"
            urgency_reason = (
                "La descrizione contiene elementi che richiedono "
                "una valutazione tempestiva da parte di un operatore."
            )

        else:
            urgency = "standard_review"

    # --------------------------------------------------------
    # 4. PREPARAZIONE DELLA RISPOSTA
    # --------------------------------------------------------

    response_result = mobility_assistance_agent.generate_response(
        sender=sender,
        question=question,
        traffic=traffic_result,
        transport=transport_result,
        routes=route_result,
        impact=impact_result
    )

    # --------------------------------------------------------
    # 5. RISULTATO FINALE
    # --------------------------------------------------------

    result = {
        "agent": "mobility_agent",
        "request_id": request_id,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "status": "analysis_completed",

        "request": {
            "sender": sender,
            "request_type": request_type,
            "question": question
        },

        "incident": incident,

        "specialist_analyses": {
            "traffic": traffic_result,
            "public_transport": transport_result,
            "route_planning": route_result,
            "mobility_impact": impact_result
        },

        "assessment": {
            "verification_status": verification_status,
            "urgency": urgency,
            "urgency_reason": urgency_reason
        },

        "response": response_result
    }

    logger.info(
        "Richiesta Mobility completata: %s",
        request_id
    )

    return result


if __name__ == "__main__":

    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    try:
        incident_id = int(
            input("Inserisci l'ID di un incidente: ")
        )

        request = {
            "request_id": "MOBILITY-TEST-001",
            "sender": "janara",
            "request_type": "incident_analysis",
            "incident_id": incident_id,
            "question": None,
            "context": {}
        }

        result = analyze_mobility_request(request)

        print("\n===== MOBILITY AGENT =====")

        print(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False
            )
        )

    except ValueError as error:
        print(f"Richiesta non valida: {error}")

    except Exception:
        logger.exception(
            "Errore durante l'esecuzione del Mobility Agent."
        )
