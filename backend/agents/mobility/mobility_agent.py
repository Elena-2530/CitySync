
import logging
from datetime import datetime, timezone

from agents.mobility.specialists import traffic_agent
from agents.mobility.specialists import public_transport_agent
from agents.mobility.specialists import route_planning_agent
from agents.mobility.specialists import mobility_impact_agent
from agents.mobility.specialists import mobility_assistance_agent


logger = logging.getLogger("neurapolis.mobility")


VALID_SENDERS = {"janara", "user", "operator"}

VALID_REQUEST_TYPES = {
    "incident_analysis",
    "route_request",
    "question"
}


def validate_request(request):
    """
    Controlla che la richiesta ricevuta sia strutturata correttamente.

    Il Mobility Agent riceve le informazioni dal chiamante.
    Non recupera autonomamente segnalazioni o incidenti dal database.
    """

    if not isinstance(request, dict):
        raise ValueError("La richiesta deve essere un dizionario.")

    sender = request.get("sender")

    if sender not in VALID_SENDERS:
        raise ValueError(
            "Mittente non valido: janara, user oppure operator."
        )

    request_type = request.get("request_type")

    if request_type not in VALID_REQUEST_TYPES:
        raise ValueError(
            "Tipologia non valida: incident_analysis, "
            "route_request oppure question."
        )

    context = request.get("context", {})

    if not isinstance(context, dict):
        raise ValueError("Il campo context deve essere un dizionario.")

    incident = request.get("incident")

    if incident is not None and not isinstance(incident, dict):
        raise ValueError("Il campo incident deve essere un dizionario.")

    question = request.get("question")

    if question is not None and not isinstance(question, str):
        raise ValueError("Il campo question deve essere una stringa.")

    if request_type == "incident_analysis" and incident is None:
        raise ValueError(
            "Per analizzare una criticità è necessario fornire "
            "il campo incident."
        )

    if request_type == "route_request":
        if not context.get("origin"):
            raise ValueError(
                "Per pianificare un percorso è necessario specificare "
                "il punto di partenza."
            )

        if not context.get("destination"):
            raise ValueError(
                "Per pianificare un percorso è necessario specificare "
                "la destinazione."
            )

    return True


def determine_specialists(request_type, question, context):
    """
    Stabilisce quali specialisti devono essere attivati.

    La selezione riguarda esclusivamente le competenze di mobilità.
    """

    specialists = set()

    if request_type == "incident_analysis":
        specialists.update({
            "traffic",
            "public_transport",
            "mobility_impact"
        })

        if context.get("origin") and context.get("destination"):
            specialists.add("route_planning")

    elif request_type == "route_request":
        specialists.update({
            "public_transport",
            "route_planning"
        })

    elif request_type == "question":
        question_text = (question or "").lower()

        traffic_keywords = [
            "traffico",
            "incidente",
            "strada",
            "viabilità",
            "chiusa",
            "chiusura",
            "bloccata",
            "bloccato",
            "allagamento",
            "allagata",
            "rallentamento"
        ]

        transport_keywords = [
            "autobus",
            "bus",
            "tram",
            "metro",
            "metropolitana",
            "treno",
            "treni",
            "mezzi",
            "trasporto pubblico",
            "linea"
        ]

        if any(word in question_text for word in traffic_keywords):
            specialists.add("traffic")

        if any(word in question_text for word in transport_keywords):
            specialists.add("public_transport")

        if context.get("origin") and context.get("destination"):
            specialists.add("route_planning")

        if request_type == "question" and not specialists:
            # Una richiesta non classificabile non deve generare
            # analisi specialistiche non pertinenti.
            pass

    return specialists


def analyze_mobility_request(request):
    """
    Punto di ingresso del Mobility Agent.

    Riceve una richiesta da Janara, da un utente o da un operatore.
    Coordina gli specialisti e restituisce un'analisi strutturata.

    Non legge il database e non analizza direttamente le segnalazioni
    social: queste responsabilità appartengono agli altri componenti
    di NEURAPOLIS.
    """

    validate_request(request)

    request_id = request.get("request_id")
    sender = request["sender"]
    request_type = request["request_type"]
    question = request.get("question")
    incident = request.get("incident")
    context = request.get("context") or {}

    selected_specialists = determine_specialists(
        request_type,
        question,
        context
    )

    traffic_result = None
    transport_result = None
    route_result = None
    impact_result = None

    # 1. Analisi del traffico e della viabilità.
    if "traffic" in selected_specialists:
        traffic_result = traffic_agent.analyze(
            incident=incident,
            context=context
        )

    # 2. Analisi del trasporto pubblico.
    if "public_transport" in selected_specialists:
        transport_result = public_transport_agent.analyze(
            incident=incident,
            context=context
        )

    # 3. Pianificazione dei percorsi.
    if "route_planning" in selected_specialists:
        route_result = route_planning_agent.analyze(context)

    # 4. Valutazione degli impatti sulla mobilità.
    if "mobility_impact" in selected_specialists:
        impact_result = mobility_impact_agent.analyze(
            incident=incident,
            traffic_analysis=traffic_result,
            transport_analysis=transport_result
        )

    # 5. Preparazione della risposta.
    response_result = mobility_assistance_agent.generate_response(
        sender=sender,
        question=question,
        traffic=traffic_result,
        transport=transport_result,
        routes=route_result,
        impact=impact_result
    )

    result = {
        "agent": "mobility_agent",
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "analysis_completed",
        "request": {
            "sender": sender,
            "request_type": request_type,
            "question": question
        },
        "incident": incident,
        "selected_specialists": sorted(selected_specialists),
        "specialist_analyses": {
            "traffic": traffic_result,
            "public_transport": transport_result,
            "route_planning": route_result,
            "mobility_impact": impact_result
        },
        "response": response_result,
        "limitations": [
            "Le valutazioni dipendono dai dati forniti nella richiesta.",
            "Il Mobility Agent non verifica autonomamente "
            "l'attendibilità delle segnalazioni.",
            "Percorsi e condizioni non sono considerati verificati "
            "se non sono supportati da dati aggiornati."
        ]
    }

    logger.info(
        "Richiesta Mobility completata: %s",
        request_id or "senza ID"
    )

    return result


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    # Esempio di richiesta ricevuta da Janara.
    # I dati sono simulati: non rappresentano condizioni reali.

    example_request = {
        "request_id": "MOBILITY-TEST-001",
        "sender": "janara",
        "request_type": "incident_analysis",
        "question": None,
        "incident": {
            "id": 15,
            "event_type": "environment",
            "description": "Possibile allagamento a Fuorigrotta "
                           "dopo il temporale.",
            "location": "Fuorigrotta, Napoli",
            "verification_status": "unverified"
        },
        "context": {
            "traffic_data": {},
            "transport_data": {}
        }
    }

    try:
        result = analyze_mobility_request(example_request)

        print("\n===== MOBILITY AGENT =====")
        print(json.dumps(result, indent=4, ensure_ascii=False))

    except ValueError as error:
        print(f"Richiesta non valida: {error}")

    except Exception:
        logger.exception(
            "Errore durante l'esecuzione del Mobility Agent."
        )
