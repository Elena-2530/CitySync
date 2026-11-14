
def analyze(incident=None, reports=None, context=None):
    """
    Analizza le informazioni disponibili sul trasporto pubblico.
    """

    context = context or {}

    transport_data = context.get("transport_data") or {}

    services = transport_data.get("services", [])

    observations = []
    missing_information = []
    required_checks = []

    if not transport_data:
        missing_information.append(
            "Non sono disponibili dati aggiornati sul trasporto pubblico."
        )

        required_checks.append(
            "Verificare lo stato delle linee presso i rispettivi operatori."
        )

    for service in services:
        name = service.get("name", "Servizio non identificato")
        status = service.get("status", "unknown")

        observations.append({
            "service": name,
            "status": status,
            "operator": service.get("operator"),
            "updated_at": service.get("updated_at"),
            "source": service.get("source")
        })

        if status == "unknown":
            missing_information.append(
                f"Stato non verificato per {name}."
            )

    return {
        "agent": "public_transport_agent",
        "analysis_status": (
            "completed" if transport_data else "insufficient_data"
        ),
        "services": observations,
        "missing_information": missing_information,
        "required_checks": required_checks
    }
