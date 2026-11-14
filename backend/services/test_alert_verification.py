
from datetime import datetime
from zoneinfo import ZoneInfo

from services.database import get_connection
from agents.verification_agent import attach_official_alert_context


def main():
    connection = get_connection()

    try:
        # Data compresa nella validità dell'allerta 094/2026.
        incident_date = datetime(
            2026, 11, 15, 10, 0,
            tzinfo=ZoneInfo("Europe/Rome")
        ).isoformat()

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
                "Segnalazione temporanea di allagamento stradale a Fuorigrotta dopo le piogge intense.",
                "Fuorigrotta",
                "pending",
                "unverified",
                "open",
                incident_date,
                incident_date
            )
        )

        incident_id = cursor.lastrowid
        connection.commit()

        print("Incidente temporaneo creato:", incident_id)

    finally:
        connection.close()

    result = attach_official_alert_context(incident_id)

    print("\nRISULTATO COLLEGAMENTO:")
    print(result)

    assert result["total_matches"] >= 1, (
        "Nessuna allerta compatibile trovata!"
    )

    print("\nTEST COLLEGAMENTO ALLERTE SUPERATO!")


if __name__ == "__main__":
    main()
