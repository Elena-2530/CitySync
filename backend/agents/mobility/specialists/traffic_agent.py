
from datetime import datetime, timezone


VALID_CONDITIONS = {
    "normal",
    "slow",
    "congested",
    "blocked",
    "closed",
    "incident",
    "flooded",
    "unknown"
}


CONDITION_DESCRIPTIONS = {
    "normal": "Traffico regolare secondo i dati ricevuti.",
    "slow": "Sono segnalati rallentamenti.",
    "congested": "È segnalato traffico intenso.",
    "blocked": "È segnalato un blocco della circolazione.",
    "closed": "È segnalata una chiusura stradale.",
    "incident": "È segnalato un incidente.",
    "flooded": "È segnalato un possibile allagamento.",
    "unknown": "Condizione della strada non conosciuta."
}


def is_update_outdated(updated_at, max_age_minutes, now):
    """
    Verifica se i dati sulla viabilità sono obsoleti.

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
    Analizza esclusivamente le informazioni sulla viabilità.

    Non consulta autonomamente fonti esterne.
    Non verifica le segnalazioni social.
    Non presume che una strada sia chiusa o congestionata
    senza dati che lo dimostrino.
    """

    context = context or {}

    traffic_data = context.get("traffic_data") or {}

    conditions = traffic_data.get("conditions", [])
    affected_roads = traffic_data.get("affected_roads", [])

    max_age_minutes = traffic_data.get(
        "max_age_minutes",
        15
    )

    now = datetime.now(timezone.utc)

    observations = []
    analyzed_conditions = []
    analyzed_roads = []
    missing_information = []
    required_checks = []

    if not traffic_data:
        missing_information.append(
            "Non sono disponibili dati aggiornati sulla viabilità."
        )

        required_checks.append(
            "Consultare una fonte aggiornata sulla viabilità."
        )

    if not conditions:
        missing_information.append(
            "Non sono disponibili condizioni di traffico."
        )

    if not affected_roads:
        missing_information.append(
            "Non sono state individuate strade interessate con precisione."
        )

    # Analisi delle condizioni di traffico.
    for condition in conditions:

        if not isinstance(condition, dict):
            missing_information.append(
                "È stato ricevuto un dato di traffico non valido."
            )
            continue

        road = condition.get(
            "road",
            "Strada non identificata"
        )

        status = condition.get(
            "status",
            "unknown"
        )

        if status not in VALID_CONDITIONS:
            status = "unknown"

        updated_at = condition.get("updated_at")
        source = condition.get("source")

        outdated = is_update_outdated(
            updated_at,
            max_age_minutes,
            now
        )

        item = {
            "road": road,
            "status": status,
            "description": CONDITION_DESCRIPTIONS[status],
            "source": source,
            "updated_at": updated_at,
            "data_outdated": outdated
        }

        analyzed_conditions.append(item)

        if status == "unknown":
            missing_information.append(
                f"Condizione non verificata per {road}."
            )

        if outdated:
            missing_information.append(
                f"I dati relativi a {road} sono assenti o obsoleti."
            )

        if not source:
            missing_information.append(
                f"Fonte non specificata per {road}."
            )

        if status in {
            "blocked",
            "closed",
            "incident",
            "flooded"
        }:
            required_checks.append(
                f"Verificare la condizione segnalata per {road}."
            )

    # Analisi delle strade interessate.
    for road in affected_roads:

        if isinstance(road, str):
            analyzed_roads.append({
                "name": road,
                "status": "not_assessed"
            })

        elif isinstance(road, dict):
            analyzed_roads.append({
                "name": road.get(
                    "name",
                    "Strada non identificata"
                ),
                "status": "not_assessed"
            })

        else:
            missing_information.append(
                "È stata ricevuta un'indicazione stradale non valida."
            )

    if analyzed_conditions:
        observations.append(
            "Sono disponibili informazioni sulle condizioni "
            "della viabilità."
        )

    if analyzed_roads:
        observations.append(
            "Sono state individuate alcune strade potenzialmente "
            "interessate."
        )

    missing_information = list(
        dict.fromkeys(missing_information)
    )

    required_checks = list(
        dict.fromkeys(required_checks)
    )

    if not analyzed_conditions:
        analysis_status = "insufficient_data"
    elif missing_information:
        analysis_status = "partial"
    else:
        analysis_status = "completed"

    return {
        "agent": "traffic_agent",
        "analysis_status": analysis_status,
        "observations": observations,
        "traffic_conditions": analyzed_conditions,
        "affected_roads": analyzed_roads,
        "missing_information": missing_information,
        "required_checks": required_checks,
        "limitations": [
            "L'analisi utilizza esclusivamente i dati ricevuti.",
            "Le condizioni segnalate non equivalgono "
            "a verifiche indipendenti.",
            "Le informazioni possono diventare obsolete."
        ]
    }
