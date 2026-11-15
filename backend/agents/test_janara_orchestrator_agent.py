"""Test di Janara: instradamento, handoff, incidenti, errori, rivalutazione."""

import os
import tempfile

import pytest

from agents import janara_orchestrator_agent as janara


def ask(question=None, sender="user", request_type="question", context=None):
    return janara.handle_request({"request_id": "T", "sender": sender, "request_type": request_type,
                                  "question": question, "context": context or {}})


def called(result):
    return [t["agent"] for t in result["agents_called"]]


@pytest.fixture()
def db(monkeypatch):
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    monkeypatch.setenv("NEURAPOLIS_DB_PATH", path)
    from services.database import get_connection, init_db
    init_db()

    def make(description, event_type="traffic", location="Fuorigrotta, Napoli"):
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO incidents (event_type, description, location, created_at, updated_at)"
            " VALUES (?,?,?,?,?)", (event_type, description, location, "2026-11-14", "2026-11-14"))
        conn.commit()
        conn.close()
        return cur.lastrowid
    return make


# --- instradamento ---------------------------------------------------------

def test_routing_by_topic():
    assert called(ask("Quando apre il Castel Nuovo?")) == ["tourism"]
    assert called(ask("C'è traffico a Fuorigrotta?")) == ["mobility"]


def test_route_to_place_uses_tourism_then_mobility_handoff():
    r = ask("Come arrivo al MANN?", context={"origin": "Piazza Garibaldi"})
    assert called(r) == ["tourism", "mobility"]
    assert "Metro" in r["response"]
    assert r["agents_called"][1]["request_type"] == "route_request"


def test_missing_origin_is_reported_not_invented():
    r = ask("Come arrivo al MANN?")
    assert called(r) == ["tourism"]
    assert any("partenza" in m.lower() for m in r["missing_information"])
    assert r["unresolved_handoffs"]


def test_out_of_scope_question_is_declared():
    r = ask("Chi ha vinto la partita?")
    assert called(r) == []
    assert r["confidence"]["level"] == "not_applicable"
    assert "Non so rispondere" in r["response"]


def test_operator_gets_trace_user_does_not():
    assert "Agenti interpellati" in ask("Quando apre il Castel Nuovo?", sender="operator")["response"]
    assert "Agenti interpellati" not in ask("Quando apre il Castel Nuovo?")["response"]


def test_confidence_is_the_lowest_of_agents():
    r = ask("Quando apre Castel dell'Ovo?")   # orari ignoti -> low
    assert r["confidence"]["level"] == "low"


# --- errori e limiti -----------------------------------------------------------

def test_agent_failure_does_not_crash(monkeypatch):
    def boom(request):
        raise RuntimeError("guasto")
    monkeypatch.setitem(janara.AGENT_CALLERS, "tourism", boom)
    r = ask("Quando apre il Castel Nuovo?")
    assert r["status"] == "completed_with_errors"
    assert any("tourism" in l and "guasto" in l for l in r["limitations"])


def test_handoff_loop_is_capped(monkeypatch):
    counter = iter(range(1000))

    def looping(target):
        return lambda request: {"response": "x", "suggested_handoffs": [
            {"agent": target, "request_type": "question", "question": f"q{next(counter)}", "context": {}}]}
    monkeypatch.setitem(janara.AGENT_CALLERS, "tourism", looping("mobility"))
    monkeypatch.setitem(janara.AGENT_CALLERS, "mobility", looping("tourism"))
    r = ask("Quando apre il Castel Nuovo?")
    assert len(r["agents_called"]) == janara.MAX_AGENT_CALLS
    assert any("Limite" in e["error"] for e in r["errors"])


def test_combined_confidence_takes_the_lowest(monkeypatch):
    monkeypatch.setitem(janara.AGENT_CALLERS, "tourism", lambda r: {
        "response": "a", "confidence": {"level": "high", "reasons": []},
        "suggested_handoffs": [{"agent": "mobility", "request_type": "question", "context": {}}]})
    monkeypatch.setitem(janara.AGENT_CALLERS, "mobility", lambda r: {
        "response": "b", "confidence": {"level": "low", "reasons": ["dati scarsi"]}})
    r = ask("Quando apre il Castel Nuovo?")
    assert r["confidence"]["level"] == "low"


@pytest.mark.parametrize("bad", [
    "testo", {"sender": "boh", "request_type": "question", "question": "a"},
    {"sender": "user", "request_type": "boh"},
    {"sender": "user", "request_type": "question"},
    {"sender": "user", "request_type": "incident_assessment", "context": {}},
    {"sender": "user", "request_type": "question", "question": "a", "context": "no"},
])
def test_invalid_requests(bad):
    with pytest.raises(ValueError):
        janara.handle_request(bad)


# --- incidenti ----------------------------------------------------------------------

def test_unverified_incident_stays_a_hypothesis(db):
    incident_id = db("Possibile allagamento a Fuorigrotta dopo il temporale.", "environment")
    r = ask(request_type="incident_assessment", context={"incident_id": incident_id})
    assert called(r) == ["social_intelligence", "verification", "mobility"]
    assert "ipotesi" in r["response"]
    assert r["confidence"]["level"] == "low"
    assert r["required_checks"]


def test_confirmed_incident_is_not_flagged_unverified(db):
    from agents.verification_agent import add_evidence
    incident_id = db("Incidente stradale su via Marina.")
    add_evidence(incident_id, "Polizia Locale", "https://pl.example/1", "Conferma", "official_confirmation")
    r = ask(f"Cosa sai dell'incidente {incident_id}?")
    assert r["incident"]["id"] == incident_id
    assert "confermata" in r["response"] and "ipotesi" not in r["response"]


def test_non_mobility_incident_skips_mobility(db):
    incident_id = db("Rissa in piazza.", "other")
    r = ask(request_type="incident_assessment", context={"incident_id": incident_id})
    assert "mobility" not in called(r)


def test_unknown_incident_is_declared(db):
    r = ask(request_type="incident_assessment", context={"incident_id": 9999})
    assert "non trovato" in r["response"]
    assert r["missing_information"]


# --- cambio di condizioni --------------------------------------------------------------

def test_reassess_with_rain_changes_places():
    first = ask("Cosa vedere vicino a Municipio?", context={"when": "2026-11-14T11:00"})
    second = janara.reassess(first, {"weather": "rain"})
    assert second["revision"]["changes_applied"] == {"weather": "rain"}
    assert second["revision"]["differences"] != ["Le nuove condizioni non cambiano la risposta."]


def test_reassess_validates_input():
    first = ask("Quando apre il Castel Nuovo?")
    with pytest.raises(ValueError):
        janara.reassess(first, {})
    with pytest.raises(ValueError):
        janara.reassess({}, {"weather": "rain"})


def test_reassess_detects_verification_change(db):
    from agents.verification_agent import add_evidence
    incident_id = db("Strada bloccata a Fuorigrotta.")
    first = ask(request_type="incident_assessment", context={"incident_id": incident_id})
    add_evidence(incident_id, "Comune", "https://c.example/1", "ok", "official_confirmation")
    second = janara.reassess(first, {"note": "nuova evidenza"})
    assert any("Stato di verifica" in d for d in second["revision"]["differences"])


def test_request_is_not_modified():
    request = {"request_id": "T", "sender": "user", "request_type": "question",
               "question": "Quando apre il Castel Nuovo?", "context": {"a": 1}}
    snapshot = {**request, "context": {"a": 1}}
    janara.handle_request(request)
    assert request == snapshot
