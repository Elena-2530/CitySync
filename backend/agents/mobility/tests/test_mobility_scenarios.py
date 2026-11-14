"""
Scenari completi del Mobility Agent: le richieste di Janara, operatori e utenti
descritte nelle specifiche. I dati sono simulati.
"""

import pytest

from agents.mobility.mobility_agent import analyze_mobility_request

INCIDENT = {
    "id": 15,
    "event_type": "traffic",
    "description": "Incidente stradale a Fuorigrotta. Traffico rallentato e veicoli in coda.",
    "location": "Fuorigrotta, Napoli",
    "verification_status": "unverified"
}


def ask(sender, request_type, question=None, incident=None, context=None):
    return analyze_mobility_request({
        "request_id": "TEST",
        "sender": sender,
        "request_type": request_type,
        "question": question,
        "incident": incident,
        "context": context or {}
    })


def text_of(result):
    return result["response"]["response"]


def test_janara_incident_analysis():
    result = ask("janara", "incident_analysis", incident=INCIDENT)

    assert result["status"] == "analysis_completed"
    assert result["problem_type"]["type"] == "incidente_stradale"
    assert result["action_plan"]
    assert result["missing_information"]
    assert result["required_checks"]
    assert result["specialist_analyses"]["mobility_impact"]["possible_impacts"]
    # Segnalazione non verificata: l'affidabilità non può essere alta.
    assert result["confidence"]["level"] == "low"
    assert result["limitations"]


def test_agent_never_states_unverified_facts_as_confirmed():
    result = ask("janara", "incident_analysis", incident=INCIDENT)
    text = text_of(result).lower()
    assert "confermat" not in text or "non" in text
    assert "ipotesi" in text or "potenzial" in text


def test_operator_asks_which_roads():
    result = ask("operator", "question", "Quali strade potrebbero essere interessate?",
                 incident=INCIDENT)
    text = text_of(result)
    assert result["request"]["intent"] == "affected_roads"
    assert "Via Giulio Cesare" in text
    # Le strade sono assi principali indicativi, non strade accertate.
    assert "ipotesi" in text.lower()


def test_operator_asks_missing_information():
    result = ask("operator", "question", "Quali informazioni mancano?", incident=INCIDENT)
    text = text_of(result)
    assert result["request"]["intent"] == "missing_info"
    assert "Informazioni mancanti" in text
    assert "Verifiche necessarie" in text


def test_user_asks_how_to_avoid_traffic_without_invented_traffic_data():
    result = ask("user", "question", "Come posso evitare il traffico?",
                 incident=INCIDENT, context={"location": "Fuorigrotta"})
    text = text_of(result).lower()
    assert "non ho dati sul traffico in tempo reale" in text


def test_tourist_gets_a_route_with_disclaimer():
    result = ask(
        "user", "question",
        "Sono a Piazza Garibaldi e voglio raggiungere Castel dell'Ovo. "
        "Qual è il modo migliore per arrivarci?",
        context={"user_type": "tourist"}
    )
    text = text_of(result)
    assert "percorso consigliato" in text
    assert "stime" in text
    assert "tempo reale" in text
    assert result["response"]["recommended_route"]["realtime_verified"] is False


def test_route_avoids_suspended_segment_and_says_so():
    services = [{
        "name": "Metro Linea 1",
        "operator": "ANM",
        "status": "suspended",
        "between": ["Università", "Municipio"],
        "source": "esempio_simulato"
    }]
    result = ask("user", "route_request", context={
        "origin": "Piazza Garibaldi",
        "destination": "Castel dell'Ovo",
        "transport_data": {"services": services}
    })
    assert result["route_plan"]["excluded_lines"]
    route = result["response"]["recommended_route"]
    for step in route["steps"]:
        if step["type"] == "ride" and step["line_id"] == "L1":
            assert not (step["from"] == "Garibaldi" and step["to"] == "Municipio")


def test_unknown_place_is_declared_not_guessed():
    result = ask("user", "route_request", context={
        "origin": "Posillipo", "destination": "Piazza Garibaldi"
    })
    assert "Non riconosco" in text_of(result)
    assert result["response"]["recommended_route"] is None
    assert any("Posillipo" in item for item in result["missing_information"])


def test_line_status_question_without_data_does_not_invent_status():
    result = ask("user", "question", "La Linea 1 funziona?")
    text = text_of(result).lower()
    assert "non ho informazioni aggiornate" in text


def test_unrelated_question_has_no_confidence():
    result = ask("user", "question", "ciao")
    assert result["confidence"]["level"] == "not_applicable"


def test_request_is_not_modified_by_the_agent():
    request = {
        "request_id": "TEST",
        "sender": "user",
        "request_type": "route_request",
        "question": None,
        "incident": None,
        "context": {"origin": "Piazza Garibaldi", "destination": "Mergellina"}
    }
    snapshot = {**request, "context": dict(request["context"])}
    analyze_mobility_request(request)
    assert request == snapshot


@pytest.mark.parametrize("bad_request", [
    "non un dizionario",
    {"sender": "sconosciuto", "request_type": "question"},
    {"sender": "user", "request_type": "boh"},
    {"sender": "janara", "request_type": "incident_analysis"},
    {"sender": "user", "request_type": "route_request",
     "context": {"origin": "Piazza Garibaldi"}},
])
def test_invalid_requests_are_rejected(bad_request):
    with pytest.raises(ValueError):
        analyze_mobility_request(bad_request)
