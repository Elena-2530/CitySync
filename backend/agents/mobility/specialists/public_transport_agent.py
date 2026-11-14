
from datetime import datetime, timezone


VALID_STATUSES = {
    "active",
    "delayed",
    "suspended",
    "cancelled",
    "disrupted",
    "unknown"
}


STATUS_DESCRIPTIONS = {
    "active": "Servizio dichiarato attivo.",
    "delayed": "Servizio in ritardo.",
    "suspended": "Servizio sospeso.",
    "cancelled": "Corsa cancellata.",
    "disrupted": "Servizio con criticità.",
    "unknown": "Stato del servizio non verificato."
}


def is_update_outdated(updated_at, max_age_minutes, now):
    """
    Verifica se l'aggiornamento del servizio è troppo vecchio.

    Le date devono essere ISO 8601 con fuso orario.
    """

    if not updated_at:
        return True

    try:
        update_time = datetime.fromisoformat(
            updated_at.replace("Z", "+00:00")
        )

        if update_time.tzinfo is None:
            return True

        age = (now - update_time).total_seconds() / 60

        return age > max_age_minutes

    except (ValueError, TypeError, AttributeError):
        return True


def analyze(incident=None, reports=None, context=None):
    """
    Analizza esclusivamente informazioni sul trasporto pubblico.

    Non consulta autonomamente fonti esterne.
    Non verifica la veridicità delle segnalazioni.
    Utilizza esclusivamente i dati forniti dal chiamante.
    """

    context = context or {}

    transport_data = context.get("transport_data") or {}

    services = transport_data.get("services", [])

    max_age_minutes = transport_data.get(
        "max_age_minutes",
        15
    )

    now = datetime.now(timezone.utc)

    observations = []
    missing_information = []
    required_checks = []

    if not transport_data or not services:
        missing_information.append(
            "Non sono disponibili informazioni sui servizi "
            "di trasporto pubblico."
        )

        required_checks.append(
            "Consultare le fonti ufficiali degli operatori "
            "del trasporto pubblico."
        )

    for service in services:

        if not isinstance(service, dict):
            missing_information.append(
                "È stato ricevuto un dato di servizio non valido."
            )
            continue

        name = service.get(
            "name",
            "Servizio non identificato"
        )

        status = service.get(
            "status",
            "unknown"
        )

        if status not in VALID_STATUSES:
            status = "unknown"

        updated_at = service.get("updated_at")
        source = service.get("source")

        outdated = is_update_outdated(
            updated_at,
            max_age_minutes,
            now
        )

        observation = {
            "service": name,
            "operator": service.get("operator"),
            "status": status,
            "status_description": STATUS_DESCRIPTIONS[status],
            "source": source,
            "updated_at": updated_at,
            "data_outdated": outdated
        }

        observations.append(observation)

        if status == "unknown":
            missing_information.append(
                f"Stato non verificato per {name}."
            )

        if outdated:
            missing_information.append(
                f"Le informazioni relative a {name} "
                "sono assenti o non aggiornate."
            )

        if not source:
            missing_information.append(
                f"Fonte non specificata per {name}."
            )

        if status in {
            "delayed",
            "suspended",
            "cancelled",
            "disrupted"
        }:
            required_checks.append(
                f"Verificare presso l'operatore lo stato "
                f"del servizio {name}."
            )

    missing_information = list(
        dict.fromkeys(missing_information)
    )

    required_checks = list(
        dict.fromkeys(required_checks)
    )

    if not observations or missing_information:
        analysis_status = "insufficient_data"
    else:
        analysis_status = "completed"

    return {
        "agent": "public_transport_agent",
        "analysis_status": analysis_status,
        "services": observations,
        "missing_information": missing_information,
        "required_checks": required_checks,
        "limitations": [
            "L'analisi utilizza esclusivamente i dati ricevuti.",
            "Lo stato dichiarato da una fonte non equivale "
            "a una verifica indipendente.",
            "L'aggiornamento dei dati dipende dalla fonte."
        ]
    }
