
def analyze(
    incident=None,
    traffic_analysis=None,
    transport_analysis=None
):
    """
    Valuta i possibili impatti di un evento sulla mobilità.

    Utilizza i risultati dei Traffic e Public Transport Agent.

    Le conseguenze individuate sono ipotesi da verificare,
    non fatti accertati.
    """

    incident = incident if isinstance(incident, dict) else {}
    traffic_analysis = (
        traffic_analysis
        if isinstance(traffic_analysis, dict)
        else {}
    )
    transport_analysis = (
        transport_analysis
        if isinstance(transport_analysis, dict)
        else {}
    )

    description = (
        incident.get("description")
        if isinstance(incident.get("description"), str)
        else ""
    ).lower()

    event_type = incident.get("event_type", "")

    possible_impacts = []
    missing_information = []
    supporting_observations = []
    required_checks = []

    # --------------------------------------------------
    # 1. Analisi della descrizione dell'evento
    # --------------------------------------------------

    is_accident = any(word in description for word in [
        "incidente",
        "collisione",
        "scontro"
    ])

    is_flooding = any(word in description for word in [
        "allagamento",
        "allagata",
        "allagato",
        "acqua sulla strada"
    ])

    is_road_closure = any(word in description for word in [
        "strada chiusa",
        "strada bloccata",
        "chiusura",
        "blocco stradale"
    ])

    is_fire = any(word in description for word in [
        "incendio",
        "fumo"
    ])

    is_weather_event = any(word in description for word in [
        "temporale",
        "forte pioggia",
        "vento forte",
        "maltempo"
    ])

    if is_accident:
        possible_impacts.extend([
            "Possibili rallentamenti della circolazione.",
            "Possibili code nelle strade limitrofe.",
            "Possibili ritardi per il trasporto pubblico."
        ])

        supporting_observations.append(
            "La descrizione dell'evento indica un possibile incidente."
        )

    if is_flooding:
        possible_impacts.extend([
            "Possibile riduzione della percorribilità stradale.",
            "Possibili difficoltà per veicoli e pedoni.",
            "Possibili deviazioni dei mezzi pubblici."
        ])

        supporting_observations.append(
            "La descrizione dell'evento indica un possibile allagamento."
        )

    if is_road_closure:
        possible_impacts.extend([
            "Possibile interruzione della circolazione.",
            "Possibile necessità di percorsi alternativi.",
            "Possibili ripercussioni sulle linee di trasporto pubblico."
        ])

        supporting_observations.append(
            "La descrizione indica una possibile chiusura stradale."
        )

    if is_fire:
        possible_impacts.extend([
            "Possibili limitazioni alla circolazione nell'area interessata.",
            "Possibili deviazioni o rallentamenti."
        ])

        supporting_observations.append(
            "La descrizione indica un possibile incendio."
        )

    if is_weather_event:
        possible_impacts.append(
            "Possibili difficoltà nella circolazione "
            "a causa delle condizioni meteorologiche."
        )

        supporting_observations.append(
            "La descrizione segnala condizioni meteorologiche avverse."
        )

    if not description:
        missing_information.append(
            "Descrizione dell'evento non disponibile."
        )

    # --------------------------------------------------
    # 2. Analisi dei risultati del Traffic Agent
    # --------------------------------------------------

    traffic_conditions = traffic_analysis.get(
        "traffic_conditions",
        []
    )

    if not isinstance(traffic_conditions, list):
        traffic_conditions = []
        missing_information.append(
            "Il formato delle condizioni del traffico non è valido."
        )

    if not traffic_conditions:
        missing_information.append(
            "Non sono disponibili informazioni sulle condizioni "
            "della viabilità."
        )

    for condition in traffic_conditions:

        if not isinstance(condition, dict):
            continue

        road = condition.get(
            "road",
            "Strada non identificata"
        )

        status = condition.get("status", "unknown")

        outdated = condition.get("data_outdated", True)

        if not isinstance(status, str):
            status = "unknown"

        status = status.lower()

        # I dati obsoleti non vengono utilizzati come
        # indicazione di una condizione attuale.
        if outdated:
            supporting_observations.append(
                f"Le informazioni su {road} sono obsolete "
                "e non consentono una valutazione attuale."
            )

            # Un dato obsoleto equivale a un dato mancante: la valutazione
            # non può dirsi completa.
            missing_information.append(
                f"Le informazioni su {road} sono obsolete."
            )

            required_checks.append(
                f"Aggiornare le informazioni sulla viabilità "
                f"di {road}."
            )

            continue

        if status == "slow":
            possible_impacts.append(
                f"Possibili rallentamenti in prossimità di {road}."
            )

            supporting_observations.append(
                f"Sono riportati rallentamenti per {road}."
            )

        elif status == "congested":
            possible_impacts.append(
                f"Possibili code e tempi di percorrenza maggiori "
                f"in prossimità di {road}."
            )

            supporting_observations.append(
                f"È segnalato traffico intenso su {road}."
            )

        elif status == "blocked":
            possible_impacts.append(
                f"Possibili interruzioni della circolazione "
                f"in prossimità di {road}."
            )

            supporting_observations.append(
                f"È segnalato un blocco della circolazione su {road}."
            )

        elif status == "closed":
            possible_impacts.append(
                f"Possibile necessità di percorsi alternativi "
                f"per evitare {road}."
            )

            supporting_observations.append(
                f"È segnalata una chiusura stradale per {road}."
            )

        elif status == "flooded":
            possible_impacts.append(
                f"Possibili difficoltà di percorrenza "
                f"in prossimità di {road}."
            )

            supporting_observations.append(
                f"È segnalato un allagamento in prossimità di {road}."
            )

        elif status == "incident":
            possible_impacts.append(
                f"Possibili rallentamenti e code in prossimità "
                f"di {road}."
            )

            supporting_observations.append(
                f"È segnalato un incidente su {road}."
            )

        elif status == "unknown":
            missing_information.append(
                f"Non è conosciuta la condizione attuale di {road}."
            )

            required_checks.append(
                f"Verificare la situazione della viabilità "
                f"su {road}."
            )

    # --------------------------------------------------
    # 3. Analisi dei servizi di trasporto pubblico
    # --------------------------------------------------

    services = transport_analysis.get("services", [])

    if not isinstance(services, list):
        services = []
        missing_information.append(
            "Il formato dei dati sul trasporto pubblico non è valido."
        )

    if not services:
        missing_information.append(
            "Non sono disponibili informazioni sui servizi "
            "di trasporto pubblico."
        )

    for service in services:

        if not isinstance(service, dict):
            continue

        name = service.get(
            "name",
            "Servizio non identificato"
        )

        status = service.get("status", "unknown")

        outdated = service.get("data_outdated", True)

        if not isinstance(status, str):
            status = "unknown"

        status = status.lower()

        if outdated:
            supporting_observations.append(
                f"Le informazioni sul servizio {name} "
                "sono obsolete."
            )

            missing_information.append(
                f"Le informazioni sul servizio {name} sono obsolete."
            )

            required_checks.append(
                f"Aggiornare le informazioni sul servizio {name}."
            )

            continue

        if status == "delayed":
            possible_impacts.append(
                f"Possibili ritardi per gli utenti del servizio {name}."
            )

            supporting_observations.append(
                f"Il servizio {name} risulta in ritardo."
            )

        elif status in {"suspended", "cancelled"}:
            possible_impacts.append(
                f"Possibili interruzioni degli spostamenti "
                f"che utilizzano il servizio {name}."
            )

            supporting_observations.append(
                f"Il servizio {name} risulta "
                f"{'sospeso' if status == 'suspended' else 'cancellato'}."
            )

        elif status == "disrupted":
            possible_impacts.append(
                f"Possibili disagi per gli utenti del servizio {name}."
            )

            supporting_observations.append(
                f"Il servizio {name} presenta criticità."
            )

        elif status == "unknown":
            missing_information.append(
                f"Non è conosciuto lo stato del servizio {name}."
            )

            required_checks.append(
                f"Verificare lo stato del servizio {name}."
            )

    # --------------------------------------------------
    # 4. Valutazione delle informazioni disponibili
    # --------------------------------------------------

    if not traffic_analysis:
        missing_information.append(
            "Analisi del Traffic Agent non disponibile."
        )

    if not transport_analysis:
        missing_information.append(
            "Analisi del Public Transport Agent non disponibile."
        )

    if not possible_impacts:
        observations_message = (
            "Non sono stati individuati impatti specifici "
            "sulla mobilità con le informazioni disponibili."
        )
    else:
        observations_message = (
            "Sono stati individuati possibili impatti "
            "che richiedono valutazione."
        )

    possible_impacts = list(dict.fromkeys(possible_impacts))
    missing_information = list(dict.fromkeys(missing_information))
    supporting_observations = list(
        dict.fromkeys(supporting_observations)
    )
    required_checks = list(dict.fromkeys(required_checks))

    if not supporting_observations:
        assessment_status = "insufficient_data"
    elif missing_information:
        assessment_status = "partial"
    else:
        assessment_status = "completed"

    # --------------------------------------------------
    # 5. Risultato
    # --------------------------------------------------

    return {
        "agent": "mobility_impact_agent",
        "assessment_type": "potential_impact",
        "assessment_status": assessment_status,
        "possible_impacts": possible_impacts,
        "supporting_observations": supporting_observations,
        "missing_information": missing_information,
        "required_checks": required_checks,
        "summary": observations_message,
        "limitations": [
            "Gli impatti individuati sono ipotesi e non fatti accertati.",
            "L'analisi utilizza esclusivamente i dati ricevuti.",
            "Le informazioni obsolete non vengono considerate "
            "indicazioni delle condizioni attuali.",
            "L'agente non determina autonomamente chiusure, "
            "deviazioni o interruzioni dei servizi.",
            "Le decisioni operative richiedono verifica umana."
        ]
    }
