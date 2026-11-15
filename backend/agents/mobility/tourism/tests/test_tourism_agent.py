"""Scenari completi del Tourism Agent (richieste di Janara, operatori e utenti)."""

import pytest

from agents.tourism import question_parser
from agents.tourism.tourism_agent import analyze_tourism_request


def ask(sender, request_type, question=None, context=None):
    return analyze_tourism_request({
        "request_id": "TEST",
        "sender": sender,
        "request_type": request_type,
        "question": question,
        "context": context or {}
    })


def text_of(result):
    return result["response"]["response"]


def ids(result):
    return [p["id"] for p in result["places"]]


# --- parser ---------------------------------------------------------------

def test_parser_intents():
    cases = {
        "Quando apre il Castel Nuovo?": "hours",
        "Quanto costa il biglietto?": "tickets",
        "Dove si trova il Duomo?": "where",
        "Mi racconti la storia del MANN?": "history",
        "Cosa vedere vicino a Municipio?": "nearby",
        "Cosa posso fare se piove?": "indoor",
        "Quali musei posso visitare?": "general",   # la categoria la decide l'agente
        "ciao": "general",
    }
    for question, expected in cases.items():
        assert question_parser.parse_question(question)["intent"] == expected, question
    assert question_parser.parse_question("Quali musei posso visitare?")["category"] == "museum"
    assert question_parser.parse_question("Come arrivo al MANN?")["asks_route"] is True


# --- orari: l'agente non inventa -------------------------------------------

def test_hours_from_official_recent_source():
    result = ask("user", "question", "Quando apre il Castel Nuovo?", {"when": "2026-11-14T11:00"})
    text = text_of(result)
    assert result["request"]["intent"] == "hours"
    assert result["confidence"]["level"] == "high"
    assert "09:00-18:00" in text and "Comune di Napoli" in text
    assert "risulta aperto" in text
    assert result["places"][0]["open_status"]["status"] == "open"


def test_hours_from_unofficial_old_source_are_flagged():
    result = ask("user", "question", "Il MANN è aperto?", {"when": "2026-11-17T10:00"})
    text = text_of(result)
    assert result["confidence"]["level"] == "low"
    assert "non ufficiale" in text
    assert "superata" in text
    assert result["required_checks"]


def test_unknown_hours_are_declared_not_invented():
    result = ask("user", "question", "A che ora apre Castel dell'Ovo?")
    text = text_of(result)
    assert "Non ho orari verificati" in text
    assert "risulta aperto" not in text and "risulta chiuso" not in text
    assert result["missing_information"]
    assert result["confidence"]["level"] == "low"


def test_day_question_uses_day_schedule():
    result = ask("user", "question", "Il Castel Nuovo è aperto domenica?")
    assert "Domenica risulta chiuso" in text_of(result)


def test_unverified_prices_are_not_invented():
    result = ask("user", "question", "Quanto costa il biglietto del MANN?")
    text = text_of(result)
    assert "Non ho informazioni verificate sui prezzi" in text
    assert "€" not in text
    assert result["missing_information"]


def test_verified_prices_come_with_source():
    result = ask("user", "question", "Quanto costa il biglietto del Palazzo Reale?")
    text = text_of(result)
    assert "15 €" in text
    assert "Ministero della Cultura" in text


# --- luoghi, storia, indirizzi ------------------------------------------------

def test_history_and_where():
    history = ask("user", "question", "Mi racconti la storia della Cappella Sansevero?")
    assert "Sanmartino" in text_of(history)
    where = ask("user", "question", "Dove si trova il Duomo?")
    assert "Via Duomo 147" in text_of(where)
    assert where["places"][0]["coordinates_approximate"] is True


def test_unknown_place_is_declared():
    result = ask("user", "question", "Quando apre il Colosseo?", {"place": "Colosseo"})
    assert "Non ho informazioni" in text_of(result)
    assert result["places"] == []
    assert result["unresolved_places"] == ["Colosseo"]


def test_missing_place_asks_which_one():
    result = ask("user", "question", "A che ora apre?")
    assert "Di quale luogo" in text_of(result)
    assert result["missing_information"]


def test_search_by_category_returns_only_that_category():
    result = ask("user", "question", "Quali musei posso visitare?")
    assert result["request"]["intent"] == "search"
    assert result["places"]
    assert all("museum" in p["categories"] for p in result["places"])


# --- vicino a, maltempo ----------------------------------------------------------

def test_nearby_with_rain_suggests_only_covered_places():
    result = ask("janara", "nearby", context={
        "location": "Piazza Municipio", "weather": "rain", "when": "2026-11-14T11:00"
    })
    assert result["places"][0]["id"] == "castel_nuovo"
    assert all(p["indoor"] in ("indoor", "covered", "partial") for p in result["places"])
    assert "piazza_plebiscito" not in ids(result)
    assert "evitare" in text_of(result) and "Plebiscito" in text_of(result)


def test_rain_warns_about_places_closed_at_that_time():
    # sabato notte: i luoghi con orari risultano chiusi
    result = ask("janara", "nearby", context={
        "location": "Piazza Municipio", "weather": "rain", "when": "2026-11-14T23:00"
    })
    assert "risultano chiusi" in text_of(result)


def test_nearby_by_coordinates():
    result = ask("operator", "nearby", context={"location": {"lat": 40.8383, "lon": 14.2529}, "radius_m": 200})
    assert ids(result) and ids(result)[0] == "castel_nuovo"


def test_nearby_without_known_center_asks_for_it():
    result = ask("user", "question", "Cosa vedere vicino a casa mia?")
    assert result["missing_information"]


# --- percorsi: si passa la mano al Mobility Agent -----------------------------------

def test_route_question_hands_off_to_mobility():
    result = ask("user", "question", "Come arrivo al MANN?", {"origin": "Piazza Garibaldi"})
    handoff = result["suggested_handoffs"][0]
    assert handoff["agent"] == "mobility"
    assert handoff["request_type"] == "route_request"
    assert handoff["context"]["origin"] == "Piazza Garibaldi"
    assert "MANN" in handoff["context"]["destination"]
    # L'agente non inventa percorsi.
    assert "minuti" not in text_of(result)


# --- destinatari e struttura ---------------------------------------------------------

def test_janara_gets_technical_header_and_sources():
    result = ask("janara", "question", "Quando apre il Castel Nuovo?", {"when": "2026-11-14T11:00"})
    text = text_of(result)
    assert text.startswith("Turismo · hours")
    assert "Fonti:" in text and "comune.napoli.it" in text
    assert "Affidabilità" in text


def test_user_gets_plain_answer_without_technical_lines():
    result = ask("user", "question", "Quando apre il Castel Nuovo?", {"when": "2026-11-14T11:00"})
    text = text_of(result)
    assert "Fonti:" not in text and "Affidabilità" not in text


def test_unrelated_question_has_no_confidence():
    assert ask("user", "question", "ciao")["confidence"]["level"] == "not_applicable"


def test_result_has_limitations_and_request_is_not_modified():
    request = {"request_id": "T", "sender": "user", "request_type": "place_info",
               "question": None, "context": {"place": "MANN"}}
    snapshot = {**request, "context": dict(request["context"])}
    result = analyze_tourism_request(request)
    assert request == snapshot
    assert result["limitations"]
    assert result["request"]["intent"] == "history"


@pytest.mark.parametrize("bad_request", [
    "non un dizionario",
    {"sender": "sconosciuto", "request_type": "question"},
    {"sender": "user", "request_type": "boh"},
    {"sender": "user", "request_type": "place_info"},
    {"sender": "user", "request_type": "nearby"},
    {"sender": "user", "request_type": "question", "context": "no"},
])
def test_invalid_requests_are_rejected(bad_request):
    with pytest.raises(ValueError):
        analyze_tourism_request(bad_request)


def test_every_place_can_be_routed_by_the_mobility_agent():
    """Il nome passato nell'handoff deve essere riconosciuto dal Mobility Agent."""
    transport_data = pytest.importorskip("agents.mobility.mobility_data.transport_data")
    from agents.tourism.tourism_data import places

    missing = [p["name"] for p in places.all_places() if transport_data.resolve_place(p["name"]) is None]
    assert missing == []
