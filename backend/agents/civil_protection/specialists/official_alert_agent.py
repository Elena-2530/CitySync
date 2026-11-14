
"""Recupero e valutazione temporale delle allerte ufficiali."""

import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.database import get_connection, init_db


ROME_TZ = ZoneInfo("Europe/Rome")

ITALIAN_MONTHS = {
    "gennaio": "January",
    "febbraio": "February",
    "marzo": "March",
    "aprile": "April",
    "maggio": "May",
    "giugno": "June",
    "luglio": "July",
    "agosto": "August",
    "settembre": "September",
    "ottobre": "October",
    "novembre": "November",
    "dicembre": "December",
    "gen": "Jan",
    "feb": "Feb",
    "mar": "Mar",
    "apr": "Apr",
    "mag": "May",
    "giu": "Jun",
    "lug": "Jul",
    "ago": "Aug",
    "set": "Sep",
    "ott": "Oct",
    "nov": "Nov",
    "dic": "Dec",
}

ITALIAN_WEEKDAYS = (
    "lunedì",
    "lunedi",
    "martedì",
    "martedi",
    "mercoledì",
    "mercoledi",
    "giovedì",
    "giovedi",
    "venerdì",
    "venerdi",
    "sabato",
    "domenica",
)

ENGLISH_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _normalize_datetime_text(value):
    """Normalizza testo italiano di date e orari."""
    text = str(value).strip().lower()
    text = text.replace(",", " ")
    text = re.sub(r"\s+", " ", text)

    # Rimuove i giorni della settimana italiani e inglesi.
    # Esempio: "06:00 domenica 15 novembre 2026"
    # diventa: "06:00 15 november 2026".
    weekdays = ITALIAN_WEEKDAYS + ENGLISH_WEEKDAYS

    for weekday in sorted(weekdays, key=len, reverse=True):
        text = re.sub(
            rf"\b{re.escape(weekday)}\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )

    text = re.sub(r"\s+", " ", text).strip()

    # Traduce i nomi dei mesi italiani in inglese.
    for italian, english in sorted(
        ITALIAN_MONTHS.items(),
        key=lambda item: -len(item[0]),
    ):
        text = re.sub(
            rf"\b{re.escape(italian)}\b",
            english,
            text,
            flags=re.IGNORECASE,
        )

    return re.sub(r"\s+", " ", text).strip()


def parse_alert_datetime(value):
    """
    Converte le date più comuni estratte dai bollettini.

    Le date senza fuso orario sono considerate orari locali italiani.
    Se il formato non è riconosciuto restituisce None.
    """
    if not value or not isinstance(value, str):
        return None

    text = _normalize_datetime_text(value)

    # Prima prova il formato ISO 8601.
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ROME_TZ)

        return parsed

    except ValueError:
        pass

    # Poi prova i formati utilizzati nei bollettini.
    formats = (
        "%H:%M %d/%m/%Y",
        "%d/%m/%Y %H:%M",
        "%H:%M %d %B %Y",
        "%d %B %Y %H:%M",
        "%H:%M %d %b %Y",
        "%d %b %Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%H:%M %d-%m-%Y",
    )

    for date_format in formats:
        try:
            parsed = datetime.strptime(text, date_format)
            return parsed.replace(tzinfo=ROME_TZ)

        except ValueError:
            continue

    return None


def _as_utc(value):
    """Converte una data in UTC per confronti coerenti."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=ROME_TZ)

    return value.astimezone(timezone.utc)


def determine_validity(valid_from, valid_until, now=None):
    """
    Restituisce:
    - upcoming: l'allerta non è ancora iniziata;
    - active: l'allerta è attualmente valida;
    - expired: l'allerta è terminata;
    - unknown: le date non sono interpretabili o coerenti.
    """
    start = parse_alert_datetime(valid_from)
    end = parse_alert_datetime(valid_until)

    if start is None or end is None:
        return "unknown"

    start_utc = _as_utc(start)
    end_utc = _as_utc(end)

    if end_utc < start_utc:
        return "unknown"

    if now is None:
        now = datetime.now(timezone.utc)

    current = _as_utc(now)

    if current < start_utc:
        return "upcoming"

    if current > end_utc:
        return "expired"

    return "active"


def _decode_json_list(value):
    if isinstance(value, list):
        return value

    if not value:
        return []

    try:
        decoded = json.loads(value)
        return decoded if isinstance(decoded, list) else []

    except (TypeError, json.JSONDecodeError):
        return []


def get_official_alerts():
    """Legge dal database gli avvisi e le relative zone."""
    init_db()
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                a.id AS alert_id,
                a.alert_number,
                a.source_name,
                a.source_url,
                a.valid_from,
                a.valid_until,
                a.raw_json,
                a.created_at,
                a.updated_at,
                z.zone_number,
                z.territory,
                z.alert_level,
                z.risks
            FROM official_alerts AS a
            LEFT JOIN official_alert_zones AS z
                ON z.alert_id = a.id
            ORDER BY a.valid_from DESC, a.id DESC, z.zone_number ASC
            """
        ).fetchall()

        alerts_by_id = {}

        for row in rows:
            alert_id = row["alert_id"]

            if alert_id not in alerts_by_id:
                try:
                    raw_data = (
                        json.loads(row["raw_json"])
                        if row["raw_json"]
                        else {}
                    )

                except (TypeError, json.JSONDecodeError):
                    raw_data = {}

                alerts_by_id[alert_id] = {
                    "id": alert_id,
                    "alert_number": row["alert_number"],
                    "source_name": row["source_name"],
                    "source_url": row["source_url"],
                    "valid_from": row["valid_from"],
                    "valid_until": row["valid_until"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "raw_data": (
                        raw_data if isinstance(raw_data, dict) else {}
                    ),
                    "zones": [],
                }

            if row["zone_number"] is not None:
                alerts_by_id[alert_id]["zones"].append({
                    "zone": row["zone_number"],
                    "territory": row["territory"],
                    "alert_level": row["alert_level"],
                    "risks": _decode_json_list(row["risks"]),
                })

        return list(alerts_by_id.values())

    finally:
        connection.close()


def analyze_one_alert(alert, now=None):
    """Normalizza una singola allerta e ne valuta la validità temporale."""
    if not isinstance(alert, dict):
        return None

    zones = alert.get("zones", [])

    if not isinstance(zones, list):
        zones = []

    normalized_zones = []

    for zone in zones:
        if not isinstance(zone, dict):
            continue

        level = zone.get("alert_level")

        if isinstance(level, str):
            level = level.strip().lower()
        else:
            level = None

        risks = zone.get("risks", [])

        if not isinstance(risks, list):
            risks = []

        normalized_zones.append({
            "zone": zone.get("zone", zone.get("zone_number")),
            "territory": zone.get("territory"),
            "alert_level": level,
            "risks": [
                risk.strip().lower()
                for risk in risks
                if isinstance(risk, str) and risk.strip()
            ],
        })

    valid_from = alert.get("valid_from")
    valid_until = alert.get("valid_until")

    return {
        "id": alert.get("id"),
        "alert_number": alert.get("alert_number"),
        "source_name": alert.get("source_name"),
        "source_url": alert.get("source_url"),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "validity_status": determine_validity(
            valid_from,
            valid_until,
            now,
        ),
        "zones": normalized_zones,
        "raw_data": alert.get("raw_data", {}),
        "data_origin": "official_source",
    }


def analyze_official_alerts(alerts=None, now=None):
    """Carica e analizza le allerte, oppure usa quelle passate dal chiamante."""
    source_alerts = get_official_alerts() if alerts is None else alerts

    if not isinstance(source_alerts, list):
        source_alerts = []

    analyzed = []

    for alert in source_alerts:
        result = analyze_one_alert(alert, now=now)

        if result is not None:
            analyzed.append(result)

    missing_information = []
    required_checks = []

    if not analyzed:
        missing_information.append(
            "Non sono disponibili allerte ufficiali nel database o nell'input."
        )

        required_checks.append(
            "Verificare l'acquisizione e l'aggiornamento delle fonti ufficiali."
        )

    for alert in analyzed:
        alert_number = alert.get("alert_number") or "senza numero"

        if not alert.get("alert_number"):
            missing_information.append(
                "Una delle allerte non contiene il numero identificativo."
            )

        if alert["validity_status"] == "unknown":
            missing_information.append(
                f"La validità temporale dell'avviso {alert_number} "
                "non è determinabile."
            )

            required_checks.append(
                f"Verificare le date di validità dell'avviso {alert_number}."
            )

        if not alert["zones"]:
            missing_information.append(
                f"L'avviso {alert_number} non contiene zone strutturate."
            )

            required_checks.append(
                f"Verificare l'estrazione delle zone dell'avviso {alert_number}."
            )

    return {
        "agent": "official_alert_agent",
        "analysis_status": "partial" if missing_information else "completed",
        "alerts": analyzed,
        "missing_information": list(dict.fromkeys(missing_information)),
        "required_checks": list(dict.fromkeys(required_checks)),
        "limitations": [
            "La classificazione temporale dipende dalla correttezza delle date estratte.",
            "Le date senza fuso orario sono interpretate come orari locali italiani.",
            "Un avviso senza date interpretabili viene classificato come unknown.",
        ],
    }
