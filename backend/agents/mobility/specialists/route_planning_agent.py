
from datetime import datetime, timezone
import math


VALID_ROUTE_STATUSES = {
    "available",
    "disrupted",
    "unavailable",
    "unknown"
}


def is_update_outdated(updated_at, max_age_minutes, now):
    """
    Verifica se le informazioni sul percorso sono obsolete.

    Richiede una data ISO 8601 con fuso orario.
    """

    if not isinstance(updated_at, str) or not updated_at.strip():
        return True

    try:
        update_time = datetime.fromisoformat(
            updated_at.replace("Z", "+00:00")
        )

        if update_time.tzinfo is None:
            return True

        age = (now - update_time).total_seconds() / 60

        # Una data futura non è considerata valida.
        if age < 0:
            return True

        return age > max_age_minutes

    except (ValueError, TypeError, AttributeError):
        return True


def analyze(context=None):
    """
    Valuta i percorsi ricevuti e individua quelli raccomandabili.

    Non calcola autonomamente itinerari.
    Non inventa tempi, distanze o fermate.
    Non raccomanda percorsi senza fonte e timestamp validi.
    """

    context = context or {}

    if not isinstance(context, dict):
        context = {}

    origin = context.get("origin")
    destination = context.get("destination")

    route_options = context.get("route_options", [])

    max_age_minutes = context.get(
        "max_route_age_minutes",
        30
    )

    missing_information = []
    required_checks = []
    observations = []

    valid_routes = []

    now = datetime.now(timezone.utc)

    # 1. Controllo origine e destinazione.

    if isinstance(origin, str) and origin.strip():
        origin = origin.strip()
    else:
        origin = None
        missing_information.append(
            "Punto di partenza non specificato."
        )

    if isinstance(destination, str) and destination.strip():
        destination = destination.strip()
    else:
        destination = None
        missing_information.append(
            "Destinazione non specificata."
        )

    # 2. Controllo dell'intervallo temporale.

    if (
        not isinstance(max_age_minutes, (int, float))
        or isinstance(max_age_minutes, bool)
        or not math.isfinite(max_age_minutes)
        or max_age_minutes <= 0
    ):
        max_age_minutes = 30

        missing_information.append(
            "Intervallo di validità dei percorsi non valido: "
            "utilizzato il valore predefinito di 30 minuti."
        )

    # 3. Controllo della struttura dei percorsi.

    if not isinstance(route_options, list):
        route_options = []

        missing_information.append(
            "Il formato dei percorsi ricevuti non è valido."
        )

    if not route_options:
        missing_information.append(
            "Non sono disponibili percorsi da valutare."
        )

        required_checks.append(
            "Richiedere percorsi a un servizio di "
            "pianificazione affidabile."
        )

    # 4. Analisi dei singoli percorsi.

    for index, route in enumerate(route_options):

        route_number = index + 1

        if not isinstance(route, dict):
            missing_information.append(
                f"Il percorso numero {route_number} "
                "ha un formato non valido."
            )
            continue

        source = route.get("source")
        updated_at = route.get("updated_at")
        status = route.get("status", "unknown")

        # La fonte deve essere una stringa non vuota.
        valid_source = (
            isinstance(source, str)
            and bool(source.strip())
        )

        if not isinstance(status, str):
            status = "unknown"
        else:
            status = status.strip().lower()

            if status not in VALID_ROUTE_STATUSES:
                status = "unknown"

        outdated = is_update_outdated(
            updated_at,
            max_age_minutes,
            now
        )

        evaluated_route = {
            **route,
            "status": status,
            "data_outdated": outdated,
            "is_recommendable": False
        }

        if not valid_source:
            missing_information.append(
                f"Il percorso numero {route_number} "
                "non indica una fonte valida."
            )

        if outdated:
            missing_information.append(
                f"Il percorso numero {route_number} "
                "è privo di un aggiornamento valido "
                "o è obsoleto."
            )

        if status == "unknown":
            missing_information.append(
                f"Lo stato del percorso numero {route_number} "
                "non è conosciuto."
            )

        if status == "disrupted":
            required_checks.append(
                f"Verificare le criticità del percorso "
                f"numero {route_number} prima di raccomandarlo."
            )

        if status == "unavailable":
            required_checks.append(
                f"Il percorso numero {route_number} "
                "risulta non disponibile."
            )

        if status == "unknown":
            required_checks.append(
                f"Verificare la disponibilità del percorso "
                f"numero {route_number}."
            )

        # 5. Valutazione della raccomandabilità.

        if (
            status == "available"
            and valid_source
            and not outdated
            and origin
            and destination
        ):
            evaluated_route["is_recommendable"] = True

            valid_routes.append(evaluated_route)

    # 6. Selezione del percorso.

    # Per ora viene mantenuto l'ordine ricevuto dal servizio
    # di routing. Non viene inventato un criterio di ottimizzazione.

    recommended_route = (
        valid_routes[0] if valid_routes else None
    )

    alternative_routes = (
        valid_routes[1:] if len(valid_routes) > 1 else []
    )

    if recommended_route:
        observations.append(
            "È stato individuato un percorso disponibile "
            "con fonte e aggiornamento validi."
        )

    if alternative_routes:
        observations.append(
            "Sono disponibili anche percorsi alternativi."
        )

    if not recommended_route:
        required_checks.append(
            "Verificare origine, destinazione e disponibilità "
            "di percorsi aggiornati."
        )

    # 7. Rimozione delle informazioni duplicate.

    missing_information = list(
        dict.fromkeys(missing_information)
    )

    required_checks = list(
        dict.fromkeys(required_checks)
    )

    # 8. Stato complessivo dell'analisi.

    if recommended_route is None:
        analysis_status = "insufficient_data"

    elif missing_information or required_checks:
        analysis_status = "partial"

    else:
        analysis_status = "completed"

    return {
        "agent": "route_planning_agent",
        "analysis_status": analysis_status,
        "origin": origin,
        "destination": destination,
        "recommended_route": recommended_route,
        "alternative_routes": alternative_routes,
        "missing_information": missing_information,
        "required_checks": required_checks,
        "limitations": [
            "L'agente valuta esclusivamente i percorsi ricevuti.",
            "Non calcola autonomamente distanze o tempi "
            "di percorrenza.",
            "La presenza di una fonte non garantisce "
            "che il percorso sia privo di criticità.",
            "Le informazioni possono diventare obsolete.",
            "La scelta del percorso segue per ora "
            "l'ordine restituito dalla fonte."
        ]
    }
