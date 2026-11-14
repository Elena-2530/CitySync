
import asyncio
import uuid

from datetime import datetime, timezone

from services.social_collector import process_event
from services.database import get_connection, init_db


async def test_pipeline():

    # Inizializziamo il database prima di utilizzare il collector.
    init_db()

    # Creiamo un evento Bluesky simulato.
    rkey = f"test-{uuid.uuid4().hex[:12]}"

    event = {
        "kind": "commit",
        "did": "did:plc:neurapolis-test",
        "commit": {
            "operation": "create",
            "collection": "app.bsky.feed.post",
            "rkey": rkey,
            "record": {
                "text": (
                    "Incendio segnalato a Bagnoli, Napoli. "
                    "Si vede del fumo nella zona."
                ),
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
        }
    }

    # Passiamo l'evento al collector.
    await process_event(event)

    # Recuperiamo il post dal database.
    post_uri = (
        f"at://did:plc:neurapolis-test/"
        f"app.bsky.feed.post/{rkey}"
    )

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                id,
                post_uri,
                incident_id,
                text,
                categories,
                locations
            FROM social_reports
            WHERE post_uri = ?
            """,
            (post_uri,)
        ).fetchone()

        if row is None:
            raise AssertionError(
                "La segnalazione non è stata salvata nel database."
            )

        if row["incident_id"] is None:
            raise AssertionError(
                "La segnalazione non è stata associata a un incidente."
            )

        incident = connection.execute(
            """
            SELECT id, event_type, location, latitude, longitude
            FROM incidents
            WHERE id = ?
            """,
            (row["incident_id"],)
        ).fetchone()

        if incident is None:
            raise AssertionError(
                "L'incidente associato non esiste nel database."
            )

        print("\nTEST PIPELINE SUPERATO!")
        print("ID segnalazione:", row["id"])
        print("ID incidente:", row["incident_id"])
        print("Testo:", row["text"])
        print("Categorie:", row["categories"])
        print("Località:", row["locations"])
        print("Coordinate:", incident["latitude"], incident["longitude"])

    finally:
        connection.close()


if __name__ == "__main__":
    asyncio.run(test_pipeline())