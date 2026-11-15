"""
Orari di apertura: quando un luogo è aperto e quanto ci si può fidare del dato.

Regola di fondo: l'agente non dice mai "è aperto" se non ha un orario preso da
una fonte; e quando la fonte è non ufficiale o vecchia lo dichiara.
"""

from datetime import date, datetime, time, timedelta

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES_IT = {
    "mon": "lunedì", "tue": "martedì", "wed": "mercoledì", "thu": "giovedì",
    "fri": "venerdì", "sat": "sabato", "sun": "domenica",
}

# Una fonte ufficiale più vecchia di così non è più considerata "recente".
RECENT_DAYS = 120


def now_local():
    """Ora attuale a Roma; se i fusi orari non sono disponibili, ora del computer."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def easter(year):
    """Data della Pasqua (algoritmo gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def is_italian_holiday(day):
    """Festività nazionali (comprese Pasqua e Lunedì dell'Angelo)."""
    # (giorno, mese)
    fixed = {(1, 1), (6, 1), (25, 4), (1, 5), (2, 6), (15, 8), (1, 11), (8, 12), (25, 12), (26, 12)}
    if (day.day, day.month) in fixed:
        return True
    pasqua = easter(day.year)
    return day in (pasqua, pasqua + timedelta(days=1))


def _to_time(value):
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _fmt_ranges(ranges):
    return ", ".join(f"{a}-{b}" for a, b in ranges)


def reliability(hours, today=None):
    """
    Affidabilità dell'orario: high / medium / low / none.

    - high: fonte ufficiale con data di aggiornamento recente;
    - medium: fonte ufficiale senza data o non recente;
    - low: fonte non ufficiale;
    - none: nessun orario disponibile.
    """
    today = today or now_local().date()
    if not hours or hours.get("status") in ("unknown", "open_air"):
        return "none"
    source = hours.get("source")
    if not source:
        return "none"
    if source["type"] != "official":
        return "low"
    as_of = source.get("as_of")
    if not as_of:
        return "medium"
    age = (today - date.fromisoformat(as_of)).days
    return "high" if age <= RECENT_DAYS else "medium"


def day_schedule(place, day):
    """
    Cosa dice la fonte per quel giorno.

    Restituisce {"state": ..., "ranges": [...], "last_entry": ...} con state:
    "hours" (ci sono orari), "closed" (chiuso quel giorno della settimana),
    "holiday_unknown" (festivo: possibile chiusura), "open_air", "unknown".
    """
    hours = place.get("hours") or {"status": "unknown"}
    status = hours.get("status")

    if status == "open_air":
        return {"state": "open_air", "ranges": [], "last_entry": None}
    if status == "unknown" or not hours.get("weekly"):
        return {"state": "unknown", "ranges": [], "last_entry": None}

    if hours.get("closed_on_holidays") and is_italian_holiday(day):
        return {"state": "holiday_unknown", "ranges": [], "last_entry": None}

    ranges = hours["weekly"].get(DAYS[day.weekday()], [])
    if not ranges:
        return {"state": "closed", "ranges": [], "last_entry": None}
    return {"state": "hours", "ranges": ranges, "last_entry": hours.get("last_entry")}


def open_status(place, when):
    """
    Stato del luogo alla data/ora `when`.

    status: "open" | "closed" | "unknown"
    """
    schedule = day_schedule(place, when.date())
    state = schedule["state"]

    if state in ("unknown", "open_air"):
        return {"status": "unknown", "reason": "Nessun orario di apertura disponibile per questo luogo."}
    if state == "holiday_unknown":
        return {"status": "unknown",
                "reason": "Giorno festivo: la fonte indica che nei festivi il luogo è chiuso salvo aperture straordinarie."}
    if state == "closed":
        return {"status": "closed",
                "reason": f"Secondo la fonte è chiuso il {DAY_NAMES_IT[DAYS[when.weekday()]]}."}

    current = when.time()
    for start, end in schedule["ranges"]:
        if _to_time(start) <= current < _to_time(end):
            last = schedule["last_entry"]
            reason = f"Aperto fino alle {end}."
            if last and current >= _to_time(last):
                return {"status": "closed",
                        "reason": f"L'ultimo ingresso è alle {last}: a quest'ora non si può più entrare."}
            if last:
                reason += f" Ultimo ingresso alle {last}."
            return {"status": "open", "reason": reason}
    return {"status": "closed",
            "reason": f"Fuori dall'orario di apertura ({_fmt_ranges(schedule['ranges'])})."}


def weekly_summary(place):
    """Riepilogo leggibile dell'orario settimanale, raggruppando i giorni uguali."""
    hours = place.get("hours") or {}
    weekly = hours.get("weekly")
    if not weekly:
        return None

    groups = []
    for key in DAYS:
        ranges = weekly.get(key, [])
        label = _fmt_ranges(ranges) if ranges else "chiuso"
        if groups and groups[-1]["label"] == label:
            groups[-1]["days"].append(key)
        else:
            groups.append({"label": label, "days": [key]})

    parts = []
    for group in groups:
        first, last = group["days"][0], group["days"][-1]
        days = DAY_NAMES_IT[first] if first == last else f"{DAY_NAMES_IT[first]}-{DAY_NAMES_IT[last]}"
        parts.append(f"{days}: {group['label']}")
    text = "; ".join(parts)
    if hours.get("last_entry"):
        text += f" (ultimo ingresso {hours['last_entry']})"
    return text


def parse_when(question, context=None, now=None):
    """
    Data e ora a cui si riferisce la richiesta.

    Ordine: context["when"] (ISO), poi parole nella domanda ("domani",
    "lunedì", "alle 15:30"), altrimenti adesso.
    Restituisce {"datetime": datetime, "has_time": bool, "label": str}.
    """
    import re

    now = now or now_local()
    context = context or {}

    given = context.get("when")
    if given:
        try:
            parsed = given if isinstance(given, datetime) else datetime.fromisoformat(str(given))
            return {"datetime": parsed.replace(tzinfo=None), "has_time": True, "label": "alla data indicata"}
        except ValueError:
            pass

    text = (question or "").lower()
    day = now.date()
    label = "adesso"
    has_time = True

    if "domani" in text:
        day = day + timedelta(days=1)
        label = "domani"
        has_time = False
    else:
        names = {"lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, "mercoledì": 2, "mercoledi": 2,
                 "giovedì": 3, "giovedi": 3, "venerdì": 4, "venerdi": 4, "sabato": 5, "domenica": 6}
        for word, number in names.items():
            if re.search(rf"\b{word}\b", text):
                delta = (number - day.weekday()) % 7
                day = day + timedelta(days=delta)
                label = word
                has_time = False
                break

    clock = re.search(r"\balle\s+(\d{1,2})(?:[:.](\d{2}))?", text)
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"datetime": datetime.combine(day, time(hour, minute)), "has_time": True,
                    "label": f"{label} alle {hour:02d}:{minute:02d}" if label != "adesso" else f"alle {hour:02d}:{minute:02d}"}

    if has_time:
        return {"datetime": now, "has_time": True, "label": "adesso"}
    return {"datetime": datetime.combine(day, time(12, 0)), "has_time": False, "label": label}
