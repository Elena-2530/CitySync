
import tempfile
from pathlib import Path

from services import database
from services.geocoding import geocode_location


def test_geocoding():

    temporary_dir = tempfile.TemporaryDirectory()

    database.DB_PATH = Path(temporary_dir.name) / "test_geocoding.db"

    calls = []

    def fake_search(query):
        calls.append(query)

        return [{
            "lat": "40.8167",
            "lon": "14.1667",
            "display_name": "Bagnoli, Napoli, Campania, Italia",
            "osm_type": "relation",
            "osm_id": 123456
        }]

    try:
        print("\nTEST 1 - Prima geocodifica")

        result_1 = geocode_location(
            "Bagnoli",
            search_function=fake_search
        )

        assert result_1 is not None
        assert result_1["latitude"] == 40.8167
        assert result_1["longitude"] == 14.1667
        assert result_1["source"] == "nominatim"

        print("OK: coordinate recuperate e salvate.")

        print("\nTEST 2 - Recupero dalla cache")

        result_2 = geocode_location(
            "Bagnoli",
            search_function=fake_search
        )

        assert result_2 is not None
        assert result_2["source"] == "cache"
        assert len(calls) == 1

        print("OK: seconda ricerca recuperata dalla cache.")
        print("OK: nessuna nuova richiesta al servizio.")

        print("\nTEST 3 - Località non trovata")

        def fake_not_found(query):
            return []

        result_3 = geocode_location(
            "Localita inesistente",
            search_function=fake_not_found
        )

        assert result_3 is None

        print("OK: gestita correttamente una località non trovata.")

        print("\nTUTTI I TEST SONO SUPERATI!")

    finally:
        temporary_dir.cleanup()


if __name__ == "__main__":
    test_geocoding()
