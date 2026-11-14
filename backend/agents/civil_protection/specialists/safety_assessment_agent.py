
"""Sintesi prudenziale delle informazioni di sicurezza disponibili."""


def assess_safety(
    official_analysis,
    risk_analysis,
    territorial_analysis,
):
    official_analysis = (
        official_analysis if isinstance(official_analysis, dict) else {}
    )
    risk_analysis = (
        risk_analysis if isinstance(risk_analysis, dict) else {}
    )
    territorial_analysis = (
        territorial_analysis if isinstance(territorial_analysis, dict) else {}
    )

    alerts = official_analysis.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []

    active = [
        alert for alert in alerts
        if isinstance(alert, dict)
        and alert.get("validity_status") == "active"
    ]

    upcoming = [
        alert for alert in alerts
        if isinstance(alert, dict)
        and alert.get("validity_status") == "upcoming"
    ]

    expired = [
        alert for alert in alerts
        if isinstance(alert, dict)
        and alert.get("validity_status") == "expired"
    ]

    unknown = [
        alert for alert in alerts
        if isinstance(alert, dict)
        and alert.get("validity_status") == "unknown"
    ]

    risk_records = risk_analysis.get("risk_records", [])
    if not isinstance(risk_records, list):
        risk_records = []

    affected_areas = territorial_analysis.get("affected_areas", [])
    if not isinstance(affected_areas, list):
        affected_areas = []

    observations = []
    recommendations = []
    recommended_checks = []
    missing_information = []

    # Osservazioni sulle allerte.
    if active:
        observations.append(
            f"Sono presenti {len(active)} allerte ufficiali "
            "classificate come attive."
        )

    if upcoming:
        observations.append(
            f"Sono presenti {len(upcoming)} allerte ufficiali "
            "con validità futura."
        )

    if expired:
        observations.append(
            f"Sono presenti {len(expired)} allerte scadute, "
            "da non trattare come attive."
        )

    if unknown:
        observations.append(
            f"Sono presenti {len(unknown)} allerte la cui "
            "validità temporale non è determinabile."
        )

        missing_information.append(
            "La validità temporale di una o più allerte ufficiali "
            "non è determinabile."
        )

        recommended_checks.append(
            "Verificare le date di inizio e fine delle allerte "
            "nelle rispettive fonti ufficiali."
        )

    if not alerts:
        missing_information.append(
            "Non sono disponibili allerte ufficiali da valutare."
        )

        recommended_checks.append(
            "Verificare che le fonti ufficiali siano state acquisite "
            "e aggiornate."
        )

    # Analisi dei rischi.
    active_risks = [
        record for record in risk_records
        if isinstance(record, dict)
        and record.get("validity_status") == "active"
    ]

    if active and not active_risks:
        missing_information.append(
            "Le allerte attive non contengono tipologie di rischio strutturate."
        )

        recommended_checks.append(
            "Verificare il contenuto e l'estrazione delle tipologie di rischio."
        )

    # Verifica delle aree territoriali.
    if active and not affected_areas:
        missing_information.append(
            "Non sono disponibili aree territoriali strutturate "
            "per le allerte attive."
        )

        recommended_checks.append(
            "Verificare le zone e la legenda territoriale dei bollettini."
        )

    # Verifica della provenienza delle allerte attive.
    for alert in active:
        number = alert.get("alert_number") or "senza numero"

        if not alert.get("source_name"):
            missing_information.append(
                f"La fonte dell'avviso {number} non è indicata."
            )

            recommended_checks.append(
                f"Verificare la provenienza ufficiale dell'avviso {number}."
            )

    # Raccomandazioni per allerte attive.
    if active:
        recommendations.extend([
            "Consultare il bollettino e le istruzioni aggiornate "
            "delle autorità competenti.",
            "Verificare gli aggiornamenti ufficiali prima di assumere "
            "decisioni.",
            "Condividere le informazioni indicando chiaramente "
            "fonte e periodo di validità.",
        ])

    # Raccomandazioni per allerte future.
    if upcoming:
        recommendations.append(
            "È presente almeno un'allerta ufficiale con validità futura. "
            "Consultare il relativo bollettino e monitorare gli aggiornamenti "
            "delle autorità competenti in prossimità dell'inizio della validità."
        )

        for alert in upcoming:
            number = alert.get("alert_number") or "senza numero"
            valid_from = alert.get("valid_from")

            if valid_from:
                recommendations.append(
                    f"L'avviso {number} ha inizio validità previsto per "
                    f"{valid_from}."
                )

    # Raccomandazioni per allerte scadute.
    if expired:
        recommendations.append(
            "Le allerte scadute non devono essere presentate come attive. "
            "Verificare eventuali nuovi bollettini o proroghe."
        )

    # Raccomandazioni per validità sconosciuta.
    if unknown:
        recommendations.append(
            "Non è possibile stabilire se tutte le allerte analizzate "
            "siano attive, future o scadute. Verificare la loro validità "
            "prima di formulare conclusioni sulla situazione."
        )

    # Nessuna allerta disponibile.
    if not alerts:
        recommendations.append(
            "Non sono disponibili allerte ufficiali nell'analisi corrente. "
            "Questo non dimostra l'assenza di rischi: verificare le fonti "
            "ufficiali aggiornate."
        )

    # Se esistono allerte, ma nessuna è attiva, lo dichiariamo
    # senza confondere questa condizione con l'assenza di rischi.
    if alerts and not active and not unknown:
        recommendations.append(
            "Nessuna delle allerte analizzate risulta attiva "
            "al momento della valutazione."
        )

    if not alerts:
        assessment_status = "insufficient_data"
    elif missing_information:
        assessment_status = "partial"
    else:
        assessment_status = "completed"

    return {
        "agent": "safety_assessment_agent",
        "assessment_status": assessment_status,
        "observations": observations,
        "active_alert_count": len(active),
        "active_risk_count": len(active_risks),
        "affected_area_count": len(affected_areas),
        "recommendations": list(dict.fromkeys(recommendations)),
        "recommended_checks": list(dict.fromkeys(recommended_checks)),
        "missing_information": list(dict.fromkeys(missing_information)),
        "limitations": [
            "Questa è una sintesi informativa e non una valutazione "
            "ufficiale di pubblica sicurezza.",
            "Non vengono impartite istruzioni di evacuazione o soccorso.",
            "Le indicazioni operative devono provenire dalle autorità competenti.",
            "L'assenza di allerte attive nei dati analizzati non dimostra "
            "l'assenza di rischi sul territorio.",
            "Le allerte future non devono essere presentate come allerte attive.",
        ],
    }
