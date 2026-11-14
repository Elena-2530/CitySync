
import uuid
from datetime import datetime, timezone

from services.database import get_connection, init_db
from agents.verification_agent import add_evidence


def create_test_incident(description):
    """Crea un incidente temporaneo per il test."""

    unique_location = f"zona_test_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    init_db()

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO incidents (
                event_type,
                description,
                location,
                priority,
                verification_status,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "environment",
                description,
                unique_location,
                "pending",
                "unverified",
                "open",
                now,
                now
            )
        )

        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


def test_verification_classification():
    print("\n=== TEST VERIFICATION AGENT ===")

    # TEST 1: una fonte indipendente
    incident_id = create_test_incident(
        "Test conferma parziale"
    )

    result = add_evidence(
        incident_id,
        "Test News",
        "https://test-news.example/articolo",
        "La fonte riporta un incendio.",
        "independent_confirmation"
    )

    assert result["verification_status"] == "partially_confirmed"
    print("TEST 1 SUPERATO: una fonte indipendente")

    # TEST 2: una seconda fonte indipendente
    result = add_evidence(
        incident_id,
        "Seconda Test News",
        "https://second-test-news.example/articolo",
        "Una seconda fonte riporta lo stesso incendio.",
        "independent_confirmation"
    )

    assert result["verification_status"] == "confirmed"
    print("TEST 2 SUPERATO: due fonti indipendenti")

    # TEST 3: una contraddizione ufficiale insieme alle conferme
    result = add_evidence(
        incident_id,
        "Test Ente",
        "https://ente.example/comunicazione",
        "La fonte ufficiale dichiara che non risulta alcun incendio.",
        "official_contradiction"
    )

    assert result["verification_status"] == "conflicting"
    print("TEST 3 SUPERATO: conferme e contraddizione")

    # TEST 4: una sola contraddizione indipendente
    incident_id = create_test_incident(
        "Test contestazione indipendente"
    )

    result = add_evidence(
        incident_id,
        "Fonte indipendente",
        "https://fonte.example/articolo",
        "La fonte sostiene che l'incidente non sia avvenuto.",
        "independent_contradiction"
    )

    assert result["verification_status"] == "contested"
    print("TEST 4 SUPERATO: contestazione indipendente")

    # TEST 5: una sola contraddizione ufficiale
    incident_id = create_test_incident(
        "Test contraddizione ufficiale"
    )

    result = add_evidence(
        incident_id,
        "Ente ufficiale",
        "https://ente-ufficiale.example/comunicato",
        "L'ente dichiara ufficialmente che l'evento non è avvenuto.",
        "official_contradiction"
    )

    assert result["verification_status"] == "contradicted"
    print("TEST 5 SUPERATO: contraddizione ufficiale")

    # TEST 6: due articoli dello stesso dominio
    incident_id = create_test_incident(
        "Test deduplicazione fonti"
    )

    add_evidence(
        incident_id,
        "News",
        "https://news.example/articolo-1",
        "Prima notizia sull'incidente.",
        "independent_confirmation"
    )

    result = add_evidence(
        incident_id,
        "News",
        "https://www.news.example/articolo-2",
        "Seconda notizia sull'incidente.",
        "independent_confirmation"
    )

    assert result["independent_sources"] == 1
    assert result["verification_status"] == "partially_confirmed"
    print("TEST 6 SUPERATO: deduplicazione per dominio")

    # TEST 7: il contesto non conferma l'incidente
    incident_id = create_test_incident(
        "Test evidenza contestuale"
    )

    result = add_evidence(
        incident_id,
        "Protezione Civile",
        "https://protezione-civile.example/allerta",
        "Allerta meteo presente nella zona.",
        "context"
    )

    assert result["verification_status"] == "unverified"
    print("TEST 7 SUPERATO: il contesto non conferma l'evento")

    print("\nTUTTI I TEST VERIFICATION AGENT SUPERATI!")


if __name__ == "__main__":
    test_verification_classification()
