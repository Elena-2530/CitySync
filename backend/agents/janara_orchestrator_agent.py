"""
Janara Orchestrator Agent

Coordina gli altri agenti di NEURAPOLIS: Mobility, Tourism, Verification e
Social Intelligence. Non analizza niente da solo: decide chi interpellare,
passa le richieste, segue gli "handoff" suggeriti dagli agenti, riunisce le
risposte in un'unica risposta e dichiara cosa manca o non è verificato.

Regole (le stesse degli altri agenti):
- non inventa dati: se nessun agente sa rispondere, lo dice;
- una segnalazione non verificata resta un'ipotesi;
- l'affidabilità complessiva è la più bassa tra quelle degli agenti usati;
- se un agente fallisce, l'errore è riportato e gli altri risultati restano.

Tipi di richiesta (request_type):
- "question": domanda in linguaggio naturale (instradata per argomento);
- "incident_assessment": valutazione di un incidente già nel database
  (serve context["incident_id"]); NOTA: la valutazione della verifica
  aggiorna verification_status dell'incidente, come fa il Verification Agent.

Uso:
    from agents.janara_orchestrator_agent import handle_request, reassess
    risultato = handle_request({
        "request_id": "R1", "sender": "user", "request_type": "question",
        "question": "Come arrivo al MANN?", "context": {"origin": "Piazza Garibaldi"}
    })
    print(risultato["response"])
"""

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger("neurapolis.janara")

VALID_SENDERS = {"user", "operator", "system"}
VALID_REQUEST_TYPES = {"question", "incident_assessment"}

MAX_AGENT_CALLS = 6          # protezione contro catene di handoff infinite
KNOWN_AGENTS = {"mobility", "tourism"}

CONFIDENCE_ORDER = ["low", "medium", "high"]

TOURISM_WORDS = [
    "museo", "musei", "castello", "castel", "chiesa", "cattedrale", "duomo", "palazzo",
    "teatro", "monument", "cosa vedere", "visitare", "visita", "biglietto", "biglietti",
    "orari", "orario", "apre", "aperto", "chiude", "chiuso", "storia di", "panorama",
    "turist", "piove", "pioggia", "cosa fare",
]
MOBILITY_WORDS = [
    "traffico", "strada", "strade", "bus", "autobus", "metro", "metropolitana", "tram",
    "funicolare", "treno", "linea", "linee", "percorso", "come arrivo", "come si arriva",
    "come raggiungo", "arrivare", "raggiungere", "bloccat", "chiusa", "chiuso al traffico",
    "ritardo", "sciopero", "incidente stradale", "allagament",
]
INCIDENT_PATTERN = re.compile(r"\bincident[ei]\s*(?:n\.?|numero|#)?\s*(\d+)", re.IGNORECASE)


# ============================================================
# Validazione
# ============================================================

def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("La richiesta deve essere un dizionario.")
    if request.get("sender") not in VALID_SENDERS:
        raise ValueError("Mittente non valido: user, operator oppure system.")
    if request.get("request_type") not in VALID_REQUEST_TYPES:
        raise ValueError("Tipologia non valida: question oppure incident_assessment.")
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
            raise ValueError("Per valutare un incidente serve context['incident_id'] numerico.")
    elif not (question or "").strip() and not (context or {}).get("incident_id"):
        raise ValueError("Serve una domanda (question) oppure un incident_id.")


# ============================================================
# Instradamento
# ============================================================

def _has_any(text, words):
    return any(word in text for word in words)


def plan_routing(question, context):
    """
    Decide quali agenti interpellare per una domanda.

    Restituisce {"incident_id", "tourism", "mobility", "reasons"}.
    Nessun agente interpellato = "nessuna competenza riconosciuta".
    """
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

    if tourism:
        reasons.append("Riconosciuto un argomento turistico (luoghi, orari, cosa vedere).")
    if mobility:
        reasons.append("Riconosciuto un argomento di mobilità (percorsi, traffico, trasporti).")
    if not (incident_id is not None or tourism or mobility):
        reasons.append("Nessun argomento di competenza degli agenti riconosciuto.")

    return {"incident_id": incident_id, "tourism": tourism, "mobility": mobility, "reasons": reasons}


# ============================================================
# Chiamate agli agenti (isolate per poterle sostituire nei test)
# ============================================================

def _call_mobility(request):
    from agents.mobility.mobility_agent import analyze_mobility_request
    return analyze_mobility_request(request)


def _call_tourism(request):
    from agents.tourism.tourism_agent import analyze_tourism_request
    return analyze_tourism_request(request)


def _call_social(incident_id):
    from agents.social_intelligence_agent import get_social_intelligence
    return get_social_intelligence(incident_id)


def _call_verification(incident_id):
    from agents.verification_agent import evaluate_incident
    return evaluate_incident(incident_id)


AGENT_CALLERS = {"mobility": lambda r: _call_mobility(r), "tourism": lambda r: _call_tourism(r)}


def _text_of(result):
    """Testo di risposta di un agente (stringa o dizionario annidato)."""
    response = (result or {}).get("response")
    while isinstance(response, dict):
        response = response.get("response")
    return response if isinstance(response, str) else ""


class _Run:
    """Stato di una singola richiesta: traccia delle chiamate ed errori."""

    def __init__(self, request_id, sender):
        self.request_id = request_id
        self.sender = sender
        self.trace = []
        self.results = {}          # nome agente -> lista risultati
        self.errors = []
        self.seen = set()

    def call(self, agent, request_type, question=None, context=None, incident=None, reason=""):
        key = (agent, request_type, question, repr(sorted((context or {}).items(), key=str)),
               repr(incident))
        if key in self.seen:
            return None
        if len(self.trace) >= MAX_AGENT_CALLS:
            self.errors.append({"agent": agent, "error": "Limite di chiamate agli agenti raggiunto."})
            return None
        self.seen.add(key)

        request = {
            "request_id": f"{self.request_id}-{len(self.trace) + 1}",
            "sender": self.sender if self.sender != "system" else "janara",
            "request_type": request_type,
            "question": question,
            "context": dict(context or {}),
        }
        if incident is not None:
            request["incident"] = incident

        entry = {"agent": agent, "request_type": request_type, "reason": reason, "status": "ok"}
        self.trace.append(entry)
        try:
            result = AGENT_CALLERS[agent](request)
        except Exception as error:                       # un agente non deve far cadere Janara
            logger.exception("Errore nell'agente %s", agent)
            entry["status"] = "error"
            entry["error"] = str(error)
            self.errors.append({"agent": agent, "error": str(error)})
            return None
        self.results.setdefault(agent, []).append(result)
        return result


# ============================================================
# Handoff
# ============================================================

def _follow_handoffs(run, result, context):
    """
    Esegue gli handoff suggeriti da un agente verso altri agenti noti.
    Restituisce gli handoff non eseguibili e le informazioni mancanti.
    """
    unresolved, missing = [], []
    for handoff in (result or {}).get("suggested_handoffs") or []:
        agent = handoff.get("agent")
        if agent not in KNOWN_AGENTS:
            unresolved.append({**handoff, "motivo": "Agente sconosciuto a Janara."})
            continue
        h_context = dict(context)
        h_context.update(handoff.get("context") or {})
        if handoff.get("request_type") == "route_request" and not h_context.get("origin"):
            missing.append("Punto di partenza: serve per calcolare il percorso.")
            unresolved.append({**handoff, "motivo": "Manca il punto di partenza."})
            continue
        followed = run.call(agent, handoff.get("request_type", "question"), handoff.get("question"),
                            h_context, reason="Handoff suggerito da un altro agente.")
        if followed:   # gli handoff a catena si fermano per ripetizione o per il limite di chiamate
            u, m = _follow_handoffs(run, followed, h_context)
            unresolved += u
            missing += m
    return unresolved, missing


# ============================================================
# Valutazione di un incidente
# ============================================================

def _assess_incident(run, incident_id, question, context):
    """Social Intelligence + Verification, poi (se pertinente) Mobility."""
    out = {"social": None, "verification": None, "found": True}

    try:
        social = _call_social(incident_id)
        run.trace.append({"agent": "social_intelligence", "request_type": "get_social_intelligence",
                          "reason": "Raccolta delle segnalazioni associate.", "status": "ok"})
    except Exception as error:
        run.trace.append({"agent": "social_intelligence", "status": "error", "error": str(error)})
        run.errors.append({"agent": "social_intelligence", "error": str(error)})
        return out

    if social is None:
        out["found"] = False
        run.trace[-1]["status"] = "not_found"
        return out
    out["social"] = social

    try:
        out["verification"] = _call_verification(incident_id)
        run.trace.append({"agent": "verification", "request_type": "evaluate_incident",
                          "reason": "Valutazione delle evidenze (aggiorna verification_status).",
                          "status": "ok"})
    except Exception as error:
        run.trace.append({"agent": "verification", "status": "error", "error": str(error)})
        run.errors.append({"agent": "verification", "error": str(error)})

    incident = dict(social["incident"])
    if out["verification"]:
        incident["verification_status"] = out["verification"]["verification_status"]

    # Il Mobility Agent riceve i dati dal chiamante: gli passiamo l'incidente.
    mobility_incident = {k: incident.get(k) for k in
                         ("id", "event_type", "description", "location", "verification_status")}
    from agents.mobility.mobility_agent import classify_problem
    problem = classify_problem(mobility_incident, question)
    if problem and problem["type"] != "non_classificato":
        run.call("mobility", "incident_analysis", question, context, incident=mobility_incident,
                 reason="L'incidente ha effetti sulla mobilità.")
    return out


# ============================================================
# Composizione della risposta
# ============================================================

STATUS_TEXT = {
    "unverified": "non verificata: va trattata come ipotesi",
    "partially_confirmed": "parzialmente confermata (una sola fonte indipendente)",
    "confirmed": "confermata",
    "contradicted": "smentita da una fonte ufficiale",
    "conflicting": "con evidenze contrastanti: serve un controllo umano",
}


def _combine_confidence(results):
    levels, reasons = [], []
    for result in results:
        confidence = (result or {}).get("confidence") or {}
        if confidence.get("level") in CONFIDENCE_ORDER:
            levels.append(confidence["level"])
            reasons.extend(confidence.get("reasons") or [])
    if not levels:
        return {"level": "not_applicable", "reasons": ["Nessun dato usato per la risposta."]}
    lowest = min(levels, key=CONFIDENCE_ORDER.index)
    return {"level": lowest, "reasons": ["Affidabilità complessiva = la più bassa tra gli agenti usati."] + reasons}


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        key = repr(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _incident_paragraph(assessment):
    social, verification = assessment["social"], assessment["verification"]
    incident = social["incident"]
    status = (verification or {}).get("verification_status") or incident["verification_status"]
    lines = [f"Segnalazione {incident['id']} ({incident['description'] or 'senza descrizione'}"
             f"{', ' + incident['location'] if incident['location'] else ''}): "
             f"{STATUS_TEXT.get(status, status)}."]
    analysis = social["social_analysis"]
    lines.append(f"Segnalazioni social associate: {analysis['total_reports']}"
                 f" da {analysis['distinct_authors']} autori distinti.")
    if verification:
        lines.append(f"Evidenze registrate: {verification['total_evidence']} "
                     f"(conferme ufficiali {verification['official_confirmations']}, "
                     f"fonti indipendenti {verification['independent_sources']}, "
                     f"contraddizioni {verification['contradictions']}).")
    return " ".join(lines), status


def _compose(run, sender, routing, assessment, unresolved_handoffs):
    parts, limitations, missing, checks, handoffs = [], [], [], [], list(unresolved_handoffs)
    all_results = []
    incident_status = None

    if assessment and assessment["found"] and assessment["social"]:
        paragraph, incident_status = _incident_paragraph(assessment)
        parts.append(paragraph)
        limitations.extend(assessment["social"]["social_analysis"]["limitations"])
        if incident_status in ("unverified", "partially_confirmed", "conflicting"):
            checks.append("Verificare l'evento con una fonte ufficiale prima di agire.")

    for agent in ("tourism", "mobility"):
        for result in run.results.get(agent, []):
            all_results.append(result)
            text = _text_of(result)
            if text:
                parts.append(text)
            limitations.extend(result.get("limitations") or [])
            missing.extend(result.get("missing_information") or [])
            checks.extend(result.get("required_checks") or [])
            handoffs.extend(h for h in (result.get("suggested_handoffs") or [])
                            if h.get("agent") not in KNOWN_AGENTS)

    if assessment and not assessment["found"]:
        parts.append("Incidente non trovato nel database: non posso dire nulla su di esso.")
        missing.append("Un identificativo di incidente esistente.")

    if not parts:
        parts.append("Non so rispondere a questa richiesta: non riguarda mobilità, turismo o "
                     "segnalazioni di incidenti. Prova a chiedere, ad esempio, come raggiungere un "
                     "luogo, gli orari di un museo o lo stato di una segnalazione.")
        limitations.append("Nessun agente ha le competenze per questa richiesta.")

    for error in run.errors:
        limitations.append(f"L'agente {error['agent']} non ha risposto ({error['error']}): "
                           "la risposta può essere incompleta.")

    confidence = _combine_confidence(all_results)
    if incident_status in ("unverified", "partially_confirmed", "conflicting") and \
            confidence["level"] in ("high", "medium"):
        confidence = {"level": "low",
                      "reasons": ["La segnalazione non è confermata: l'analisi resta un'ipotesi."]
                                 + confidence["reasons"]}

    text = "\n\n".join(parts)
    if sender in ("operator", "system"):
        called = ", ".join(f"{t['agent']}" for t in run.trace) or "nessuno"
        text += f"\n\nAgenti interpellati: {called}. Affidabilità: {confidence['level']}."

    return {
        "text": text,
        "confidence": confidence,
        "limitations": _dedupe(limitations),
        "missing_information": _dedupe(missing),
        "required_checks": _dedupe(checks),
        "unresolved_handoffs": handoffs,
        "incident_status": incident_status,
    }


# ============================================================
# Punto di ingresso
# ============================================================

def handle_request(request):
    """Punto di ingresso di Janara: riceve una richiesta e coordina gli agenti."""

    validate_request(request)

    request_id = request.get("request_id") or "JANARA"
    sender = request["sender"]
    question = request.get("question")
    context = dict(request.get("context") or {})

    run = _Run(request_id, sender)

    if request["request_type"] == "incident_assessment":
        routing = {"incident_id": int(context["incident_id"]), "tourism": False, "mobility": False,
                   "reasons": ["Valutazione esplicita di un incidente."]}
    else:
        routing = plan_routing(question, context)

    assessment = None
    if routing["incident_id"] is not None:
        assessment = _assess_incident(run, routing["incident_id"], question, context)

    unresolved, missing_extra = [], []
    mobility_handled = False

    if routing["tourism"]:
        tourism_type = "question"
        result = run.call("tourism", tourism_type, question, context, reason="Argomento turistico.")
        if result:
            u, m = _follow_handoffs(run, result, context)
            unresolved += u
            missing_extra += m
            # Se il turismo ha già girato la domanda sul percorso, non la ripetiamo.
            mobility_handled = any(h.get("agent") == "mobility"
                                   for h in result.get("suggested_handoffs") or [])

    if routing["mobility"] and not mobility_handled and not any(t["agent"] == "mobility" for t in run.trace):
        result = run.call("mobility", "question", question, context, reason="Argomento di mobilità.")
        if result:
            u, m = _follow_handoffs(run, result, context)
            unresolved += u
            missing_extra += m

    composed = _compose(run, sender, routing, assessment, unresolved)
    composed["missing_information"] = _dedupe(composed["missing_information"] + missing_extra)

    return {
        "agent": "janara_orchestrator_agent",
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if not run.errors else "completed_with_errors",
        "request": {"sender": sender, "request_type": request["request_type"],
                    "question": question, "context": context},
        "routing": routing,
        "agents_called": run.trace,
        "agent_results": run.results,
        "incident": assessment["social"]["incident"] if assessment and assessment["social"] else None,
        "response": composed["text"],
        "confidence": composed["confidence"],
        "missing_information": composed["missing_information"],
        "required_checks": composed["required_checks"],
        "limitations": composed["limitations"],
        "unresolved_handoffs": composed["unresolved_handoffs"],
        "errors": run.errors,
    }


# ============================================================
# Cambio di condizioni
# ============================================================

def _place_ids(result):
    ids = set()
    for item in (result.get("agent_results", {}).get("tourism") or []):
        ids.update(p["id"] for p in item.get("places", []))
    return ids


def reassess(previous, changes):
    """
    Rivaluta una richiesta già svolta quando cambiano le condizioni
    (es. {"weather": "rain"} oppure un nuovo "when").

    Rilancia la stessa richiesta con il contesto aggiornato e spiega cosa è
    cambiato: affidabilità, stato di verifica dell'incidente, luoghi proposti.
    """
    if not isinstance(previous, dict) or "request" not in previous:
        raise ValueError("Serve il risultato di una precedenza chiamata a handle_request.")
    if not isinstance(changes, dict) or not changes:
        raise ValueError("Indicare almeno un cambiamento di condizioni (dizionario non vuoto).")

    original = previous["request"]
    context = {**(original.get("context") or {}), **changes}
    new = handle_request({
        "request_id": f"{previous['request_id']}-rev",
        "sender": original["sender"],
        "request_type": original["request_type"],
        "question": original.get("question"),
        "context": context,
    })

    diff = []
    old_level, new_level = previous["confidence"]["level"], new["confidence"]["level"]
    if old_level != new_level:
        diff.append(f"Affidabilità: da {old_level} a {new_level}.")
    old_status = (previous.get("incident") or {}).get("verification_status")
    new_status = (new.get("incident") or {}).get("verification_status")
    if old_status != new_status and new_status:
        diff.append(f"Stato di verifica: da {old_status} a {new_status}.")
    old_places, new_places = _place_ids(previous), _place_ids(new)
    if old_places - new_places:
        diff.append("Luoghi non più proposti: " + ", ".join(sorted(old_places - new_places)) + ".")
    if new_places - old_places:
        diff.append("Nuovi luoghi proposti: " + ", ".join(sorted(new_places - old_places)) + ".")
    if previous["response"] != new["response"] and not diff:
        diff.append("La risposta è cambiata nei dettagli.")
    if not diff:
        diff.append("Le nuove condizioni non cambiano la risposta.")

    new["revision"] = {"changes_applied": changes, "differences": diff,
                       "previous_request_id": previous["request_id"]}
    return new


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    demo = handle_request({
        "request_id": "JANARA-DEMO-1", "sender": "user", "request_type": "question",
        "question": "Come arrivo al MANN?", "context": {"origin": "Piazza Garibaldi"},
    })
    print(demo["response"])
    print(json.dumps(demo["agents_called"], indent=2, ensure_ascii=False))
