
def analyze(incident, reports=None, context=None):
    """
    Analizza le informazioni disponibili sulla viabilità.

    Non presume che una strada sia chiusa o congestionata
    senza dati che lo dimostrino.
    """

    reports = reports or []
    context = context or {}

    traffic_data = context.get("traffic_data") or {}

    description = (incident or {}).get("description") or ""

    road_conditions = traffic_data.get("conditions", [])
    affected_roads = traffic_data.get("affected_roads", [])

    observations = []
    missing_information = []
    required_checks = []

    if description:
        observations.append(
            "Descrizione dell'evento disponibile."
        )

    if not traffic_data:
        missing_information.append(
            "Non sono disponibili dati aggiornati sul traffico."
        )
        required_checks.append(
            "Consultare una fonte aggiornata sulla viabilità."
        )

    if not affected_roads:
        missing_information.append(
            "Non sono state individuate strade interessate con precisione."
        )

    if not road_conditions:
        missing_information.append(
            "Non sono disponibili condizioni di traffico verificate."
        )

    return {
        "agent": "traffic_agent",
        "analysis_status": (
            "completed" if incident else "insufficient_data"
        ),
        "observations": observations,
        "traffic_conditions": road_conditions,
        "affected_roads": affected_roads,
        "missing_information": missing_information,
        "required_checks": required_checks
    }
