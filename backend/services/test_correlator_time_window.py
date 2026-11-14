
import tempfile
from pathlib import Path

from services import database
from services.database import get_connection
from services.incident_correlator import correlate_report


def prepare_test_database():
    """Crea un database temporaneo per il test."""

    temporary_dir = tempfile.TemporaryDirectory()

    database.DB_PATH = Path(temporary_dir.name) / "test_time.db"
    database.init_db()

    return temporary_dir


def create_report(uri, author, published_at):
    """Crea una segnalazione di prova."""

    return correlate_report(
        post_uri=uri,
        text=(
            "Allagamento a Bagnoli, acqua sulla strada "
            "e traffico rallentato."
        ),
        categories=["environment"],
        locations=["napoli", "bagnoli"],
        author_did=author,
        published_at=published_at
    )


def test_moving_time_window():
    print("\nTEST - Finestra temporale mobile")

    # Primo post: crea l'incidente alle 10:00.
    incident_1 = create_report(
        "test://time/1",
        "author-1",
        "2026-11-14T10:00:00+00:00"
    )

    # Secondo post: 50 minuti dopo.
    incident_2 = create_report(
        "test://time/2",
        "author-2",
        "2026-11-14T10:50:00+00:00"
    )

    assert incident_1 == incident_2
    print("OK: il secondo post è stato associato.")

    # Terzo post: 50 minuti dopo il secondo.
    incident_3 = create_report(
        "test://time/3",
        "author-3",
        "2026-11-14T11:40:00+00:00"
    )

    assert incident_1 == incident_3
    print("OK: il terzo post è stato associato.")

    # Quarto post: 61 minuti dopo il terzo.
    incident_4 = create_report(
        "test://time/4",
        "author-4",
        "2026-11-14T12:41:00+00:00"
    )

    assert incident_4 != incident_1
    print("OK: il quarto post ha creato un nuovo incidente.")

    # Verifichiamo il numero effettivo di incidenti e segnalazioni.
    connection = get_connection()

    try:
        total_incidents = connection.execute(
            "SELECT COUNT(*) FROM incidents"
        ).fetchone()[0]

        first_incident_reports = connection.execute(
            """
            SELECT COUNT(*)
            FROM social_reports
            WHERE incident_id = ?
            """,
            (incident_1,)
        ).fetchone()[0]

        fourth_incident_reports = connection.execute(
            """
            SELECT COUNT(*)
            FROM social_reports
            WHERE incident_id = ?
            """,
            (incident_4,)
        ).fetchone()[0]

    finally:
        connection.close()

    assert total_incidents == 2
    assert first_incident_reports == 3
    assert fourth_incident_reports == 1

    print(f"Incidenti creati: {total_incidents}")
    print(f"Segnalazioni primo incidente: {first_incident_reports}")
    print(f"Segnalazioni secondo incidente: {fourth_incident_reports}")

    print("\nTEST SUPERATO!")


if __name__ == "__main__":
    temporary_dir = prepare_test_database()

    try:
        test_moving_time_window()

    except AssertionError as error:
        print(f"\nTEST FALLITO: {error}")

    finally:
        temporary_dir.cleanup()
