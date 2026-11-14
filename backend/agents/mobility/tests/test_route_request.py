
import json

from agents.mobility.mobility_agent import analyze_mobility_request


def test_route_request():
    request = {
        "request_id": "MOBILITY-ROUTE-TEST-001",
        "sender": "user",
        "request_type": "route_request",
        "question": (
            "Come posso arrivare da Piazza Garibaldi "
            "a Fuorigrotta utilizzando i mezzi pubblici?"
        ),
        "incident": None,
        "context": {
            "origin": "Piazza Garibaldi, Napoli",
            "destination": "Fuorigrotta, Napoli",
            "transport_data": {},
            "route_options": []
        }
    }

    result = analyze_mobility_request(request)

    # Verifica che la richiesta sia stata elaborata.
    assert result["status"] == "analysis_completed"

    # Non deve essere necessario un incidente.
    assert result["incident"] is None

    # Devono essere attivati gli specialisti corretti.
    assert "public_transport" in result["selected_specialists"]
    assert "route_planning" in result["selected_specialists"]

    # Non devono essere attivati specialisti non pertinenti.
    assert "traffic" not in result["selected_specialists"]
    assert "mobility_impact" not in result["selected_specialists"]

    # Le analisi devono essere presenti.
    assert result["specialist_analyses"]["public_transport"] is not None
    assert result["specialist_analyses"]["route_planning"] is not None

    # Senza dati reali non deve essere inventato un percorso.
    route = result["specialist_analyses"]["route_planning"]
    assert route["recommended_route"] is None

    print("\n===== TEST RICHIESTA PERCORSO =====")
    print(json.dumps(result, indent=4, ensure_ascii=False))
    print("\nTEST SUPERATO: richiesta di percorso gestita correttamente.")


if __name__ == "__main__":
    test_route_request()
