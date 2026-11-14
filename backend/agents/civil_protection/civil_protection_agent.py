"""Coordinatore settoriale Civil Protection Agent."""

from datetime import datetime, timezone

from agents.civil_protection.specialists.official_alert_agent import (
    analyze_official_alerts,
)
from agents.civil_protection.specialists.risk_analysis_agent import (
    analyze_risks,
)
from agents.civil_protection.specialists.territorial_impact_agent import (
    analyze_territorial_impact,
)
from agents.civil_protection.specialists.safety_assessment_agent import (
    assess_safety,
)


def analyze_civil_protection_request(alerts=None, now=None):
    """
    Coordina l'analisi delle allerte di protezione civile.

    Args:
        alerts: elenco opzionale di allerte già strutturate. Se None,
                le allerte vengono recuperate dal database.
        now: datetime opzionale, utile soprattutto nei test.

    Returns:
        Dizionario strutturato da consegnare a Janara.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    official_analysis = analyze_official_alerts(alerts=alerts, now=now)
    risk_analysis = analyze_risks(official_analysis)
    territorial_analysis = analyze_territorial_impact(official_analysis)
    safety_analysis = assess_safety(
        official_analysis=official_analysis,
        risk_analysis=risk_analysis,
        territorial_analysis=territorial_analysis,
    )

    all_alerts = official_analysis.get("alerts", [])
    active_alerts = [
        item for item in all_alerts
        if item.get("validity_status") == "active"
    ]
    upcoming_alerts = [
        item for item in all_alerts
        if item.get("validity_status") == "upcoming"
    ]
    expired_alerts = [
        item for item in all_alerts
        if item.get("validity_status") == "expired"
    ]

    missing_information = []
    required_checks = []

    for section in (
        official_analysis,
        risk_analysis,
        territorial_analysis,
        safety_analysis,
    ):
        missing_information.extend(section.get("missing_information", []))
        required_checks.extend(section.get("required_checks", []))

    missing_information = list(dict.fromkeys(missing_information))
    required_checks = list(dict.fromkeys(required_checks))

    if not all_alerts:
        analysis_status = "insufficient_data"
    elif missing_information:
        analysis_status = "partial"
    else:
        analysis_status = "completed"

    return {
        "agent": "civil_protection_agent",
        "analysis_type": "civil_protection_assessment",
        "analysis_status": analysis_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_alerts": len(all_alerts),
            "active_alerts": len(active_alerts),
            "upcoming_alerts": len(upcoming_alerts),
            "expired_alerts": len(expired_alerts),
            "unknown_validity_alerts": sum(
                item.get("validity_status") == "unknown"
                for item in all_alerts
            ),
        },
        "official_alert_analysis": official_analysis,
        "risk_analysis": risk_analysis,
        "territorial_impact_analysis": territorial_analysis,
        "safety_assessment": safety_analysis,
        "missing_information": missing_information,
        "required_checks": required_checks,
        "limitations": [
            "L'analisi utilizza esclusivamente le allerte e i dati ricevuti.",
            "Un'allerta indica un rischio previsto e non prova che un evento si sia verificato.",
            "I territori sono riportati come descritti dalla fonte ufficiale; non sono ricavati confini geografici precisi.",
            "Il livello di allerta non viene trasformato in una probabilità numerica.",
            "L'agente non invia soccorsi, non dispone evacuazioni e non assume decisioni operative.",
            "Le decisioni operative competono alle autorità e agli operatori umani."
        ],
    }


if __name__ == "__main__":
    import json

    result = analyze_civil_protection_request()
    print(json.dumps(result, indent=4, ensure_ascii=False))
