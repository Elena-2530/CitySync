"""Analisi delle tipologie e dei livelli di rischio dichiarati nelle allerte."""

VALID_LEVELS = {"verde", "gialla", "arancione", "rossa"}

LEVEL_ORDER = {
    "verde": 1,
    "gialla": 2,
    "arancione": 3,
    "rossa": 4,
}

LEVEL_LABELS = {
    "verde": "verde",
    "gialla": "gialla",
    "arancione": "arancione",
    "rossa": "rossa",
}


def analyze_risks(official_alert_analysis):
    if not isinstance(official_alert_analysis, dict):
        official_alert_analysis = {}

    alerts = official_alert_analysis.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []

    risk_records = []
    missing_information = []
    required_checks = []

    for alert in alerts:
        if not isinstance(alert, dict):
            continue

        alert_number = alert.get("alert_number")
        validity = alert.get("validity_status", "unknown")

        for zone in alert.get("zones", []):
            if not isinstance(zone, dict):
                continue

            level = zone.get("alert_level")
            if level not in VALID_LEVELS:
                missing_information.append(
                    f"Livello di allerta mancante o non riconosciuto nella zona {zone.get('zone')} dell'avviso {alert_number or 'senza numero'}."
                )
                required_checks.append(
                    f"Verificare il livello di allerta della zona {zone.get('zone')}."
                )

            risks = zone.get("risks", [])
            if not isinstance(risks, list):
                risks = []

            if not risks:
                missing_information.append(
                    f"Tipologia di rischio non specificata per la zona {zone.get('zone')} dell'avviso {alert_number or 'senza numero'}."
                )

            for risk in risks:
                if not isinstance(risk, str) or not risk.strip():
                    continue

                risk_records.append({
                    "alert_number": alert_number,
                    "validity_status": validity,
                    "zone": zone.get("zone"),
                    "territory": zone.get("territory"),
                    "alert_level": level,
                    "risk_type": risk.strip().lower(),
                    "is_current_alert": validity == "active",
                })

    highest_level = None
    recognized_levels = [
        item["alert_level"]
        for item in risk_records
        if item.get("alert_level") in VALID_LEVELS
    ]
    if recognized_levels:
        highest_level = max(recognized_levels, key=lambda item: LEVEL_ORDER[item])

    return {
        "agent": "risk_analysis_agent",
        "analysis_status": "partial" if missing_information else (
            "completed" if risk_records else "insufficient_data"
        ),
        "risk_records": risk_records,
        "risk_types": sorted(set(item["risk_type"] for item in risk_records)),
        "highest_reported_alert_level": highest_level,
        "missing_information": list(dict.fromkeys(missing_information)),
        "required_checks": list(dict.fromkeys(required_checks)),
        "limitations": [
            "Il livello più alto è quello riportato nelle allerte ricevute, non una valutazione autonoma del pericolo.",
            "La presenza di un rischio in un'allerta non dimostra che il fenomeno si sia verificato.",
            "I livelli di allerta non vengono convertiti in probabilità o punteggi numerici."
        ],
    }
