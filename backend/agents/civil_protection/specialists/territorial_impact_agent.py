"""Estrazione delle aree territoriali citate nelle allerte."""

NAPLES_TERMS = (
    "napoli", "naples", "area vesuviana", "isole", "piana campana",
    "campi flegrei", "vesuvio"
)


def analyze_territorial_impact(official_alert_analysis):
    if not isinstance(official_alert_analysis, dict):
        official_alert_analysis = {}

    alerts = official_alert_analysis.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []

    affected_areas = []
    missing_information = []
    required_checks = []

    for alert in alerts:
        if not isinstance(alert, dict):
            continue

        for zone in alert.get("zones", []):
            if not isinstance(zone, dict):
                continue

            territory = zone.get("territory")
            territory_text = territory.strip() if isinstance(territory, str) else ""

            if not territory_text:
                missing_information.append(
                    f"Descrizione territoriale mancante per la zona {zone.get('zone')} dell'avviso {alert.get('alert_number') or 'senza numero'}."
                )
                required_checks.append(
                    f"Verificare la legenda territoriale della zona {zone.get('zone')}."
                )
                continue

            normalized = territory_text.casefold()
            naples_relevance = any(term in normalized for term in NAPLES_TERMS)

            affected_areas.append({
                "alert_number": alert.get("alert_number"),
                "validity_status": alert.get("validity_status", "unknown"),
                "zone": zone.get("zone"),
                "territory": territory_text,
                "alert_level": zone.get("alert_level"),
                "risk_types": zone.get("risks", []),
                "naples_area_mentioned": naples_relevance,
                "geographic_precision": "official_textual_zone",
            })

    unique = []
    seen = set()
    for area in affected_areas:
        key = (
            area.get("alert_number"),
            area.get("zone"),
            area.get("territory"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(area)

    return {
        "agent": "territorial_impact_agent",
        "analysis_status": "partial" if missing_information else (
            "completed" if unique else "insufficient_data"
        ),
        "affected_areas": unique,
        "naples_related_areas": [
            area for area in unique if area["naples_area_mentioned"]
        ],
        "missing_information": list(dict.fromkeys(missing_information)),
        "required_checks": list(dict.fromkeys(required_checks)),
        "limitations": [
            "Le aree sono riportate testualmente come descritte nella fonte ufficiale.",
            "La corrispondenza con Napoli è una ricerca testuale indicativa, non una verifica GIS.",
            "Non vengono dedotti indirizzi, coordinate, confini o singoli quartieri."
        ],
    }
