"""
Tourism Agent di NEURAPOLIS.

Risponde a Janara, operatori e utenti su luoghi e monumenti di Napoli:
dove si trovano, storia, orari, prezzi, cosa vedere nei dintorni, cosa fare
con il maltempo. Usa regole esplicite e dati con fonte dichiarata.

Regole di progetto:
- un orario viene riportato solo se è in una fonte, con tipo e data della fonte;
- un luogo non presente nei dati non viene inventato;
- per i percorsi l'agente non risponde: indica a Janara di chiamare il Mobility Agent.
"""

import logging
from datetime import datetime, timezone

from agents.tourism import opening_hours, question_parser, tourism_response as tr
from agents.tourism.tourism_data import places as places_data

logger = logging.getLogger("neurapolis.tourism")

VALID_SENDERS = {"janara", "user", "operator"}
VALID_REQUEST_TYPES = {"place_info", "search", "nearby", "question"}
RAIN_WORDS = {"rain", "storm", "pioggia", "temporale", "maltempo"}
RAIN_FRIENDLY = {"indoor", "covered"}
DEFAULT_RADIUS_M = 1000
DEFAULT_LIMIT = 5


def validate_request(request):
    """Controlla che la richiesta sia strutturata correttamente."""

    if not isinstance(request, dict):
        raise ValueError("La richiesta deve essere un dizionario.")

    if request.get("sender") not in VALID_SENDERS:
        raise ValueError("Mittente non valido: janara, user oppure operator.")

    request_type = request.get("request_type")
    if request_type not in VALID_REQUEST_TYPES:
        raise ValueError("Tipologia non valida: place_info, search, nearby oppure question.")

    context = request.get("context", {})
    if not isinstance(context, dict):
        raise ValueError("Il campo context deve essere un dizionario.")

    question = request.get("question")
    if question is not None and not isinstance(question, str):
        raise ValueError("Il campo question deve essere una stringa.")

    if request_type == "place_info" and not context.get("place") and not question:
        raise ValueError("Per le informazioni su un luogo serve context['place'] oppure una domanda.")

    if request_type == "nearby" and not (context.get("location") or context.get("place")):
        raise ValueError("Per cercare luoghi vicini serve context['location'] oppure context['place'].")

    return True


def _card(place, distance_m=None, when=None):
    """Scheda sintetica di un luogo, adatta alla risposta strutturata."""
    hours = place.get("hours") or {"status": "unknown"}
    card = {
        "id": place["id"],
        "name": place["name"],
        "categories": place["categories"],
        "neighborhood": place.get("neighborhood"),
        "address": place.get("address"),
        "lat": place["lat"],
        "lon": place["lon"],
        "coordinates_approximate": True,
        "indoor": place.get("indoor"),
        "description": place.get("description"),
        "highlights": place.get("highlights", []),
        "hours": {
            "status": hours["status"],
            "summary": opening_hours.weekly_summary(place),
            "last_entry": hours.get("last_entry"),
            "reliability": opening_hours.reliability(hours),
            "source": hours.get("source"),
            "notes": hours.get("notes"),
        },
        "tickets": place.get("tickets"),
    }
    if distance_m is not None:
        card["distance_m"] = distance_m
    if when is not None and hours["status"] in ("official", "secondary"):
        card["open_status"] = opening_hours.open_status(place, when)
    return card


def _resolve_center(context, question, resolved_place, data):
    """Punto di partenza per le ricerche 'vicino a': coordinate, nome o zona."""
    location = context.get("location")

    if isinstance(location, dict) and "lat" in location and "lon" in location:
        try:
            return {"lat": float(location["lat"]), "lon": float(location["lon"]), "name": "la posizione indicata"}
        except (TypeError, ValueError):
            return None

    if isinstance(location, str):
        place = places_data.find_place(location, data)
        if place:
            return {"lat": place["lat"], "lon": place["lon"], "name": place["name"], "place_id": place["id"]}
        area = places_data.find_area(location, data)
        if area:
            return {"lat": area["lat"], "lon": area["lon"], "name": area["name"]}
        return None

    if resolved_place:
        return {"lat": resolved_place["lat"], "lon": resolved_place["lon"],
                "name": resolved_place["name"], "place_id": resolved_place["id"]}

    area = places_data.find_area(question, data)
    if area:
        return {"lat": area["lat"], "lon": area["lon"], "name": area["name"]}
    return None


def _confidence(intent, hours_rel, found_anything, unresolved):
    """Affidabilità della risposta, con i motivi."""
    if intent == "general":
        return {"level": "not_applicable", "reasons": ["La richiesta non riguarda un luogo specifico."]}
    if unresolved or not found_anything:
        return {"level": "low", "reasons": ["Il luogo richiesto non è tra quelli presenti nei dati."]}
    if intent in ("hours", "tickets"):
        level = {"high": "high", "medium": "medium"}.get(hours_rel, "low")
        reasons = {
            "high": ["Orario da fonte ufficiale aggiornata di recente."],
            "medium": ["Dato da fonte ufficiale, ma senza data recente di aggiornamento."],
        }.get(hours_rel, ["Dato mancante o da fonte non ufficiale e datata."])
        return {"level": level, "reasons": reasons}
    return {"level": "medium", "reasons": [
        "Descrizioni e posizioni vengono da una base di conoscenza interna, non verificate fonte per fonte; coordinate approssimate."
    ]}


def analyze_tourism_request(request):
    """
    Punto di ingresso del Tourism Agent.

    Riceve una richiesta da Janara, da un utente o da un operatore e
    restituisce una risposta strutturata (testo, luoghi, fonti, verifiche).
    """

    validate_request(request)

    data = places_data.load()
    request_id = request.get("request_id")
    sender = request["sender"]
    request_type = request["request_type"]
    question = request.get("question")
    context = dict(request.get("context") or {})

    parsed = question_parser.parse_question(question) if question else {
        "intent": "general", "category": None, "asks_route": False
    }

    # --- intento ---------------------------------------------------------
    if request_type == "search":
        intent = "search"
    elif request_type == "nearby":
        intent = "nearby"
    elif request_type == "place_info" and parsed["intent"] in ("general", "search", "nearby", "indoor"):
        intent = "history"
    else:
        intent = parsed["intent"]

    weather = str(context.get("weather", "")).lower()
    raining = weather in RAIN_WORDS or intent == "indoor"

    # --- luogo e posizione ----------------------------------------------
    unresolved = []
    place = None
    if context.get("place"):
        place = places_data.find_place(context["place"], data)
        if place is None:
            unresolved.append(str(context["place"]))
    if place is None and not unresolved and question:
        place = places_data.find_place(question, data)

    category = context.get("category") or parsed["category"]

    # Domande senza parole chiave chiare: si decide in base a ciò che è stato riconosciuto.
    if intent == "general" and place is not None:
        intent = "where" if parsed["asks_route"] else "history"
    elif intent == "general" and category:
        intent = "search"
    elif intent == "search" and place is not None and request_type == "question":
        intent = "history"   # "Cosa vedere al MANN?" → cosa c'è dentro il luogo

    needs_place = intent in ("hours", "tickets", "where", "history")
    when_info = opening_hours.parse_when(question, context)

    shown = []            # luoghi della risposta (schede)
    blocks = []           # parti del testo
    caveats, checks, missing = [], [], []
    hours_rel = "none"
    handoffs = []

    # --- risposte per intento ---------------------------------------------
    if needs_place and place is None:
        if unresolved:
            blocks.append(f"Non ho informazioni su \"{unresolved[0]}\".")
        else:
            blocks.append("Di quale luogo vuoi parlare?")
            missing.append("Il luogo di cui si chiede (nome del monumento o del museo).")
        blocks.append("Posso aiutarti con: " + ", ".join(p["name"] for p in places_data.all_places(data)) + ".")

    elif intent == "hours":
        answer = tr.hours_answer(place, when_info)
        blocks.append(answer["text"])
        caveats += answer["caveats"]; checks += answer["checks"]; missing += answer["missing"]
        hours_rel = answer["reliability"]
        shown.append(_card(place, when=when_info["datetime"]))

    elif intent == "tickets":
        answer = tr.tickets_answer(place)
        blocks.append(answer["text"])
        checks += answer["checks"]; missing += answer["missing"]
        hours_rel = answer["reliability"]
        shown.append(_card(place))

    elif intent == "where":
        blocks.append(tr.where_text(place))
        caveats.append("Le coordinate sono approssimate: usa l'indirizzo per la navigazione.")
        shown.append(_card(place))

    elif intent == "history":
        blocks.append(tr.history_text(place))
        shown.append(_card(place))

    elif intent in ("nearby", "indoor"):
        center = _resolve_center(context, question, place, data)
        if center is None and intent == "nearby":
            blocks.append("Non ho capito rispetto a quale punto cercare. Indica un luogo o una zona (per esempio Municipio o Chiaia).")
            missing.append("Il punto di partenza della ricerca (luogo, zona o coordinate).")
        else:
            radius = int(context.get("radius_m") or DEFAULT_RADIUS_M)
            limit = int(context.get("limit") or DEFAULT_LIMIT)
            if center is not None:
                found = places_data.nearby(center["lat"], center["lon"], radius, data,
                                           exclude_id=center.get("place_id"))
            else:
                found = [{"place": p, "distance_m": None} for p in places_data.all_places(data)]

            if raining:
                dry = [f for f in found if f["place"].get("indoor") in RAIN_FRIENDLY or f["place"].get("indoor") == "partial"]
                wet = [f for f in found if f not in dry]
                found = dry
                if wet:
                    caveats.append("Con la pioggia conviene evitare: " + ", ".join(f["place"]["name"] for f in wet) + ".")

            found = found[:limit]
            where = f" vicino a {center['name']}" if center else ""
            if found:
                title = f"Luoghi al coperto{where}:" if raining else f"Luoghi da vedere{where} (entro {radius} m):"
                blocks.append(title + "\n" + tr.places_list(found, with_distance=center is not None))
                for item in found:
                    shown.append(_card(item["place"], item.get("distance_m"), when_info["datetime"] if raining else None))
                if raining:
                    closed_now = [c["name"] for c in shown
                                  if c.get("open_status", {}).get("status") == "closed"]
                    if closed_now:
                        caveats.append("Secondo gli orari disponibili risultano chiusi adesso: " + ", ".join(closed_now) + ".")
                    checks.append("Verificare gli orari dei luoghi indicati prima di andare.")
            else:
                blocks.append(f"Non ho luoghi{' al coperto' if raining else ''}{where} entro {radius} m.")

    elif intent == "search":
        found = places_data.by_category(category, data) if category else places_data.all_places(data)
        found = found[: int(context.get("limit") or 8)]
        if found:
            title = "Ecco cosa ho trovato:" if category else "Ecco alcuni luoghi da visitare a Napoli:"
            blocks.append(title + "\n" + tr.places_list(found))
            shown += [_card(p) for p in found]
        else:
            blocks.append("Non ho luoghi di questa categoria.")

    else:  # general
        blocks.append("Posso dirti dove si trovano monumenti e musei di Napoli, la loro storia, gli orari e i prezzi "
                      "(quando li conosco), cosa vedere nei dintorni e cosa fare se piove. Per esempio: "
                      "\"Quando apre Castel Nuovo?\" oppure \"Cosa vedere vicino a Municipio?\".")

    # --- percorsi: li gestisce il Mobility Agent -----------------------------
    if parsed["asks_route"] and place is not None:
        blocks.append(f"Per sapere come arrivare a {place['name']} serve il piano dei percorsi (Mobility Agent).")
        handoffs.append({
            "agent": "mobility",
            "request_type": "route_request",
            "context": {"origin": context.get("origin"), "destination": place["name"]},
            "reason": "La richiesta riguarda come raggiungere il luogo."
        })
        if not context.get("origin"):
            missing.append("Il punto di partenza per calcolare il percorso.")

    # --- testo finale secondo il destinatario --------------------------------
    caveats = list(dict.fromkeys(caveats))
    checks = list(dict.fromkeys(checks))
    missing = list(dict.fromkeys(missing))
    confidence = _confidence(intent, hours_rel, bool(shown), bool(unresolved))

    text = "\n\n".join(blocks)
    if caveats:
        text += "\n\n" + ("Attenzione: " if sender == "user" else "Limiti: ") + " ".join(caveats)
    if sender != "user":
        sources = [c["hours"]["source"]["url"] for c in shown if c["hours"].get("source")]
        if sources:
            text += "\n\nFonti: " + ", ".join(dict.fromkeys(sources))
        if intent != "general":
            labels = {"high": "alta", "medium": "media", "low": "bassa"}
            text += f"\n\nAffidabilità: {labels.get(confidence['level'], confidence['level'])}."
    if sender == "janara":
        text = f"Turismo · {intent}. Luoghi trovati: {len(shown)}.\n\n" + text

    limitations = [
        "Gli orari sono riportati solo se presenti in una fonte, con tipo e data della fonte, e vanno verificati sul sito ufficiale.",
        "Descrizioni e posizioni sono di conoscenza generale; le coordinate sono approssimate.",
        "Il Tourism Agent non conosce eventi, scioperi o chiusure straordinarie in corso.",
        f"I dati comprendono {len(places_data.all_places(data))} luoghi: non è un elenco completo delle attrazioni di Napoli.",
    ]

    result = {
        "agent": "tourism_agent",
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "analysis_completed",
        "request": {"sender": sender, "request_type": request_type, "question": question, "intent": intent},
        "places": shown,
        "unresolved_places": unresolved,
        "missing_information": missing,
        "required_checks": checks,
        "confidence": confidence,
        "suggested_handoffs": handoffs,
        "response": {
            "recipient": sender,
            "question": question,
            "response": text,
            "caveats": caveats,
            "missing_information": missing,
        },
        "limitations": limitations,
    }

    logger.info("Richiesta Tourism completata: %s", request_id or "senza ID")
    return result


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    examples = [
        {"request_id": "TOURISM-TEST-001", "sender": "user", "request_type": "question",
         "question": "Quando apre il Castel Nuovo?", "context": {}},
        {"request_id": "TOURISM-TEST-002", "sender": "user", "request_type": "question",
         "question": "Mi racconti la storia della Cappella Sansevero?", "context": {}},
        {"request_id": "TOURISM-TEST-003", "sender": "janara", "request_type": "nearby",
         "question": None, "context": {"location": "Piazza Municipio", "weather": "rain"}},
        {"request_id": "TOURISM-TEST-004", "sender": "user", "request_type": "question",
         "question": "Come arrivo al MANN?", "context": {"origin": "Piazza Garibaldi"}},
    ]

    for example in examples:
        try:
            result = analyze_tourism_request(example)
            print(f"\n===== TOURISM AGENT · {result['request_id']} =====")
            print(json.dumps(result, indent=4, ensure_ascii=False))
        except ValueError as error:
            print(f"Richiesta non valida: {error}")
