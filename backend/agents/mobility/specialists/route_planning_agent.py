
def analyze(context=None):
    """
    Analizza le alternative di percorso disponibili.
    """

    context = context or {}

    origin = context.get("origin")
    destination = context.get("destination")

    route_options = context.get("route_options", [])

    missing_information = []

    if not origin:
        missing_information.append(
            "Punto di partenza non specificato."
        )

    if not destination:
        missing_information.append(
            "Destinazione non specificata."
        )

    if not route_options:
        missing_information.append(
            "Non sono disponibili percorsi verificati."
        )

    return {
        "agent": "route_planning_agent",
        "analysis_status": (
            "completed" if route_options else "insufficient_data"
        ),
        "origin": origin,
        "destination": destination,
        "recommended_route": (
            route_options[0] if route_options else None
        ),
        "alternative_routes": route_options[1:],
        "missing_information": missing_information
    }
