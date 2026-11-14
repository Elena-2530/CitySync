
from agents.mobility.specialists.mobility_impact_agent import analyze


def test_mobility_impact_agent():

    incident = {
        "event_type": "environment",
        "description": "Possibile allagamento a Fuorigrotta "
                       "dopo il temporale."
    }

    traffic_analysis = {
        "traffic_conditions": [
            {
                "road": "Via Fuorigrotta",
                "status": "flooded",
                "data_outdated": False
            },
            {
                "road": "Via Marina",
                "status": "slow",
                "data_outdated": False
            },
            {
                "road": "Via Toledo",
                "status": "closed",
                "data_outdated": True
            }
        ]
    }

    transport_analysis = {
        "services": [
            {
                "name": "Metro Linea 2",
                "status": "delayed",
                "data_outdated": False
            },
            {
                "name": "Autobus linea 151",
                "status": "suspended",
                "data_outdated": False
            },
            {
                "name": "Tram",
                "status": "unknown",
                "data_outdated": True
            }
        ]
    }

    result = analyze(
        incident=incident,
        traffic_analysis=traffic_analysis,
        transport_analysis=transport_analysis
    )

    impacts = result["possible_impacts"]

    assert result["agent"] == "mobility_impact_agent"

    assert result["assessment_type"] == "potential_impact"

    assert result["assessment_status"] == "partial"

    # Impatto dell'allagamento.
    assert any(
        "Fuorigrotta" in impact
        for impact in impacts
    )

    # Impatto dei rallentamenti.
    assert any(
        "Via Marina" in impact
        for impact in impacts
    )

    # Impatto del trasporto pubblico.
    assert any(
        "Metro Linea 2" in impact
        for impact in impacts
    )

    assert any(
        "Autobus linea 151" in impact
        for impact in impacts
    )

    # Il dato obsoleto di Via Toledo non deve generare
    # un impatto attuale.
    assert not any(
        "Via Toledo" in impact
        for impact in impacts
    )

    # Devono essere segnalate informazioni mancanti
    # e verifiche necessarie.
    assert result["missing_information"]
    assert result["required_checks"]

    print("\n===== MOBILITY IMPACT AGENT =====")

    print("Stato:", result["assessment_status"])

    print("\nPossibili impatti:")

    for impact in impacts:
        print("-", impact)

    print("\nOsservazioni:")

    for observation in result["supporting_observations"]:
        print("-", observation)

    print("\nVerifiche richieste:")

    for check in result["required_checks"]:
        print("-", check)

    print("\nTEST SUPERATO")


if __name__ == "__main__":
    test_mobility_impact_agent()
