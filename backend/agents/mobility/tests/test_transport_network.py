"""Test della rete di trasporto, dei vincoli e del pianificatore di percorsi."""

import pytest

from agents.mobility.mobility_data import route_data, transport_data


def test_demo_network_is_consistent_and_declared_demo():
    network = transport_data.load_network()
    # load_network solleva ValueError se tempi di tratta o fermate non tornano.
    assert network["lines"]
    meta = network["meta"]
    assert meta["data_type"] == "static_demo"
    assert meta["realtime"] is False
    assert meta["verified"] is False


def test_unknown_place_is_not_invented():
    assert transport_data.resolve_place("Posillipo") is None
    assert transport_data.resolve_place("") is None


def test_known_place_is_resolved():
    place = transport_data.resolve_place("Piazza Garibaldi, Napoli")
    assert place is not None
    assert place["lat"] and place["lon"]


def test_segment_suspension_blocks_only_that_segment():
    disruptions = transport_data.disruptions_from_services([{
        "name": "Metro Linea 1",
        "status": "suspended",
        "between": ["Università", "Municipio"]
    }])
    assert disruptions["disabled_lines"] == {}
    assert disruptions["blocked_hops"] == {("L1", 1)}
    assert disruptions["blocked_segments"][0]["from"] == "Università"


def test_whole_line_suspension_disables_line():
    disruptions = transport_data.disruptions_from_services([
        {"name": "Metro Linea 2", "status": "suspended"}
    ])
    assert disruptions["disabled_lines"] == {"L2": "suspended"}


def test_unknown_service_is_reported_not_ignored():
    disruptions = transport_data.disruptions_from_services([
        {"name": "Funivia Fantasma", "status": "suspended"}
    ])
    assert disruptions["unmatched_services"] == ["Funivia Fantasma"]


def test_route_is_planned_and_marked_not_realtime():
    plan = route_data.plan_routes("Piazza Garibaldi", "Castel dell'Ovo")
    assert plan["options"]
    best = plan["options"][0]
    assert best["realtime_verified"] is False
    assert best["total_minutes_estimate"] > 0
    assert best["warnings"]


def test_suspended_segment_is_not_used_by_any_option():
    disruptions = transport_data.disruptions_from_services([{
        "name": "Metro Linea 1",
        "status": "suspended",
        "between": ["Università", "Municipio"]
    }])
    plan = route_data.plan_routes(
        "Piazza Garibaldi", "Castel dell'Ovo", disruptions=disruptions
    )
    assert plan["excluded_lines"]
    for option in plan["options"]:
        for step in option["steps"]:
            if step["type"] == "ride" and step["line_id"] == "L1":
                # Su Linea 1 non si può attraversare Università → Municipio.
                assert {step["from"], step["to"]} != {"Università", "Municipio"}
                assert not (step["from"] == "Garibaldi" and step["to"] == "Municipio")


def test_all_lines_down_gives_no_route_instead_of_inventing_one():
    disruptions = transport_data.disruptions_from_services([
        {"name": "Metro Linea 1", "status": "suspended"},
        {"name": "Metro Linea 2", "status": "suspended"},
        {"name": "Bus C56", "status": "suspended"},
    ])
    plan = route_data.plan_routes(
        "Piazza Garibaldi", "Mergellina", disruptions=disruptions
    )
    for option in plan["options"]:
        assert all(step["type"] != "ride" for step in option["steps"])


def test_unresolved_place_returns_no_options():
    plan = route_data.plan_routes("Posillipo", "Piazza Garibaldi")
    assert plan["unresolved"] == ["Posillipo"]
    assert plan["options"] == []


def _write_csv(path, header, rows):
    path.write_text(
        header + "\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )


@pytest.fixture
def tiny_gtfs(tmp_path):
    """Un feed GTFS minimo: una linea con tre fermate."""
    _write_csv(tmp_path / "stops.txt", "stop_id,stop_name,stop_lat,stop_lon", [
        "A,Alfa,40.8500,14.2500",
        "B,Beta,40.8450,14.2550",
        "C,Gamma,40.8400,14.2600",
        "Z,Mai usata,40.9000,14.3000",
    ])
    _write_csv(tmp_path / "routes.txt", "route_id,agency_id,route_short_name,route_long_name,route_type", [
        "R1,TEST,R1,Linea di prova,3",
    ])
    _write_csv(tmp_path / "trips.txt", "route_id,service_id,trip_id,direction_id", [
        "R1,S,T1,0", "R1,S,T2,0",
    ])
    _write_csv(tmp_path / "stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence", [
        "T1,08:00:00,08:00:00,A,1", "T1,08:04:00,08:04:00,B,2", "T1,08:09:00,08:09:00,C,3",
        "T2,09:00:00,09:00:00,A,1", "T2,09:04:00,09:04:00,B,2", "T2,09:09:00,09:09:00,C,3",
    ])
    return tmp_path


def test_gtfs_loader_builds_lines_and_hop_times(tiny_gtfs):
    network = transport_data.load_gtfs_directory(tiny_gtfs)
    assert network["lines"]["R1"]["stops"] == ["A", "B", "C"]
    assert network["lines"]["R1"]["hop_minutes"] == [4, 5]
    # Le fermate mai usate non entrano nella rete.
    assert "Z" not in network["stops"]
    assert network["meta"]["realtime"] is False
    assert network["meta"]["data_type"] == "static_gtfs"


def test_gtfs_network_is_used_when_env_var_is_set(tiny_gtfs, monkeypatch):
    monkeypatch.setenv("NEURAPOLIS_GTFS_DIR", str(tiny_gtfs))
    network = transport_data.get_network(force_reload=True)
    assert "R1" in network["lines"]
    plan = route_data.plan_routes("Alfa", "Gamma", network=network)
    assert plan["options"]
    assert plan["options"][0]["lines"] == ["Linea di prova"]
