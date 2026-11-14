
import logging
from datetime import datetime, timezone

from agents.mobility import question_parser
from agents.mobility.mobility_data import route_data
from agents.mobility.mobility_data import traffic_data
from agents.mobility.mobility_data import transport_data
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


# Tipologie di problema di mobilità: (codice, etichetta, parole chiave).
PROBLEM_TYPES = [
    ("incidente_stradale", "Incidente stradale",
     ["incidente", "collisione", "scontro", "tamponamento"]),
    ("allagamento", "Allagamento",
     ["allagamento", "allagata", "allagato", "acqua sulla strada"]),
    ("chiusura_stradale", "Chiusura o blocco stradale",
     ["strada chiusa", "strada bloccata", "chiusura", "blocco stradale", "bloccata", "bloccato"]),
    ("incendio", "Incendio o fumo sulla sede stradale",
     ["incendio", "fumo"]),
    ("maltempo", "Maltempo con effetti sulla circolazione",
     ["temporale", "forte pioggia", "vento forte", "maltempo", "nubifragio"]),
    ("interruzione_trasporto_pubblico", "Interruzione del trasporto pubblico",
     ["metro ferma", "linea sospesa", "sciopero", "guasto", "interruzione del servizio"]),
]

# Piano d'azione per tipologia: sono verifiche e raccomandazioni, non decisioni.
ACTION_PLANS = {
    "incidente_stradale": [
        "Verificare la posizione esatta dell'incidente.",
        "Cercare conferme da fonti ufficiali (polizia locale, operatori).",
        "Controllare le condizioni delle strade limitrofe.",
        "Valutare con gli operatori eventuali percorsi alternativi.",
        "Segnalare all'operatore la possibile criticità.",
    ],
    "allagamento": [
        "Verificare la posizione e l'estensione dell'allagamento.",
        "Controllare con fonti ufficiali la percorribilità dei tratti interessati.",
        "Verificare se linee di superficie e sottopassi sono coinvolti.",
        "Valutare con gli operatori eventuali percorsi alternativi.",
        "Segnalare all'operatore la possibile criticità.",
    ],
    "chiusura_stradale": [
        "Verificare presso la fonte ufficiale la chiusura e la sua durata.",
        "Individuare le linee di trasporto pubblico che passano dal tratto.",
        "Valutare con gli operatori deviazioni e percorsi alternativi.",
        "Segnalare all'operatore la possibile criticità.",
    ],
    "incendio": [
        "Verificare la posizione e le limitazioni alla circolazione.",
        "Cercare conferme dai soccorsi o da fonti ufficiali.",
        "Controllare strade limitrofe e linee di trasporto vicine.",
        "Segnalare all'operatore la possibile criticità.",
    ],
    "maltempo": [
        "Verificare le allerte meteo ufficiali per la zona.",
        "Controllare le condizioni di sottopassi e strade a rischio.",
        "Verificare lo stato dei servizi di trasporto pubblico.",
        "Segnalare all'operatore la possibile criticità.",
    ],
    "interruzione_trasporto_pubblico": [
        "Verificare presso l'operatore il tratto e la durata dell'interruzione.",
        "Individuare linee alternative e servizi sostitutivi disponibili.",
        "Valutare l'impatto sui nodi di interscambio vicini.",
        "Segnalare all'operatore la possibile criticità.",
    ],
    "non_classificato": [
        "Verificare la natura e la posizione dell'evento.",
        "Cercare conferme da fonti ufficiali.",
        "Segnalare all'operatore la possibile criticità.",
    ],
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


def determine_specialists(request_type, question, context, intent=None):
    """
    Stabilisce quali specialisti devono essere attivati.

    La selezione riguarda esclusivamente le competenze di mobilità.
    `intent` (facoltativo) è l'intento già riconosciuto nella domanda.
    """

    specialists = set()
    context = context or {}

    if request_type == "incident_analysis":
        specialists.update({
            "traffic",
            "public_transport",
            "mobility_impact"
        })

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
            "strade",
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

        # Specialisti richiesti dall'intento riconosciuto.
        if intent == "affected_roads":
            specialists.add("traffic")
        elif intent == "avoid_traffic":
            specialists.update({"traffic", "public_transport"})
        elif intent == "transport_status":
            specialists.add("public_transport")
        elif intent in {"impact", "missing_info"}:
            specialists.update({
                "traffic",
                "public_transport",
                "mobility_impact"
            })

    # Se sono noti partenza e destinazione serve il pianificatore.
    if context.get("origin") and context.get("destination"):
        specialists.add("route_planning")
        if request_type != "incident_analysis":
            specialists.add("public_transport")

    return specialists


def classify_problem(incident, question=None):
    """Riconosce la tipologia di problema dalla descrizione dell'evento."""

    text = " ".join([
        (incident or {}).get("description") or "",
        question or ""
    ]).lower()

    for code, label, keywords in PROBLEM_TYPES:
        if any(word in text for word in keywords):
            return {"type": code, "label": label, "basis": "description_keywords"}

    if not (incident or {}).get("description"):
        return None

    return {
        "type": "non_classificato",
        "label": "Problema di mobilità non classificato",
        "basis": "description_keywords"
    }


def build_context_hints(incident, context):
    """
    Informazioni sulla zona dell'evento: strade principali (base di
    conoscenza) e fermate di trasporto pubblico vicine (rete programmata).
    Sono ipotesi di supporto, non verifiche.
    """

    location = (
        (incident or {}).get("location")
        or context.get("location")
        or context.get("zone")
    )

    if not location:
        return {}

    hints = {"location": location}

    roads = traffic_data.roads_for_location(location)
    if roads:
        hints["potentially_affected_roads"] = roads

    place = transport_data.resolve_place(location)
    if place:
        transit = []
        seen = set()
        for near in transport_data.stops_near(place["lat"], place["lon"], 1000):
            for line in transport_data.lines_serving(near["stop"]["id"]):
                key = (line["id"], near["stop"]["id"])
                if key in seen:
                    continue
                seen.add(key)
                transit.append({
                    "line": line["name"],
                    "operator": line.get("operator", ""),
                    "stop": near["stop"]["name"],
                    "distance_m": near["distance_m"]
                })
        if transit:
            hints["transit_in_area"] = transit
            hints["transit_basis"] = "static_network"

    return hints


def compute_confidence(incident, selected, traffic_result, transport_result,
                       planned_route):
    """
    Affidabilità complessiva dell'analisi, con i motivi.

    Parte da "alta" e scende quando mancano conferme o dati recenti.
    """

    # Nessuna segnalazione, nessuno specialista e nessun percorso: la richiesta
    # non si basa su dati di mobilità, quindi non ha senso dare un'affidabilità.
    if incident is None and not selected and not planned_route:
        return {
            "level": "not_applicable",
            "reasons": ["La richiesta non richiede un'analisi basata su dati di mobilità."]
        }

    score = 3
    reasons = []

    if incident is not None:
        status = incident.get("verification_status")
        if status == "partially_confirmed":
            score -= 1
            reasons.append("La segnalazione è solo parzialmente confermata.")
        elif status != "confirmed":
            score -= 2
            reasons.append("La segnalazione non risulta verificata.")

    if "traffic" in selected and (
        traffic_result or {}
    ).get("analysis_status") in (None, "insufficient_data"):
        score -= 1
        reasons.append("Mancano dati recenti sulla viabilità.")

    if "public_transport" in selected and (
        transport_result or {}
    ).get("analysis_status") in (None, "insufficient_data"):
        score -= 1
        reasons.append("Mancano dati recenti sul trasporto pubblico.")

    if planned_route:
        score -= 1
        reasons.append(
            "I percorsi sono calcolati sulla rete programmata, "
            "non su dati in tempo reale."
        )

    level = "high" if score >= 3 else "medium" if score == 2 else "low"

    if not reasons:
        reasons.append(
            "Dati recenti e segnalazione confermata."
            if incident is not None else "Dati recenti disponibili."
        )

    return {"level": level, "reasons": reasons}


def _collect(key, *results):
    """Unisce, senza duplicati, un campo elenco dei risultati degli specialisti."""

    merged = []
    for result in results:
        if isinstance(result, dict):
            merged.extend(result.get(key, []) or [])
    return list(dict.fromkeys(merged))


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

    # Copia di lavoro: la richiesta ricevuta non viene modificata.
    context = dict(request.get("context") or {})

    # --- comprensione della domanda -------------------------------------
    parsed = question_parser.parse_question(
        question,
        context.get("user_type")
    ) if question else {
        "intent": "general", "origin": None,
        "destination": None, "profile": None
    }

    if request_type == "route_request":
        intent = "route"
    else:
        intent = parsed["intent"]

    if parsed["origin"] and parsed["destination"]:
        if not context.get("origin"):
            context["origin"] = parsed["origin"]
        if not context.get("destination"):
            context["destination"] = parsed["destination"]

    profile = context.get("profile") or parsed["profile"] or "fastest"

    selected_specialists = determine_specialists(
        request_type,
        question,
        context,
        intent
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
    route_plan = None
    planned_route = False

    if "route_planning" in selected_specialists:
        if context.get("route_options") is None:
            # Il chiamante non ha fornito il campo route_options: i percorsi
            # li calcola il pianificatore sulla rete, tenendo conto delle
            # interruzioni segnalate. Se invece route_options è presente
            # (anche vuoto) il chiamante dichiara quali percorsi esistono e
            # il Mobility Agent non ne aggiunge altri.
            services = (context.get("transport_data") or {}).get("services", [])
            disruptions = transport_data.disruptions_from_services(services)

            route_plan = route_data.plan_routes(
                context["origin"],
                context["destination"],
                disruptions=disruptions,
                profile=profile
            )
            context["route_options"] = route_plan["options"]
            planned_route = bool(route_plan["options"])
        else:
            route_plan = {
                "origin": {"name": context["origin"]},
                "destination": {"name": context["destination"]},
                "unresolved": [],
                "excluded_lines": [],
                "options": context["route_options"]
            }

        route_result = route_planning_agent.analyze(context)

        if planned_route:
            route_result["required_checks"] = list(dict.fromkeys(
                route_result.get("required_checks", []) + [
                    "Verificare in tempo reale lo stato delle linee "
                    "indicate nel percorso."
                ]
            ))

    # 4. Valutazione degli impatti sulla mobilità.
    if "mobility_impact" in selected_specialists:
        impact_result = mobility_impact_agent.analyze(
            incident=incident,
            traffic_analysis=traffic_result,
            transport_analysis=transport_result
        )

    # 5. Classificazione, contesto, piano d'azione e affidabilità.
    problem = classify_problem(incident, question)
    hints = build_context_hints(incident, context)

    all_results = (
        traffic_result, transport_result, route_result, impact_result
    )
    required_checks = _collect("required_checks", *all_results)
    missing_information = _collect("missing_information", *all_results)

    if route_plan and route_plan.get("unresolved"):
        missing_information.append(
            "Luoghi non riconosciuti: "
            + ", ".join(route_plan["unresolved"]) + "."
        )

    action_plan = list(ACTION_PLANS.get(
        problem["type"], []
    )) if problem else []

    confidence = compute_confidence(
        incident,
        selected_specialists,
        traffic_result,
        transport_result,
        planned_route
    )

    # 6. Preparazione della risposta.
    response_result = mobility_assistance_agent.generate_response(
        sender=sender,
        question=question,
        traffic=traffic_result,
        transport=transport_result,
        routes=route_result,
        impact=impact_result,
        intent=intent,
        route_plan=route_plan,
        hints=hints,
        incident=incident,
        confidence=confidence,
        problem=problem,
        required_checks=required_checks
    )

    limitations = [
        "Le valutazioni dipendono dai dati forniti nella richiesta.",
        "Il Mobility Agent non verifica autonomamente "
        "l'attendibilità delle segnalazioni.",
        "Percorsi e condizioni non sono considerati verificati "
        "se non sono supportati da dati aggiornati."
    ]

    if planned_route:
        limitations.append(
            "I percorsi sono calcolati sulla rete programmata "
            f"({route_plan['network'].get('name', 'rete')}): "
            "i tempi sono stime e non tengono conto di ritardi in corso."
        )

    if hints.get("potentially_affected_roads"):
        limitations.append(
            "Le strade indicate per la zona sono assi principali "
            "indicativi, non strade accertate come coinvolte."
        )

    result = {
        "agent": "mobility_agent",
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "analysis_completed",
        "request": {
            "sender": sender,
            "request_type": request_type,
            "question": question,
            "intent": intent
        },
        "incident": incident,
        "problem_type": problem,
        "selected_specialists": sorted(selected_specialists),
        "specialist_analyses": {
            "traffic": traffic_result,
            "public_transport": transport_result,
            "route_planning": route_result,
            "mobility_impact": impact_result
        },
        "route_plan": (
            {
                "origin": (route_plan.get("origin") or {}).get("name"),
                "destination": (route_plan.get("destination") or {}).get("name"),
                "unresolved": route_plan.get("unresolved", []),
                "excluded_lines": route_plan.get("excluded_lines", []),
                "options_found": len(route_plan.get("options", [])),
                "network": route_plan.get("network"),
                "notes": route_plan.get("notes", [])
            } if route_plan else None
        ),
        "context_hints": hints,
        "action_plan": action_plan,
        "required_checks": required_checks,
        "missing_information": missing_information,
        "confidence": confidence,
        "response": response_result,
        "limitations": limitations
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

    # Esempi di richieste. I dati sono simulati: non rappresentano
    # condizioni reali.

    examples = [
        # 1. Janara inoltra una segnalazione.
        {
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
        },
        # 2. Un turista chiede come muoversi.
        {
            "request_id": "MOBILITY-TEST-002",
            "sender": "user",
            "request_type": "question",
            "question": "Sono a Piazza Garibaldi e voglio raggiungere "
                        "Castel dell'Ovo. Qual è il modo migliore per arrivarci?",
            "incident": None,
            "context": {"user_type": "tourist"}
        },
        # 3. La stessa domanda con la Linea 1 sospesa tra due stazioni.
        {
            "request_id": "MOBILITY-TEST-003",
            "sender": "user",
            "request_type": "route_request",
            "question": None,
            "incident": None,
            "context": {
                "origin": "Piazza Garibaldi",
                "destination": "Castel dell'Ovo",
                "transport_data": {
                    "max_age_minutes": 15,
                    "services": [{
                        "name": "Metro Linea 1",
                        "operator": "ANM",
                        "status": "suspended",
                        "between": ["Università", "Municipio"],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "source": "esempio_simulato"
                    }]
                }
            }
        },
        # 4. Un operatore chiede quali strade potrebbero essere interessate.
        {
            "request_id": "MOBILITY-TEST-004",
            "sender": "operator",
            "request_type": "question",
            "question": "Quali strade potrebbero essere interessate?",
            "incident": {
                "id": 15,
                "event_type": "environment",
                "description": "Possibile allagamento a Fuorigrotta "
                               "dopo il temporale.",
                "location": "Fuorigrotta, Napoli",
                "verification_status": "unverified"
            },
            "context": {}
        }
    ]

    for example_request in examples:
        try:
            result = analyze_mobility_request(example_request)

            print(f"\n===== MOBILITY AGENT · {result['request_id']} =====")
            print(json.dumps(result, indent=4, ensure_ascii=False))

        except ValueError as error:
            print(f"Richiesta non valida: {error}")

        except Exception:
            logger.exception(
                "Errore durante l'esecuzione del Mobility Agent."
            )
