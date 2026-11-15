"""
Costruzione delle risposte del Tourism Agent.

Ogni funzione restituisce testo già pronto e le avvertenze da riportare.
Gli orari vengono sempre presentati con tipo di fonte e data, mai da soli.
"""

from datetime import date

from agents.tourism import opening_hours

SOURCE_TYPE_LABEL = {"official": "fonte ufficiale", "secondary": "fonte non ufficiale"}
INDOOR_LABEL = {
    "indoor": "al chiuso", "covered": "coperto", "partial": "in parte al coperto", "outdoor": "all'aperto",
}


def fmt_date(iso):
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def source_line(hours):
    """Frase sulla fonte dell'orario, con la sua affidabilità."""
    source = (hours or {}).get("source")
    if not source:
        return None
    label = SOURCE_TYPE_LABEL.get(source["type"], "fonte")
    if source.get("as_of"):
        text = f"{label}, {source['name']}, aggiornata il {fmt_date(source['as_of'])}"
    else:
        text = f"{label}, {source['name']}, senza data di aggiornamento"
    if source["type"] != "official":
        text += ": potrebbe essere superata"
    return text


def hours_answer(place, when_info, today=None):
    """
    Risposta sugli orari di un luogo.

    Restituisce {"text", "status", "reliability", "caveats", "checks", "missing"}.
    """
    today = today or opening_hours.now_local().date()
    hours = place.get("hours") or {"status": "unknown"}
    reliability = opening_hours.reliability(hours, today)
    name = place["name"]
    caveats, checks, missing = [], [], []

    if hours["status"] == "open_air":
        text = f"{name}: {hours['notes']}"
        return {"text": text, "status": "unknown", "reliability": "none",
                "caveats": [], "checks": [], "missing": []}

    if hours["status"] == "unknown":
        text = f"Non ho orari verificati per {name}. {hours['notes']}"
        missing.append(f"Orari di apertura di {name}.")
        checks.append(f"Consultare il sito ufficiale di {name} per gli orari.")
        return {"text": text, "status": "unknown", "reliability": "none",
                "caveats": [], "checks": checks, "missing": missing}

    summary = opening_hours.weekly_summary(place)
    parts = [f"{name} — orari: {summary}."]

    when = when_info["datetime"]
    if when_info["has_time"]:
        state = opening_hours.open_status(place, when)
        if state["status"] == "unknown":
            parts.append(state["reason"])
        else:
            word = "aperto" if state["status"] == "open" else "chiuso"
            when_text = "Adesso" if when_info["label"] == "adesso" else when_info["label"].capitalize()
            if reliability == "low":
                parts.append(f"{when_text} risulta {word} secondo una fonte non ufficiale e datata. {state['reason']}")
            else:
                parts.append(f"{when_text} risulta {word}. {state['reason']}")
    else:
        schedule = opening_hours.day_schedule(place, when.date())
        day = opening_hours.DAY_NAMES_IT[opening_hours.DAYS[when.weekday()]]
        if schedule["state"] == "hours":
            parts.append(f"{day.capitalize()} è aperto {opening_hours._fmt_ranges(schedule['ranges'])}.")
        elif schedule["state"] == "closed":
            parts.append(f"{day.capitalize()} risulta chiuso.")
        else:
            parts.append(f"Per {day} la fonte non è chiara: possibile chiusura per festività.")

    line = source_line(hours)
    if line:
        parts.append(f"Fonte: {line}.")
    if hours.get("notes"):
        parts.append(hours["notes"])

    caveats.append("Gli orari possono cambiare per festivi, eventi o lavori.")
    checks.append(f"Verificare gli orari di {name} sul sito ufficiale prima di andare.")
    if reliability == "low":
        caveats.append(f"L'orario di {name} viene da una fonte non ufficiale e datata.")

    return {"text": " ".join(parts), "status": opening_hours.open_status(place, when)["status"]
            if when_info["has_time"] else "unknown",
            "reliability": reliability, "caveats": caveats, "checks": checks, "missing": missing}


def tickets_answer(place):
    tickets = place.get("tickets")
    name = place["name"]
    if not tickets:
        return {"text": f"Non ho informazioni verificate sui prezzi di {name}: consulta il sito ufficiale.",
                "reliability": "none", "missing": [f"Prezzi dei biglietti di {name}."],
                "checks": [f"Consultare il sito ufficiale di {name} per i prezzi."]}
    line = source_line({"source": tickets["source"]})
    return {"text": f"{name} — {tickets['info']} ({line}.) I prezzi possono cambiare: verifica prima di andare.",
            "reliability": "medium" if tickets["source"]["type"] == "official" else "low",
            "missing": [], "checks": [f"Verificare i prezzi di {name} sul sito ufficiale."]}


def where_text(place):
    zone = f" Zona: {place['neighborhood']}." if place.get("neighborhood") else ""
    return f"{place['name']} si trova in {place['address']}.{zone}"


def history_text(place):
    text = place["description"]
    if place.get("highlights"):
        text += " Da non perdere: " + ", ".join(place["highlights"]) + "."
    return f"{place['name']}. {text}"


def places_list(items, with_distance=False):
    """Elenco puntato di luoghi (item = luogo oppure {"place", "distance_m"})."""
    lines = []
    for item in items:
        place = item["place"] if "place" in item else item
        extra = []
        if with_distance and "distance_m" in item:
            extra.append(f"a circa {item['distance_m']} m")
        extra.append(INDOOR_LABEL.get(place.get("indoor"), ""))
        extra = ", ".join(e for e in extra if e)
        lines.append(f"- {place['name']} — {extra}" if extra else f"- {place['name']}")
    return "\n".join(lines)
