"""Controlli sull'integrità dei dati dei luoghi e sulle regole di onestà."""

from agents.tourism.tourism_data import places

REQUIRED = ["id", "name", "aliases", "categories", "address", "lat", "lon", "indoor", "description", "hours"]


def test_every_place_has_required_fields_and_unique_id():
    data = places.all_places()
    assert len(data) >= 10
    ids = [p["id"] for p in data]
    assert len(ids) == len(set(ids))
    for place in data:
        for field in REQUIRED:
            assert field in place, (place.get("id"), field)


def test_coordinates_are_in_naples():
    for place in places.all_places():
        assert 40.80 < place["lat"] < 40.90, place["id"]
        assert 14.15 < place["lon"] < 14.30, place["id"]


def test_hours_always_carry_their_source():
    """Un orario senza fonte non deve esistere: è così che si inventano i dati."""
    for place in places.all_places():
        hours = place["hours"]
        if hours["status"] in ("official", "secondary"):
            source = hours["source"]
            assert source and source["url"].startswith("http"), place["id"]
            assert source["type"] == hours["status"], place["id"]
            assert "as_of" in source and "retrieved" in source, place["id"]
            assert set(hours["weekly"]) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}, place["id"]
        else:
            assert hours["status"] in ("open_air", "unknown"), place["id"]
            assert not hours["weekly"], place["id"]


def test_time_ranges_are_well_formed():
    for place in places.all_places():
        weekly = place["hours"].get("weekly") or {}
        for ranges in weekly.values():
            for start, end in ranges:
                assert start < end, place["id"]


def test_tickets_only_with_source():
    for place in places.all_places():
        tickets = place.get("tickets")
        if tickets:
            assert tickets["source"]["url"].startswith("http"), place["id"]


def test_find_place_by_alias_and_longest_match():
    assert places.find_place("Quando apre il Maschio Angioino?")["id"] == "castel_nuovo"
    assert places.find_place("storia del Cristo velato")["id"] == "cappella_sansevero"
    assert places.find_place("Castel dell'Ovo")["id"] == "castel_dell_ovo"
    assert places.find_place("Colosseo") is None
    assert places.find_place("") is None


def test_nearby_is_sorted_and_respects_radius():
    center = places.find_area("Municipio")
    found = places.nearby(center["lat"], center["lon"], 500)
    distances = [item["distance_m"] for item in found]
    assert distances == sorted(distances)
    assert all(d <= 500 for d in distances)
    assert found[0]["place"]["id"] == "castel_nuovo"
