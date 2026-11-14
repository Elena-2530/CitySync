
import tempfile
from pathlib import Path

from services import database
from services.incident_correlator import correlate_report
from services.database import get_connection


def prepare_test_database():
    """
    Usa un database temporaneo:
    i test non modificano social_reports.db.
    """
    temporary_dir = tempfile.TemporaryDirectory()

    database.DB_PATH = Path(temporary_dir.name) / "test_neurapolis.db"
    database.init_db()

    return temporary_dir


def count_reports(incident_id):
    connection = get_connection()

    try:
        return connection.execute(
            """
            SELECT COUNT(*)
            FROM social_reports
            WHERE incident_id = ?
            """,
            (incident_id,)
        ).fetchone()[0]
    finally:
        connection.close()


def test_related_reports_are_grouped():
    print("\nTEST 1 - Segnalazioni sullo stesso allagamento")

    first_id = correlate_report(
        post_uri="test://flood/1",
        text=(
            "Allagamento a Bagnoli, acqua sulla carreggiata "
            "e traffico rallentato."
        ),
        categories=["environment"],
        locations=["napoli", "bagnoli"],
        author_did="author-1",
        published_at="2026-11-14T12:00:00+00:00"
    )

    second_id = correlate_report(
        post_uri="test://flood/2",
        text=(
            "A Bagnoli acqua sulla strada dopo la pioggia, "
            "le auto procedono lentamente."
        ),
        categories=["environment"],
        locations=["napoli", "bagnoli"],
        author_did="author-2",
        published_at="2026-11-14T12:05:00+00:00"
    )

    assert first_id == second_id, (
        "ERRORE: le segnalazioni sullo stesso evento "
        "sono state separate."
    )

    print("OK: le due segnalazioni sono state raggruppate.")


def test_different_fires_are_separated():
    print("\nTEST 2 - Due incendi diversi nella stessa zona")

    first_id = correlate_report(
        post_uri="test://fire/1",
        text=(
            "Incendio in un capannone industriale a Bagnoli, "
            "fiamme visibili dal lungomare."
        ),
        categories=["environment"],
        locations=["napoli", "bagnoli"],
        author_did="author-3",
        published_at="2026-11-14T14:00:00+00:00"
    )

    second_id = correlate_report(
        post_uri="test://fire/2",
        text=(
            "Rogo di un'automobile parcheggiata a Bagnoli, "
            "intervento dei vigili del fuoco."
        ),
        categories=["environment"],
        locations=["napoli", "bagnoli"],
        author_did="author-4",
        published_at="2026-11-14T14:05:00+00:00"
    )

    assert first_id != second_id, (
        "ERRORE: due incendi potenzialmente distinti "
        "sono stati raggruppati."
    )

    print("OK: i due incendi sono rimasti separati.")


def test_duplicate_post_is_not_saved_twice():
    print("\nTEST 3 - Gestione dei post duplicati")

    post_uri = "test://duplicate/1"

    first_id = correlate_report(
        post_uri=post_uri,
        text="Traffico bloccato a Fuorigrotta per un incidente.",
        categories=["mobility"],
        locations=["napoli", "fuorigrotta"],
        author_did="author-5",
        published_at="2026-11-14T16:00:00+00:00"
    )

    second_id = correlate_report(
        post_uri=post_uri,
        text="Traffico bloccato a Fuorigrotta per un incidente.",
        categories=["mobility"],
        locations=["napoli", "fuorigrotta"],
        author_did="author-5",
        published_at="2026-11-14T16:00:00+00:00"
    )

    assert first_id == second_id, (
        "ERRORE: il post duplicato ha restituito un incidente diverso."
    )

    total = count_reports(first_id)

    assert total == 1, (
        f"ERRORE: il post è stato salvato {total} volte."
    )

    print("OK: il post duplicato non è stato salvato nuovamente.")


if __name__ == "__main__":
    temporary_dir = prepare_test_database()

    try:
        test_related_reports_are_grouped()
        test_different_fires_are_separated()
        test_duplicate_post_is_not_saved_twice()

        print("\nTUTTI I TEST SONO SUPERATI!")

    except AssertionError as error:
        print(f"\nTEST FALLITO: {error}")

    finally:
        temporary_dir.cleanup()
