
from datetime import datetime, timezone
from unittest.mock import patch

from services.database import get_connection, init_db
from services.incident_correlator import (
    calculate_geographic_distance,
    correlate_report,
    MAX_CORRELATION_DISTANCE_KM
)


# ============================================================
# TEST 1 - FORMULA DI HAVERSINE
# ============================================================

print("\nTEST 1 - Calcolo della distanza geografica")

same_point_distance = calculate_geographic_distance(
    40.8173159, 14.167038,
    40.8173159, 14.167038
)

if same_point_distance is None or same_point_distance > 0.001:
    raise AssertionError("La distanza tra punti identici deve essere zero.")

print("OK: distanza tra punti identici:", same_point_distance, "km")


near_distance = calculate_geographic_distance(
    40.8173159, 14.167038,
    40.8180, 14.1600
)

if near_distance is None or near_distance >= MAX_CORRELATION_DISTANCE_KM:
    raise AssertionError("Le coordinate di prova dovrebbero essere vicine.")

print("OK: distanza tra punti vicini:", round(near_distance, 3), "km")


far_distance = calculate_geographic_distance(
    40.8173159, 14.167038,
    40.8860, 14.2900
)

if far_distance is None or far_distance <= MAX_CORRELATION_DISTANCE_KM:
    raise AssertionError("Le coordinate di prova dovrebbero essere lontane.")

print("OK: distanza tra punti lontani:", round(far_distance, 3), "km")


# ============================================================
# TEST 2 - CORRELAZIONE TRA LOCALITA' VICINE
# ============================================================

print("\nTEST 2 - Segnalazioni in località vicine")

init_db()

test_coordinates = {
    "bagnoli": {
        "latitude": 40.8173159,
        "longitude": 14.167038
    },
    "agnano": {
        "latitude": 40.8180,
        "longitude": 14.1600
    },
    "capodichino": {
        "latitude": 40.8860,
        "longitude": 14.2900
    }
}


def fake_geocoding(location):
    return test_coordinates.get(location.casefold())


published_at = datetime.now(timezone.utc).isoformat()

categories_environment = [
    {
        "category": "environment",
        "matched_keywords": ["allagamento"]
    }
]

common_text = "Allagamento della strada dopo il temporale a"


with patch(
    "services.incident_correlator.get_location_coordinates",
    side_effect=fake_geocoding
):

    first_incident = correlate_report(
        post_uri="at://geo-test/first",
        text=f"{common_text} Bagnoli.",
        categories=categories_environment,
        locations=["bagnoli"],
        author_did="geo-author-1",
        published_at=published_at
    )

    second_incident = correlate_report(
        post_uri="at://geo-test/second",
        text=f"{common_text} Agnano.",
        categories=categories_environment,
        locations=["agnano"],
        author_did="geo-author-2",
        published_at=published_at
    )

    if first_incident != second_incident:
        raise AssertionError(
            "Le segnalazioni vicine avrebbero dovuto essere raggruppate."
        )

    print("OK: Bagnoli e Agnano sono state associate allo stesso incidente.")


# ============================================================
# TEST 3 - LOCALITA' LONTANE
# ============================================================

print("\nTEST 3 - Segnalazioni in località lontane")

with patch(
    "services.incident_correlator.get_location_coordinates",
    side_effect=fake_geocoding
):

    third_incident = correlate_report(
        post_uri="at://geo-test/third",
        text=f"{common_text} Capodichino.",
        categories=categories_environment,
        locations=["capodichino"],
        author_did="geo-author-3",
        published_at=published_at
    )

    if third_incident == first_incident:
        raise AssertionError(
            "Le segnalazioni lontane non devono essere raggruppate."
        )

    print("OK: Capodichino è rimasta separata da Bagnoli.")


# ============================================================
# TEST 4 - CATEGORIE DIFFERENTI
# ============================================================

print("\nTEST 4 - Eventi di categorie differenti")

categories_mobility = [
    {
        "category": "mobility",
        "matched_keywords": ["traffico"]
    }
]

with patch(
    "services.incident_correlator.get_location_coordinates",
    side_effect=fake_geocoding
):

    fourth_incident = correlate_report(
        post_uri="at://geo-test/fourth",
        text=f"{common_text} Bagnoli.",
        categories=categories_mobility,
        locations=["bagnoli"],
        author_did="geo-author-4",
        published_at=published_at
    )

    if fourth_incident == first_incident:
        raise AssertionError(
            "Eventi di categorie differenti non devono essere uniti."
        )

    print("OK: le categorie differenti sono rimaste separate.")


# ============================================================
# VERIFICA FINALE DATABASE
# ============================================================

connection = get_connection()

try:
    incidents = connection.execute(
        """
        SELECT id, event_type, location, latitude, longitude
        FROM incidents
        ORDER BY id
        """
    ).fetchall()

    reports = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM social_reports
        """
    ).fetchone()["total"]

    print("\n----- RISULTATO FINALE -----")

    for incident in incidents:
        print(dict(incident))

    print("Segnalazioni salvate:", reports)
    print("Incidenti creati:", len(incidents))

    if len(incidents) != 3 or reports != 4:
        raise AssertionError(
            "Il numero di incidenti o segnalazioni non è quello atteso."
        )

finally:
    connection.close()


print("\nTUTTI I TEST GEOGRAFICI SONO SUPERATI!")
