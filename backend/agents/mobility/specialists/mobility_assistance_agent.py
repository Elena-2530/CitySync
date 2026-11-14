"""
Mobility Assistance: prepara la risposta per Janara, l'operatore o l'utente.

Usa SOLO i risultati degli specialisti: non aggiunge dati. Se un dato manca,
lo dice. Il registro cambia in base al destinatario:
  - user:     linguaggio semplice, passi del percorso, avvertenze chiare;
  - operator: sintesi tecnica con impatti, verifiche e alternative;
  - janara:   riepilogo strutturato per il coordinamento tra agenti.
"""

STATUS_WORDS = {"suspended": "sospesa", "cancelled": "cancellata"}

LEVEL_LABELS = {
    "high": "alta", "medium": "media", "low": "bassa",
    "not_applicable": "non applicabile"
}


# ----------------------------------------------------------------------
# Formattazione
# ----------------------------------------------------------------------

def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def route_steps_text(route):
    """Passi del percorso in italiano, uno per riga."""
    lines = []
    for step in (route or {}).get("steps", []):
        if step.get("type") == "walk":
            lines.append(
                f"A piedi da {step['from']} a {step['to']} "
                f"(circa {step['minutes']} min, {step['distance_m']} m)"
            )
        elif step.get("type") == "ride":
            lines.append(
                f"{step['line']} da {step['from']} a {step['to']} "
                f"({_plural(step['stops_count'], 'fermata', 'fermate')}, "
                f"circa {step['minutes']} min più un'attesa stimata di "
                f"{step.get('wait_estimate_min', 0)} min)"
            )
    return lines


def route_summary(route):
    """Riga di sintesi di un percorso (linee e tempo stimato)."""
    if not route:
        return ""
    used = ", ".join(route.get("lines", [])) or "solo a piedi"
    cambi = route.get("transfers", 0)
    return (
        f"{used} · circa {route.get('total_minutes_estimate', '?')} min · "
        f"{_plural(cambi, 'cambio', 'cambi')}"
    )


def _exclusion_sentences(route_plan):
    sentences = []
    for item in (route_plan or {}).get("excluded_lines", []):
        word = STATUS_WORDS.get(item.get("status"), "non disponibile")
        if item.get("between"):
            a, b = item["between"]
            sentences.append(f"{item['line']} risulta {word} tra {a} e {b}")
        else:
            sentences.append(f"{item['line']} risulta {word}")
    return sentences


def _numbered(items):
    return "\n".join(f"{i}. {text}" for i, text in enumerate(items, start=1))


def _bullets(items):
    return "\n".join(f"- {text}" for text in items)


# ----------------------------------------------------------------------
# Contenuti per tipo di domanda
# ----------------------------------------------------------------------

def _route_block(route_plan, recommended, alternatives, technical):
    """Testo sul percorso. Restituisce (testo, avvertenze)."""
    caveats = []
    plan = route_plan or {}
    origin = (plan.get("origin") or {}).get("name", "la partenza")
    destination = (plan.get("destination") or {}).get("name", "la destinazione")

    if plan.get("unresolved"):
        names = ", ".join(f"\"{n}\"" for n in plan["unresolved"])
        return (
            f"Non riconosco {names}. Indica un luogo più preciso, per esempio "
            "una fermata, una piazza o un monumento."
        ), caveats

    parts = []
    exclusions = _exclusion_sentences(plan)

    if recommended:
        parts.append(
            f"Da {origin} a {destination} il percorso consigliato è:\n"
            + _numbered(route_steps_text(recommended))
            + f"\nTempo totale stimato: circa {recommended['total_minutes_estimate']} minuti."
        )
        for i, alt in enumerate(alternatives, start=1):
            label = "Alternativa" if len(alternatives) == 1 else f"Alternativa {i}"
            parts.append(f"{label}: {route_summary(alt)}.")
        if exclusions:
            parts.append(
                "Ho tenuto conto delle interruzioni segnalate: "
                + "; ".join(exclusions) + "."
            )
        caveats.append(
            "I tempi sono stime sulla rete programmata: non ho dati in tempo "
            "reale su frequenze, ritardi o soppressioni."
        )
        if (plan.get("network") or {}).get("data_type") == "static_demo":
            caveats.append(
                "La rete di trasporto usata è dimostrativa e ridotta: "
                "non comprende tutte le linee di Napoli."
            )
    else:
        issue = [
            o for o in plan.get("options", [])
            if o.get("status") == "disrupted"
        ]
        if issue:
            parts.append(
                f"Da {origin} a {destination} il percorso più diretto è "
                f"{route_summary(issue[0])}, ma una linea usata risulta in "
                "ritardo o con criticità: non posso consigliarlo senza verifiche."
            )
        else:
            parts.append(
                f"Non ho trovato un percorso verificato da {origin} a "
                f"{destination} con le informazioni disponibili."
            )
        if exclusions:
            parts.append("Interruzioni considerate: " + "; ".join(exclusions) + ".")
        parts.append(
            "Prima di spostarti consulta le informazioni ufficiali degli "
            "operatori (ANM, EAV, Trenitalia)."
        )

    for warning in (recommended or {}).get("warnings", [])[1:]:
        caveats.append(warning)

    return "\n\n".join(parts), caveats


def _zone_block(hints, technical):
    """Testo sulla zona di un evento: fermate e linee vicine, assi principali."""
    hints = hints or {}
    parts = []
    transit = hints.get("transit_in_area") or []
    if transit:
        parts.append(
            "Trasporto pubblico nella zona: "
            + "; ".join(
                f"{t['line']} (fermata {t['stop']}, a circa {t['distance_m']} m)"
                for t in transit
            ) + "."
        )
    roads = hints.get("potentially_affected_roads")
    if roads:
        label = (
            "Assi stradali principali della zona (ipotesi da verificare, non strade accertate come coinvolte)"
            if technical else
            "Strade principali della zona, dove conviene informarsi prima di partire"
        )
        parts.append(f"{label}: " + ", ".join(roads["roads"] + roads.get("other", [])) + ".")
    return "\n\n".join(parts)


def _live_data_missing(traffic, transport):
    traffic = traffic or {}
    transport = transport or {}
    return {
        "traffic": traffic.get("analysis_status") in (None, "insufficient_data"),
        "transport": transport.get("analysis_status") in (None, "insufficient_data"),
    }


def _transport_status_block(transport):
    services = (transport or {}).get("services") or []
    known = [s for s in services if s.get("status") != "unknown"]
    if not known:
        return (
            "Non ho informazioni aggiornate sullo stato delle linee. "
            "Controlla l'app o il sito dell'operatore della linea che ti interessa."
        )
    lines = []
    for s in known:
        note = " (dato non aggiornato)" if s.get("data_outdated") else ""
        lines.append(f"{s['service']}: {s['status_description']}{note}")
    return "Stato dei servizi secondo i dati ricevuti:\n" + _bullets(lines)


# ----------------------------------------------------------------------
# Risposta
# ----------------------------------------------------------------------

def generate_response(sender, question=None, traffic=None, transport=None,
                      routes=None, impact=None, intent="general",
                      route_plan=None, hints=None, incident=None,
                      confidence=None, problem=None, required_checks=None):
    """Prepara una risposta adeguata al destinatario."""

    sender = (sender or "user").lower()
    traffic = traffic or {}
    transport = transport or {}
    routes = routes or {}
    impact = impact or {}
    route_plan = route_plan or {}
    hints = hints or {}
    required_checks = list(required_checks or [])

    missing = []
    for part in (traffic, transport, routes):
        missing.extend(part.get("missing_information", []))
    if route_plan.get("unresolved"):
        missing.append(
            "Luoghi non riconosciuti: " + ", ".join(route_plan["unresolved"]) + "."
        )
    missing = list(dict.fromkeys(missing))

    recommended = routes.get("recommended_route")
    alternatives = routes.get("alternative_routes", [])
    impacts = impact.get("possible_impacts", [])
    technical = sender in {"operator", "janara"}
    no_live = _live_data_missing(traffic, transport)

    caveats = []
    blocks = []

    # ---- contenuto principale in base all'intento ----
    planner_ran = bool(route_plan.get("origin") or route_plan.get("unresolved"))

    if intent == "route":
        text, route_caveats = _route_block(route_plan, recommended, alternatives, technical)
        blocks.append(text)
        caveats.extend(route_caveats)

    elif intent == "missing_info":
        if missing:
            blocks.append("Informazioni mancanti:\n" + _bullets(missing))
        else:
            blocks.append("Con i dati ricevuti non risultano informazioni mancanti.")

    elif intent == "affected_roads":
        zone = _zone_block(hints, technical=True)
        confirmed = [
            f"{c['road']}: {c['description']}"
            for c in traffic.get("traffic_conditions", [])
            if not c.get("data_outdated") and c.get("status") not in ("normal", "unknown")
        ]
        if confirmed:
            blocks.append("Strade con condizioni segnalate (dati recenti):\n" + _bullets(confirmed))
        if zone:
            blocks.append(zone)
        if not confirmed and not zone:
            blocks.append(
                "Non ho dati sufficienti per indicare le strade interessate: "
                "serve conoscere la zona dell'evento o avere dati sulla viabilità."
            )

    elif intent == "avoid_traffic":
        blocks.append(
            "Non ho dati sul traffico in tempo reale, quindi non posso dirti "
            "dove ci sono code in questo momento."
        )
        zone = _zone_block(hints, technical=technical)
        if zone:
            blocks.append(zone)
        blocks.append(
            "Se mi dici da dove parti e dove vuoi andare, ti propongo un "
            "percorso con i mezzi pubblici."
        )

    elif intent == "transport_status":
        blocks.append(_transport_status_block(transport))

    else:
        # analisi di un evento (Janara/operatore) o domanda generica
        if impact.get("summary"):
            blocks.append(impact["summary"])
        if impacts:
            blocks.append(
                ("Impatti potenziali (ipotesi da verificare):\n" if technical
                 else "Possibili conseguenze sugli spostamenti:\n") + _bullets(impacts)
            )
        zone = _zone_block(hints, technical=technical)
        if zone:
            blocks.append(zone)
        if not blocks:
            blocks.append(
                "Posso aiutarti a trovare un percorso con i mezzi pubblici: "
                "dimmi da dove parti e dove vuoi andare."
                if not technical else
                "Non ci sono elementi sufficienti per una valutazione della mobilità."
            )

    # se è stato calcolato un percorso ma la domanda era su altro, lo si aggiunge
    if planner_ran and intent != "route":
        text, route_caveats = _route_block(route_plan, recommended, alternatives, technical)
        blocks.append(text)
        caveats.extend(route_caveats)

    # ---- avvertenze comuni ----
    if intent in {"avoid_traffic", "affected_roads"} and no_live["traffic"]:
        caveats.append("Non sono disponibili dati aggiornati sul traffico.")
    if technical and required_checks:
        blocks.append("Verifiche necessarie:\n" + _bullets(required_checks))

    level = (confidence or {}).get("level")
    if technical and level:
        blocks.append(f"Affidabilità dell'analisi: {LEVEL_LABELS.get(level, level)}.")

    caveats = list(dict.fromkeys(caveats))
    if caveats:
        blocks.append(
            ("Attenzione: " if not technical else "Limiti: ")
            + " ".join(caveats)
        )

    # ---- intestazione secondo il destinatario ----
    if sender == "janara":
        label = (problem or {}).get("label")
        head = (
            f"Mobilità · {label}. " if label else "Mobilità. "
        ) + (
            f"Impatti potenziali: {len(impacts)}. "
            f"Alternative di percorso: {'disponibili' if recommended else 'non disponibili'}. "
            f"Informazioni mancanti: {len(missing)}."
        )
        response = head + "\n\n" + "\n\n".join(blocks)
    else:
        response = "\n\n".join(blocks)

    return {
        "recipient": sender,
        "question": question,
        "intent": intent,
        "response": response,
        "recommended_route": recommended,
        "alternatives": alternatives,
        "route_steps": route_steps_text(recommended) if recommended else [],
        "caveats": caveats,
        "missing_information": missing,
        "possible_impacts": impacts,
    }
