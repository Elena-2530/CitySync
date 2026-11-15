"""
Janara Orchestrator Agent - CitySync

Coordina Mobility, Tourism, Civil Protection, Verification
e Social Intelligence.

Janara è l'unico coordinatore degli agenti principali.
Gli agenti specialistici possono coordinare i propri specialisti interni.
"""

import importlib
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger("citysync.janara")

VALID_SENDERS = {"user", "operator", "system"}
VALID_REQUEST_TYPES = {"question", "incident_assessment"}

MAX_AGENT_CALLS = 6

KNOWN_AGENTS = {
    "mobility",
    "tourism",
    "civil_protection",
}

CONFIDENCE_ORDER = ["low", "medium", "high"]

TOURISM_WORDS = [
    "museo", "musei", "castello", "castel", "chiesa",
    "cattedrale", "duomo", "palazzo", "teatro",
    "monumento", "cosa vedere", "visitare", "visita",
    "biglietto", "biglietti", "orari", "orario",
    "apre", "aperto", "chiude", "chiuso",
    "turista", "turismo", "piove", "pioggia",
    "cosa fare",
]

MOBILITY_WORDS = [
    "traffico", "strada", "strade", "bus", "autobus",
    "metro", "metropolitana", "tram", "funicolare",
    "treno", "linea", "linee", "percorso",
    "come arrivo", "come si arriva", "come raggiungo",
    "arrivare", "raggiungere", "bloccato", "bloccata",
    "chiusa", "chiuso al traffico", "ritardo",
    "sciopero", "incidente stradale", "allagamento",
    "viabilità",
]

CIVIL_PROTECTION_WORDS = [
    "allerta", "protezione civile", "maltempo",
    "pioggia intensa", "temporale", "temporali",
    "allagamento", "allagamenti", "frana", "frane",
    "rischio idrogeologico", "rischio idraulico",
    "esondazione", "esondazioni", "vento forte",
    "emergenza", "criticità meteo", "criticità",
    "rischio meteo", "neve", "grandine",
]

INCIDENT_PATTERN = re.compile(
    r"\bincident[ei]\s*(?:n\.?|numero|#)?\s*(\d+)",
    re.IGNORECASE,
)


# ============================================================
# VALIDAZIONE
# ============================================================

def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("La richiesta deve essere un dizionario.")

    if request.get("sender") not in VALID_SENDERS:
        raise ValueError("Mittente non valido.")

    if request.get("request_type") not in VALID_REQUEST_TYPES:
        raise ValueError("Tipologia di richiesta non valida.")

    context = request.get("context", {})

    if context is not None and not isinstance(context, dict):
        raise ValueError("Il campo context deve essere un dizionario.")

    question = request.get("question")

    if question is not None and not isinstance(question, str):
        raise ValueError("Il campo question deve essere una stringa.")

    if request["request_type"] == "incident_assessment":
        try:
            int((context or {}).get("incident_id"))
        except (TypeError, ValueError):
            raise ValueError(
                "Per valutare un incidente serve context['incident_id']."
            )

    elif not (question or "").strip() and not (context or {}).get("incident_id"):
        raise ValueError("Serve una domanda oppure un incident_id.")


# ============================================================
# INSTRADAMENTO
# ============================================================

def _has_any(text, words):
    return any(word in text for word in words)


def plan_routing(question, context):
    text = (question or "").lower()
    reasons = []

    incident_id = (context or {}).get("incident_id")

    if incident_id is None:
        match = INCIDENT_PATTERN.search(text)
        if match:
            incident_id = int(match.group(1))

    if incident_id is not None:
        reasons.append(f"La richiesta riguarda l'incidente {incident_id}.")

    tourism = _has_any(text, TOURISM_WORDS)

    if not tourism:
        try:
            from agents.tourism.tourism_data import places
            tourism = places.find_place(question or "") is not None
        except Exception:
            tourism = False

    mobility = _has_any(text, MOBILITY_WORDS)
    civil_protection = _has_any(text, CIVIL_PROTECTION_WORDS)

    if tourism:
        reasons.append("Riconosciuto un argomento turistico.")

    if mobility:
        reasons.append("Riconosciuto un argomento di mobilità.")

    if civil_protection:
        reasons.append("Riconosciuto un argomento di Protezione Civile.")

    if not (incident_id is not None or tourism or mobility or civil_protection):
        reasons.append("Nessun argomento di competenza riconosciuto.")

    return {
        "incident_id": incident_id,
        "tourism": tourism,
        "mobility": mobility,
        "civil_protection": civil_protection,
        "reasons": reasons,
    }


# ============================================================
# CHIAMATE AGLI AGENTI
# ============================================================

def _call_mobility(request):
    from agents.mobility.mobility_agent import analyze_mobility_request
    return analyze_mobility_request(request)


def _call_tourism(request):
    from agents.tourism.tourism_agent import analyze_tourism_request
    return analyze_tourism_request(request)


def _call_civil_protection(request):
    """
    Invoca il coordinatore principale della Protezione Civile.

    Nel progetto la funzione ha firma:
    analyze_civil_protection_request(alerts=None, now=None)

    Perciò viene invocata senza argomenti.
    """

    possible_modules = [
        "agents.civil_protection.civil_protection_agent",
        "agents.civil_protection.agent",
        "agents.civil_protection.coordinator",
    ]

    last_error = None

    for module_name in possible_modules:
        try:
            module = importlib.import_module(module_name)

            function = getattr(
                module,
                "analyze_civil_protection_request",
                None,
            )

            if callable(function):
                return function()

        except (ImportError, AttributeError) as error:
            last_error = error

    raise ImportError(
        "Non trovo analyze_civil_protection_request. "
        "Controllare il nome del modulo Civil Protection."
    ) from last_error


def _call_social(incident_id):
    from agents.social_intelligence_agent import get_social_intelligence
    return get_social_intelligence(incident_id)


def _call_verification(incident_id):
    from agents.verification_agent import evaluate_incident
    return evaluate_incident(incident_id)


AGENT_CALLERS = {
    "mobility": _call_mobility,
    "tourism": _call_tourism,
    "civil_protection": _call_civil_protection,
}


def _text_of(result):
    if isinstance(result, str):
        return result

    if not isinstance(result, dict):
        return ""

    response = result.get("response")

    while isinstance(response, dict):
        response = response.get("response")

    return response if isinstance(response, str) else ""


# ============================================================
# GESTIONE DI UNA SESSIONE DI COORDINAMENTO
# ============================================================

class _Run:

    def __init__(self, request_id, sender):
        self.request_id = request_id
        self.sender = sender
        self.trace = []
        self.results = {}
        self.errors = []
        self.seen = set()

    def call(
        self,
        agent,
        request_type,
        question=None,
        context=None,
        incident=None,
        reason="",
    ):
        if agent not in AGENT_CALLERS:
            self.errors.append({
                "agent": agent,
                "error": "Agente non disponibile.",
            })
            return None

        key = (
            agent,
            request_type,
            question,
            repr(sorted((context or {}).items(), key=str)),
            repr(incident),
        )

        if key in self.seen:
            return None

        if len(self.trace) >= MAX_AGENT_CALLS:
            self.errors.append({
                "agent": agent,
                "error": "Limite di chiamate raggiunto.",
            })
            return None

        self.seen.add(key)

        request = {
            "request_id": f"{self.request_id}-{len(self.trace) + 1}",
            "sender": self.sender if self.sender != "system" else "system",
            "request_type": request_type,
            "question": question,
            "context": dict(context or {}),
        }

        if incident is not None:
            request["incident"] = incident

        entry = {
            "agent": agent,
            "request_type": request_type,
            "reason": reason,
            "status": "ok",
        }

        self.trace.append(entry)

        try:
            result = AGENT_CALLERS[agent](request)

        except Exception as error:
            logger.exception("Errore nell'agente %s", agent)

            entry["status"] = "error"
            entry["error"] = str(error)

            self.errors.append({
                "agent": agent,
                "error": str(error),
            })

            return None

        self.results.setdefault(agent, []).append(result)
        return result


# ============================================================
# HANDOFF
# ============================================================

def _follow_handoffs(run, result, context):
    unresolved = []
    missing = []

    if not isinstance(result, dict):
        return unresolved, missing

    for handoff in result.get("suggested_handoffs") or []:
        if not isinstance(handoff, dict):
            continue

        agent = handoff.get("agent")

        if agent not in KNOWN_AGENTS:
            unresolved.append({
                **handoff,
                "motivo": "Agente sconosciuto a Janara.",
            })
            continue

        h_context = dict(context or {})
        h_context.update(handoff.get("context") or {})

        if (
            handoff.get("request_type") == "route_request"
            and not h_context.get("origin")
        ):
            missing.append(
                "Punto di partenza necessario per il percorso."
            )
            continue

        followed = run.call(
            agent,
            handoff.get("request_type", "question"),
            handoff.get("question"),
            h_context,
            reason="Handoff suggerito da un agente.",
        )

        if followed is not None:
            u, m = _follow_handoffs(run, followed, h_context)
            unresolved.extend(u)
            missing.extend(m)

    return unresolved, missing


# ============================================================
# VALUTAZIONE INCIDENTE
# ============================================================

def _assess_incident(run, incident_id, question, context):
    out = {
        "social": None,
        "verification": None,
        "found": True,
    }

    try:
        social = _call_social(incident_id)

        run.trace.append({
            "agent": "social_intelligence",
            "status": "ok",
        })

    except Exception as error:
        logger.exception("Errore Social Intelligence")

        run.errors.append({
            "agent": "social_intelligence",
            "error": str(error),
        })

        return out

    if social is None:
        out["found"] = False
        return out

    out["social"] = social

    try:
        out["verification"] = _call_verification(incident_id)

        run.trace.append({
            "agent": "verification",
            "status": "ok",
        })

    except Exception as error:
        logger.exception("Errore Verification")

        run.errors.append({
            "agent": "verification",
            "error": str(error),
        })

    incident_data = social.get("incident")

    if not isinstance(incident_data, dict):
        return out

    incident = dict(incident_data)

    if out["verification"]:
        incident["verification_status"] = (
            out["verification"].get("verification_status")
            or incident.get("verification_status")
        )

    mobility_incident = {
        key: incident.get(key)
        for key in (
            "id",
            "event_type",
            "description",
            "location",
            "verification_status",
        )
    }

    try:
        from agents.mobility.mobility_agent import classify_problem

        problem = classify_problem(mobility_incident, question)

        if problem and problem.get("type") != "non_classificato":
            run.call(
                "mobility",
                "incident_analysis",
                question,
                context,
                incident=mobility_incident,
                reason="L'incidente ha effetti sulla mobilità.",
            )

    except Exception as error:
        logger.exception("Errore nella classificazione dell'incidente")

        run.errors.append({
            "agent": "mobility",
            "error": str(error),
        })

    return out


# ============================================================
# AFFIDABILITÀ
# ============================================================

def _combine_confidence(results):
    levels = []
    reasons = []

    for result in results:
        if not isinstance(result, dict):
            continue

        confidence = result.get("confidence") or {}

        if confidence.get("level") in CONFIDENCE_ORDER:
            levels.append(confidence["level"])
            reasons.extend(confidence.get("reasons") or [])

    if not levels:
        return {
            "level": "not_applicable",
            "reasons": [
                "Gli agenti non hanno fornito un livello di affidabilità."
            ],
        }

    lowest = min(levels, key=CONFIDENCE_ORDER.index)

    return {
        "level": lowest,
        "reasons": [
            "Affidabilità complessiva pari al livello più basso "
            "tra quelli dichiarati dagli agenti."
        ] + reasons,
    }


# ============================================================
# COMPOSIZIONE DELLA RISPOSTA
# ============================================================

def _compose_civil_protection(result, context):
    """
    Converte il risultato strutturato dell'agente Civil Protection
    in un testo comprensibile.

    Non deduce la zona da coordinate o quartieri:
    usa esclusivamente le informazioni territoriali presenti
    nell'allerta ufficiale.
    """

    parts = []

    official = result.get("official_alert_analysis") or {}
    alerts = official.get("alerts") or []

    location = str(
        (context or {}).get("location")
        or ""
    ).lower()

    is_naples_request = any(
        word in location
        for word in ("napoli", "naples", "vomero")
    )

    active_alerts_found = False
    territorial_match_found = False

    for alert in alerts:
        if not isinstance(alert, dict):
            continue

        if alert.get("validity_status") != "active":
            continue

        active_alerts_found = True

        zones = alert.get("zones") or []

        if is_naples_request:
            relevant_zones = [
                zone for zone in zones
                if "napoli" in str(zone.get("territory", "")).lower()
            ]
        else:
            # Senza una località specifica vengono mostrate
            # le zone riportate dall'allerta regionale.
            relevant_zones = zones

        if relevant_zones:
            territorial_match_found = True

            parts.append(
                "È presente un'allerta ufficiale attiva "
                f"per il territorio indicato: "
                f"{alert.get('alert_number', 'numero non disponibile')}."
            )

            parts.append(
                "Periodo di validità: "
                f"dal {alert.get('valid_from', 'non specificato')} "
                f"al {alert.get('valid_until', 'non specificato')}."
            )

            for zone in relevant_zones:
                risks = zone.get("risks") or []
                risks_text = ", ".join(risks) if risks else "non specificati"

                parts.append(
                    f"Zona {zone.get('zone', 'non specificata')}: "
                    f"{zone.get('territory', 'territorio non specificato')}. "
                    f"Livello di allerta: "
                    f"{zone.get('alert_level', 'non specificato')}. "
                    f"Rischi indicati: {risks_text}."
                )

            if is_naples_request:
                parts.append(
                    "L'allerta comprende il territorio di Napoli. "
                    "Le informazioni disponibili non consentono però "
                    "di determinare il rischio specifico del quartiere "
                    "Vomero o di confermare che siano in corso allagamenti."
                )

            source_name = alert.get(
                "source_name",
                "Fonte ufficiale",
            )
            source_url = alert.get("source_url")

            source_text = f"Fonte: {source_name}."
            if source_url:
                source_text += f" {source_url}"

            parts.append(source_text)

    if not active_alerts_found:
        parts.append(
            "Nei dati analizzati non risultano allerte ufficiali "
            "attualmente attive. Questo risultato riguarda soltanto "
            "i dati disponibili al momento dell'analisi e non dimostra "
            "l'assenza di rischi."
        )

    elif is_naples_request and not territorial_match_found:
        parts.append(
            "Sono state rilevate allerte attive, ma i dati territoriali "
            "disponibili non permettono di associare con certezza "
            "una zona ufficiale alla località indicata."
        )

    summary = result.get("summary") or {}

    if summary:
        total = summary.get("total_alerts")
        active = summary.get("active_alerts")

        if total is not None or active is not None:
            parts.append(
                "Riepilogo dell'analisi: "
                f"{total if total is not None else 'n.d.'} allerte totali, "
                f"{active if active is not None else 'n.d.'} attive."
            )

    return parts


def _compose(run, sender, assessment, unresolved_handoffs, context=None):
    parts = []
    limitations = []
    missing = []
    checks = []
    all_results = []

    incident_status = None

    # --------------------------------------------------------
    # RISULTATO SOCIAL INTELLIGENCE E VERIFICATION
    # --------------------------------------------------------

    if assessment and assessment["found"] and assessment["social"]:
        social = assessment["social"]
        incident = social.get("incident") or {}

        verification = assessment["verification"] or {}

        incident_status = (
            verification.get("verification_status")
            or incident.get("verification_status")
            or "non verificato"
        )

        parts.append(
            f"Segnalazione {incident.get('id', 'non identificata')}: "
            f"{incident.get('description') or 'senza descrizione'}. "
            f"Stato: {incident_status}."
        )

        social_analysis = social.get("social_analysis") or {}

        limitations.extend(
            social_analysis.get("limitations") or []
        )

    if assessment and not assessment["found"]:
        parts.append("Incidente non trovato nel database.")

    # --------------------------------------------------------
    # RISULTATI DEGLI AGENTI PRINCIPALI
    # --------------------------------------------------------

    for agent in ("civil_protection", "mobility", "tourism"):
        for result in run.results.get(agent, []):
            if isinstance(result, str):
                parts.append(result)
                continue

            if not isinstance(result, dict):
                continue

            all_results.append(result)

            if agent == "civil_protection":
                parts.extend(
                    _compose_civil_protection(result, context or {})
                )

            else:
                agent_text = _text_of(result)

                if agent_text:
                    parts.append(agent_text)

            limitations.extend(result.get("limitations") or [])
            missing.extend(result.get("missing_information") or [])
            checks.extend(result.get("required_checks") or [])

    # --------------------------------------------------------
    # RISULTATO VUOTO
    # --------------------------------------------------------

    if not parts:
        parts.append(
            "Non ho trovato informazioni sufficienti per rispondere "
            "alla richiesta con gli agenti disponibili."
        )

    # --------------------------------------------------------
    # ERRORI DEGLI AGENTI
    # --------------------------------------------------------

    for error in run.errors:
        limitations.append(
            f"L'agente {error['agent']} non ha risposto: "
            f"{error['error']}."
        )

    confidence = _combine_confidence(all_results)

    response_text = "\n\n".join(parts)

    if sender in ("operator", "system"):
        called = ", ".join(
            item["agent"] for item in run.trace
        ) or "nessuno"

        response_text += (
            f"\n\nAgenti interpellati: {called}. "
            f"Affidabilità: {confidence['level']}."
        )

    return {
        "text": response_text,
        "confidence": confidence,
        "limitations": list(dict.fromkeys(limitations)),
        "missing_information": list(dict.fromkeys(missing)),
        "required_checks": list(dict.fromkeys(checks)),
        "unresolved_handoffs": unresolved_handoffs,
        "incident_status": incident_status,
    }


# ============================================================
# PUNTO DI INGRESSO
# ============================================================

def handle_request(request):
    validate_request(request)

    request_id = request.get("request_id") or "JANARA"
    sender = request["sender"]
    question = request.get("question")
    context = dict(request.get("context") or {})

    run = _Run(request_id, sender)

    if request["request_type"] == "incident_assessment":
        routing = {
            "incident_id": int(context["incident_id"]),
            "tourism": False,
            "mobility": False,
            "civil_protection": False,
            "reasons": [
                "Valutazione esplicita di un incidente."
            ],
        }
    else:
        routing = plan_routing(question, context)

    assessment = None

    if routing["incident_id"] is not None:
        assessment = _assess_incident(
            run,
            routing["incident_id"],
            question,
            context,
        )

    unresolved = []
    missing_extra = []

    # --------------------------------------------------------
    # CIVIL PROTECTION
    # --------------------------------------------------------

    if routing["civil_protection"]:
        result = run.call(
            "civil_protection",
            "question",
            question,
            context,
            reason="Richiesta relativa ad allerte e rischi territoriali.",
        )

        if result is not None:
            u, m = _follow_handoffs(run, result, context)
            unresolved.extend(u)
            missing_extra.extend(m)

    # --------------------------------------------------------
    # TOURISM
    # --------------------------------------------------------

    if routing["tourism"]:
        result = run.call(
            "tourism",
            "question",
            question,
            context,
            reason="Argomento turistico.",
        )

        if result is not None:
            u, m = _follow_handoffs(run, result, context)
            unresolved.extend(u)
            missing_extra.extend(m)

    # --------------------------------------------------------
    # MOBILITY
    # --------------------------------------------------------

    if routing["mobility"] and not any(
        item["agent"] == "mobility"
        for item in run.trace
    ):
        result = run.call(
            "mobility",
            "question",
            question,
            context,
            reason="Argomento di mobilità.",
        )

        if result is not None:
            u, m = _follow_handoffs(run, result, context)
            unresolved.extend(u)
            missing_extra.extend(m)

    # --------------------------------------------------------
    # COMPOSIZIONE RISPOSTA
    # --------------------------------------------------------

    composed = _compose(
        run,
        sender,
        assessment,
        unresolved,
        context,
    )

    composed["missing_information"] = list(
        dict.fromkeys(
            composed["missing_information"] + missing_extra
        )
    )

    return {
        "agent": "janara_orchestrator_agent",
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "completed"
            if not run.errors
            else "completed_with_errors"
        ),
        "request": {
            "sender": sender,
            "request_type": request["request_type"],
            "question": question,
            "context": context,
        },
        "routing": routing,
        "agents_called": run.trace,
        "agent_results": run.results,
        "incident": (
            assessment["social"]["incident"]
            if assessment
            and assessment.get("social")
            and assessment["social"].get("incident")
            else None
        ),
        "response": composed["text"],
        "confidence": composed["confidence"],
        "missing_information": composed["missing_information"],
        "required_checks": composed["required_checks"],
        "limitations": composed["limitations"],
        "unresolved_handoffs": composed["unresolved_handoffs"],
        "errors": run.errors,
    }


# ============================================================
# RIVALUTAZIONE
# ============================================================

def reassess(previous, changes):
    if not isinstance(previous, dict) or "request" not in previous:
        raise ValueError(
            "Serve il risultato di una precedente richiesta."
        )

    if not isinstance(changes, dict) or not changes:
        raise ValueError("Indicare almeno un cambiamento.")

    original = previous["request"]

    context = {
        **(original.get("context") or {}),
        **changes,
    }

    return handle_request({
        "request_id": f"{previous['request_id']}-rev",
        "sender": original["sender"],
        "request_type": original["request_type"],
        "question": original.get("question"),
        "context": context,
    })