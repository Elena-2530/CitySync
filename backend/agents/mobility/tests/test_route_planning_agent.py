
from datetime import datetime, timezone, timedelta

from agents.mobility.specialists.route_planning_agent import analyze


def test_route_planning_agent():

    now = datetime.now(timezone.utc)

    context = {
        "origin": "Piazza Garibaldi, Napoli",
        "destination": "Fuorigrotta, Napoli",
        "max_route_age_minutes": 30,
        "route_options": [
            {
                "name": "Percorso A",
                "duration_minutes": 45,
                "distance_km": 8,
                "status": "available",
                "source": "test_source",
                "updated_at": now.isoformat()
            },
            {
                "name": "Percorso B",
                "duration_minutes": 25,
                "distance_km": 7,
                "status": "available",
                "source": "test_source",
                "updated_at": now.isoformat()
            },
            {
                "name": "Percorso C",
                "status": "disrupted",
                "source": "test_source",
                "updated_at": now.isoformat()
            },
            {
                "name": "Percorso D",
                "status": "unavailable",
                "source": "test_source",
                "updated_at": now.isoformat()
            },
            {
                "name": "Percorso E",
                "status": "available",
                "source": "test_source",
                "updated_at": (
                    now - timedelta(hours=2)
                ).isoformat()
            },
            {
                "name": "Percorso F",
                "status": "available",
                "source": None,
                "updated_at": now.isoformat()
            }
        ]
    }

    result = analyze(context)

    assert result["analysis_status"] == "partial"

    assert result["origin"] == "Piazza Garibaldi, Napoli"
    assert result["destination"] == "Fuorigrotta, Napoli"

    # I primi due percorsi sono raccomandabili.
    assert result["recommended_route"]["name"] == "Percorso A"

    assert len(result["alternative_routes"]) == 1
    assert result["alternative_routes"][0]["name"] == "Percorso B"

    # Il percorso con criticità non deve essere raccomandato.
    assert all(
        route["status"] != "disrupted"
        for route in result["alternative_routes"]
    )

    # Il percorso obsoleto non deve essere raccomandato.
    assert all(
        route["name"] != "Percorso E"
        for route in result["alternative_routes"]
    )

    assert len(result["missing_information"]) > 0
    assert len(result["required_checks"]) > 0

    print("\n===== ROUTE PLANNING AGENT =====")

    print(
        "Percorso raccomandato:",
        result["recommended_route"]["name"]
    )

    print("\nPercorsi alternativi:")

    for route in result["alternative_routes"]:
        print("-", route["name"])

    print("\nInformazioni mancanti:")

    for item in result["missing_information"]:
        print("-", item)

    print("\nVerifiche richieste:")

    for item in result["required_checks"]:
        print("-", item)

    print("\nTEST SUPERATO")


if __name__ == "__main__":
    test_route_planning_agent()
