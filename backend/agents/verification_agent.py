
from datetime import datetime, timezone
import json
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import re

from services.database import get_connection


# Tipologie di evidenza riconosciute dall'agente
EVIDENCE_TYPES = {
    "official_confirmation",
    "independent_confirmation",
    "official_contradiction",
    "independent_contradiction",
    "context"
}


ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12
}


NAPLES_LOCATIONS = {
    "napoli", "bagnoli", "fuorigrotta", "chiaia",
    "vomero", "posillipo", "scampia", "pianura",
    "secondigliano", "forcella", "sanita",
    "spaccanapoli", "capodichino"
}


def get_source_key(evidence):
    """
    Identifica una fonte per evitare di contare
    più articoli dello stesso dominio come fonti diverse.
    """

    source_url = evidence["source_url"]

    if source_url:
        domain = urlparse(source_url).hostname

        if domain:
            return domain.lower().removeprefix("www.")

    return evidence["source_name"].strip().casefold()


def evaluate_incident(incident_id):
    """
    Valuta le evidenze associate a un incidente
    e aggiorna il suo stato di verifica.

    Gli stati possibili sono:
    - unverified
    - partially_confirmed
    - confirmed
    - contested
    - contradicted
    - conflicting
    """

    connection = get_connection()

    try:
        incident = connection.execute(
            """
            SELECT id
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,)
        ).fetchone()

        if incident is None:
            raise ValueError(
                f"Incidente {incident_id} non trovato."
            )

        evidences = connection.execute(
            """
            SELECT *
            FROM incident_evidence
            WHERE incident_id = ?
            """,
            (incident_id,)
        ).fetchall()

        official_confirmations = [
            e for e in evidences
            if e["evidence_type"] == "official_confirmation"
        ]

        independent_confirmations = [
            e for e in evidences
            if e["evidence_type"] == "independent_confirmation"
        ]

        official_contradictions = [
            e for e in evidences
            if e["evidence_type"] == "official_contradiction"
        ]

        independent_contradictions = [
            e for e in evidences
            if e["evidence_type"] == "independent_contradiction"
        ]

        # Contiamo i domini distinti delle conferme indipendenti.
        independent_sources = {
            get_source_key(e)
            for e in independent_confirmations
        }

        has_confirmation = (
            bool(official_confirmations)
            or bool(independent_sources)
        )

        has_contradiction = (
            bool(official_contradictions)
            or bool(independent_contradictions)
        )

        # Prima controlliamo se esistono evidenze di segno opposto.
        if has_confirmation and has_contradiction:
            status = "conflicting"

        # Una contraddizione ufficiale senza conferme.
        elif official_contradictions:
            status = "contradicted"

        # Una contestazione indipendente senza conferme.
        elif independent_contradictions:
            status = "contested"

        # Una conferma ufficiale.
        elif official_confirmations:
            status = "confirmed"

        # Almeno due domini indipendenti confermano l'evento.
        elif len(independent_sources) >= 2:
            status = "confirmed"

        # Un solo dominio indipendente conferma l'evento.
        elif len(independent_sources) == 1:
            status = "partially_confirmed"

        # Non ci sono evidenze sufficienti.
        else:
            status = "unverified"

        now = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            UPDATE incidents
            SET verification_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, now, incident_id)
        )

        connection.commit()

        return {
            "incident_id": incident_id,
            "verification_status": status,
            "total_evidence": len(evidences),
            "official_confirmations": len(official_confirmations),
            "independent_sources": len(independent_sources),
            "contradictions": (
                len(official_contradictions)
                + len(independent_contradictions)
            )
        }

    finally:
        connection.close()


def add_evidence(
    incident_id,
    source_name,
    source_url,
    description,
    evidence_type
):
    """
    Registra una nuova evidenza nel database
    e rivaluta automaticamente l'incidente.
    """

    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(
            f"Tipo di evidenza non valido: {evidence_type}"
        )

    if not source_name or not source_name.strip():
        raise ValueError("Il nome della fonte è obbligatorio.")

    if not description or not description.strip():
        raise ValueError("La descrizione è obbligatoria.")

    connection = get_connection()

    try:
        incident = connection.execute(
            """
            SELECT id
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,)
        ).fetchone()

        if incident is None:
            raise ValueError(
                f"Incidente {incident_id} non trovato."
            )

        existing = connection.execute(
            """
            SELECT id
            FROM incident_evidence
            WHERE incident_id = ?
            AND source_name = ?
            AND evidence_type = ?
            AND COALESCE(source_url, '') = COALESCE(?, '')
            AND evidence_description = ?
            """,
            (
                incident_id,
                source_name,
                evidence_type,
                source_url,
                description
            )
        ).fetchone()

        if existing:
            return evaluate_incident(incident_id)

        now = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            INSERT INTO incident_evidence (
                incident_id,
                agent_name,
                source_name,
                source_url,
                evidence_description,
                evidence_type,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                "verification_agent",
                source_name,
                source_url,
                description,
                evidence_type,
                now
            )
        )

        connection.commit()

    finally:
        connection.close()

    return evaluate_incident(incident_id)


def alert_risk_matches_incident(description, risks):
    """
    Verifica se il fenomeno descritto nell'incidente
    è compatibile con i rischi indicati nell'allerta.
    """

    text = (description or "").casefold()

    risk_keywords = {
        "idrogeologico": [
            "allagament",
            "piogg",
            "temporale",
            "fran",
            "smottament",
            "dissesto",
            "fango",
            "caduta massi"
        ],

        "idraulico": [
            "allagament",
            "esond",
            "fiume",
            "torrente",
            "piena",
            "strada invasa dall'acqua",
            "sottopasso allagato"
        ]
    }

    for risk in risks:
        risk = risk.casefold()

        for risk_type, keywords in risk_keywords.items():
            if risk_type in risk:
                if any(keyword in text for keyword in keywords):
                    return True

    return False


def parse_italian_date(value):
    """Converte una data dell'avviso in datetime."""

    if not value:
        return None

    match = re.search(
        r"(\d{2}:\d{2})\s+\w+\s+(\d{1,2})\s+"
        r"([a-zà]+)\s+(\d{4})",
        value.lower()
    )

    if not match:
        return None

    time_value, day, month_name, year = match.groups()
    month = ITALIAN_MONTHS.get(month_name)

    if month is None:
        return None

    hour, minute = map(int, time_value.split(":"))

    return datetime(
        int(year),
        month,
        int(day),
        hour,
        minute,
        tzinfo=ZoneInfo("Europe/Rome")
    )


def location_matches_territory(location, territory):
    """Controlla se la località dell'incidente rientra nel territorio."""

    if not location or not territory:
        return False

    location = location.casefold().strip()
    territory = territory.casefold().strip()

    if location in territory or territory in location:
        return True

    if "napoli" in territory:
        if location in NAPLES_LOCATIONS:
            return True

        if any(
            place in location
            for place in NAPLES_LOCATIONS
        ):
            return True

    return False


def attach_official_alert_context(incident_id):
    """
    Cerca allerte ufficiali territorialmente e temporalmente
    compatibili con un incidente e le registra come contesto.

    Un'allerta contestuale NON conferma automaticamente l'incidente.
    """

    connection = get_connection()

    try:
        incident = connection.execute(
            """
            SELECT id, location, created_at, event_type, description
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,)
        ).fetchone()

        if incident is None:
            raise ValueError(
                f"Incidente {incident_id} non trovato."
            )

        incident_location = incident["location"]

        incident_date = datetime.fromisoformat(
            incident["created_at"].replace("Z", "+00:00")
        )

        if incident_date.tzinfo is None:
            incident_date = incident_date.replace(
                tzinfo=timezone.utc
            )

        alerts = connection.execute(
            """
            SELECT
                a.alert_number,
                a.source_name,
                a.source_url,
                a.valid_from,
                a.valid_until,
                z.zone_number,
                z.territory,
                z.alert_level,
                z.risks
            FROM official_alerts a
            JOIN official_alert_zones z
                ON a.id = z.alert_id
            """
        ).fetchall()

    finally:
        connection.close()

    matched_alerts = []

    for alert in alerts:

        if not location_matches_territory(
            incident_location,
            alert["territory"]
        ):
            continue

        valid_from = parse_italian_date(alert["valid_from"])
        valid_until = parse_italian_date(alert["valid_until"])

        if valid_from is None or valid_until is None:
            continue

        incident_local_date = incident_date.astimezone(
            ZoneInfo("Europe/Rome")
        )

        if not valid_from <= incident_local_date <= valid_until:
            continue

        risks = json.loads(alert["risks"] or "[]")

        # Verifichiamo la compatibilità tra rischio e incidente.
        if not alert_risk_matches_incident(
            incident["description"],
            risks
        ):
            continue

        description = (
            f"Allerta ufficiale {alert['alert_number']}: "
            f"livello {alert['alert_level']} per il territorio "
            f"{alert['territory']}. "
            f"Rischi segnalati: {', '.join(risks)}. "
            f"Periodo: {alert['valid_from']} - "
            f"{alert['valid_until']}. "
            f"Questa informazione costituisce contesto "
            f"territoriale e temporale, non conferma "
            f"l'avvenimento dell'incidente."
        )

        result = add_evidence(
            incident_id=incident_id,
            source_name=alert["source_name"],
            source_url=alert["source_url"],
            description=description,
            evidence_type="context"
        )

        matched_alerts.append({
            "alert_number": alert["alert_number"],
            "zone": alert["zone_number"],
            "territory": alert["territory"],
            "alert_level": alert["alert_level"],
            "verification": result
        })

    return {
        "incident_id": incident_id,
        "matched_alerts": matched_alerts,
        "total_matches": len(matched_alerts)
    }
