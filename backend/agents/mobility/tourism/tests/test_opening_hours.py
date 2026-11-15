"""Test del calcolo di apertura e dell'affidabilità degli orari."""

from datetime import date, datetime

from agents.tourism import opening_hours as oh
from agents.tourism.tourism_data import places


def place(place_id):
    return places.get_place(place_id)


def test_easter_and_holidays():
    assert oh.easter(2026) == date(2026, 4, 5)
    assert oh.is_italian_holiday(date(2026, 4, 6))      # Lunedì dell'Angelo
    assert oh.is_italian_holiday(date(2026, 12, 8))     # Immacolata
    assert not oh.is_italian_holiday(date(2026, 11, 14))


def test_castel_nuovo_open_closed_and_last_entry():
    castel = place("castel_nuovo")
    # sabato 14 novembre 2026
    assert oh.open_status(castel, datetime(2026, 11, 14, 11, 0))["status"] == "open"
    assert oh.open_status(castel, datetime(2026, 11, 14, 18, 30))["status"] == "closed"
    # dopo l'ultimo ingresso (17:30) non si entra più
    assert oh.open_status(castel, datetime(2026, 11, 14, 17, 45))["status"] == "closed"
    # domenica chiuso
    assert oh.open_status(castel, datetime(2026, 11, 15, 11, 0))["status"] == "closed"
    # lunedì aperto
    assert oh.open_status(castel, datetime(2026, 11, 16, 10, 0))["status"] == "open"


def test_holiday_makes_status_unknown_when_source_excludes_holidays():
    castel = place("castel_nuovo")
    # 8 dicembre 2026 è un martedì festivo: la fonte dice "esclusi i festivi"
    assert oh.open_status(castel, datetime(2026, 12, 8, 11, 0))["status"] == "unknown"


def test_duomo_split_hours():
    duomo = place("duomo")
    assert oh.open_status(duomo, datetime(2026, 11, 16, 14, 0))["status"] == "closed"   # pausa lunedì
    assert oh.open_status(duomo, datetime(2026, 11, 16, 15, 0))["status"] == "open"
    assert oh.open_status(duomo, datetime(2026, 11, 15, 12, 0))["status"] == "open"     # domenica mattina
    assert oh.open_status(duomo, datetime(2026, 11, 15, 14, 0))["status"] == "closed"   # domenica pausa


def test_closed_weekday_from_source():
    palazzo = place("palazzo_reale")
    assert oh.open_status(palazzo, datetime(2026, 11, 18, 11, 0))["status"] == "closed"  # mercoledì
    assert oh.open_status(palazzo, datetime(2026, 11, 19, 11, 0))["status"] == "open"


def test_no_hours_never_gives_open_or_closed():
    for place_id in ("castel_dell_ovo", "teatro_san_carlo", "piazza_plebiscito", "spaccanapoli"):
        status = oh.open_status(place(place_id), datetime(2026, 11, 14, 11, 0))
        assert status["status"] == "unknown", place_id


def test_reliability_levels():
    today = date(2026, 11, 14)
    assert oh.reliability(place("castel_nuovo")["hours"], today) == "high"
    assert oh.reliability(place("palazzo_reale")["hours"], today) == "medium"   # ufficiale senza data
    assert oh.reliability(place("mann")["hours"], today) == "low"               # non ufficiale
    assert oh.reliability(place("castel_dell_ovo")["hours"], today) == "none"
    # Una fonte ufficiale vecchia non è più "alta".
    assert oh.reliability(place("castel_nuovo")["hours"], date(2027, 6, 1)) == "medium"


def test_weekly_summary_groups_days():
    summary = oh.weekly_summary(place("castel_nuovo"))
    assert "lunedì-sabato: 09:00-18:00" in summary
    assert "domenica: chiuso" in summary
    assert "ultimo ingresso 17:30" in summary
    assert oh.weekly_summary(place("castel_dell_ovo")) is None


def test_parse_when_context_and_words():
    now = datetime(2026, 11, 14, 10, 0)  # sabato

    given = oh.parse_when("", {"when": "2026-11-20T15:30"}, now)
    assert given["datetime"] == datetime(2026, 11, 20, 15, 30)

    tomorrow = oh.parse_when("è aperto domani?", {}, now)
    assert tomorrow["datetime"].date() == date(2026, 11, 15)
    assert tomorrow["has_time"] is False

    sunday = oh.parse_when("è aperto domenica?", {}, now)
    assert sunday["datetime"].date() == date(2026, 11, 15)

    timed = oh.parse_when("è aperto lunedì alle 15:30?", {}, now)
    assert timed["datetime"] == datetime(2026, 11, 16, 15, 30)
    assert timed["has_time"] is True

    assert oh.parse_when("è aperto?", {}, now)["datetime"] == now
