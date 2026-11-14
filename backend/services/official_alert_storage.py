
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from services.database import get_connection, init_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def save_official_alert(alert_data, source_name, source_url=None):

    alert_number = alert_data.get("alert_number")
    zones = alert_data.get("zones", [])

    if not alert_number:
        raise ValueError("Numero dell'avviso mancante.")

    if not isinstance(zones, list):
        raise ValueError("Il campo zones deve essere una lista.")

    now = datetime.now(timezone.utc).isoformat()
    raw_json = json.dumps(alert_data, ensure_ascii=False)

    init_db()
    connection = get_connection()

    try:
        with connection:

            existing = connection.execute(
                """
                SELECT id
                FROM official_alerts
                WHERE alert_number = ? AND source_name = ?
                """,
                (alert_number, source_name)
            ).fetchone()

            if existing:
                alert_id = existing["id"]

                connection.execute(
                    """
                    UPDATE official_alerts
                    SET source_url = ?,
                        valid_from = ?,
                        valid_until = ?,
                        raw_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        source_url,
                        alert_data.get("valid_from"),
                        alert_data.get("valid_until"),
                        raw_json,
                        now,
                        alert_id
                    )
                )

                connection.execute(
                    """
                    DELETE FROM official_alert_zones
                    WHERE alert_id = ?
                    """,
                    (alert_id,)
                )

                logger.info("Avviso %s aggiornato.", alert_number)

            else:
                cursor = connection.execute(
                    """
                    INSERT INTO official_alerts (
                        alert_number,
                        source_name,
                        source_url,
                        valid_from,
                        valid_until,
                        raw_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert_number,
                        source_name,
                        source_url,
                        alert_data.get("valid_from"),
                        alert_data.get("valid_until"),
                        raw_json,
                        now,
                        now
                    )
                )

                alert_id = cursor.lastrowid

                logger.info("Nuovo avviso %s salvato.", alert_number)

            for zone in zones:
                connection.execute(
                    """
                    INSERT INTO official_alert_zones (
                        alert_id,
                        zone_number,
                        territory,
                        alert_level,
                        risks
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        alert_id,
                        zone["zone"],
                        zone.get("territory"),
                        zone.get("alert_level"),
                        json.dumps(
                            zone.get("risks", []),
                            ensure_ascii=False
                        )
                    )
                )

        return alert_id

    finally:
        connection.close()


def save_alert_from_json(json_path, source_name, source_url=None):

    path = Path(json_path)

    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")

    with path.open("r", encoding="utf-8") as file:
        alert_data = json.load(file)

    return save_official_alert(
        alert_data,
        source_name,
        source_url
    )


if __name__ == "__main__":

    BASE_DIR = Path(__file__).resolve().parent.parent

    JSON_PATH = BASE_DIR / "data" / "avviso_094_2026.json"

    alert_id = save_alert_from_json(
        json_path=JSON_PATH,
        source_name="Protezione Civile Regione Campania",
        source_url="https://portaleprotezionecivile.regione.campania.it/"
    )

    print(f"\nAvviso salvato. ID database: {alert_id}")
