
import uuid
from datetime import datetime, timezone

from services.database import get_connection, init_db
from agents.verification_agent import add_evidence


def create_test_incident():
    """Crea un incidente temporaneo per il test."""

    unique_location = f"zona_test_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    # Inizializziamo le tabelle prima di inserire l'incidente.
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
                "Test di verifica incendio",
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


def main():
    incident_id = create_test_incident()

    print(f"\nIncidente di test creato: {incident_id}")

    # TEST 1: una fonte indipendente
    result = add_evidence(
        incident_id=incident_id,
        source_name="Test News",
        source_url="https://test-news.example/articolo",
        description="La fonte riporta un incendio nella zona indicata.",
        evidence_type="independent_confirmation"
    )

    print("\nDopo la prima evidenza:")
    print(result)

    assert result["verification_status"] == "partially_confirmed"

    # TEST 2: una seconda fonte indipendente
    result = add_evidence(
        incident_id=incident_id,
        source_name="Seconda Test News",
        source_url="https://second-test-news.example/articolo",
        description="Una seconda fonte riporta lo stesso incendio.",
        evidence_type="independent_confirmation"
    )

    print("\nDopo la seconda evidenza:")
    print(result)

    assert result["verification_status"] == "confirmed"

    # TEST 3: una contraddizione ufficiale
    result = add_evidence(
        incident_id=incident_id,
        source_name="Test Ente",
        source_url="https://ente.example/comunicazione",
        description="La fonte ufficiale dichiara che non risulta alcun incendio.",
        evidence_type="official_contradiction"
    )

    print("\nDopo la contraddizione:")
    print(result)

    assert result["verification_status"] == "conflicting"

    print("\nTEST VERIFICATION AGENT SUPERATO!")


if __name__ == "__main__":
    main()
