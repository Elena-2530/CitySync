"""Test della comprensione delle domande (intento, luoghi, profilo)."""

from agents.mobility import question_parser


def test_tourist_question_extracts_route():
    parsed = question_parser.parse_question(
        "Sono a Piazza Garibaldi e voglio raggiungere Castel dell'Ovo. "
        "Qual è il modo migliore per arrivarci?",
        user_type="tourist"
    )
    assert parsed["intent"] == "route"
    assert parsed["origin"] == "Piazza Garibaldi"
    assert parsed["destination"] == "Castel dell'Ovo"
    # Un turista preferisce meno cambi.
    assert parsed["profile"] == "fewest_transfers"


def test_da_a_pattern():
    parsed = question_parser.parse_question(
        "Come posso arrivare da Piazza Garibaldi a Fuorigrotta "
        "utilizzando i mezzi pubblici?"
    )
    assert parsed["intent"] == "route"
    assert parsed["origin"] == "Piazza Garibaldi"
    assert parsed["destination"] == "Fuorigrotta"


def test_operator_and_user_intents():
    cases = {
        "Quali strade potrebbero essere interessate?": "affected_roads",
        "Come posso evitare il traffico?": "avoid_traffic",
        "Quali informazioni mancano?": "missing_info",
        "Quali sono le conseguenze sulla mobilità?": "impact",
        "La Linea 1 funziona?": "transport_status",
    }
    for question, expected in cases.items():
        assert question_parser.parse_question(question)["intent"] == expected, question


def test_accessibility_profile():
    parsed = question_parser.parse_question(
        "Devo andare da Piazza Garibaldi al MANN in carrozzina"
    )
    assert parsed["profile"] == "accessible"


def test_unrelated_text_is_general_and_has_no_places():
    parsed = question_parser.parse_question("ciao")
    assert parsed["intent"] == "general"
    assert parsed["origin"] is None
    assert parsed["destination"] is None


def test_non_string_question_is_safe():
    parsed = question_parser.parse_question(None)
    assert parsed["intent"] == "general"
