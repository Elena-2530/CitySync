
import os
import sqlite3
import json

from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Percorso predefinito del database reale.
DEFAULT_DB_PATH = DATA_DIR / "social_reports.db"

# Se è impostata NEURAPOLIS_DB_PATH, viene utilizzato
# il database indicato al suo interno.
DB_PATH = Path(
    os.environ.get("NEURAPOLIS_DB_PATH", str(DEFAULT_DB_PATH))
).expanduser()


def get_connection():
    """
    Restituisce una connessione al database selezionato.

    Normalmente utilizza social_reports.db.
    Durante i test può utilizzare un database separato
    impostando la variabile NEURAPOLIS_DB_PATH.
    """

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db():
    connection = get_connection()

    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                description TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                priority TEXT DEFAULT 'pending',
                verification_status TEXT DEFAULT 'unverified',
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS social_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_uri TEXT NOT NULL UNIQUE,
                incident_id INTEGER,
                source TEXT NOT NULL,
                author_did TEXT,
                text TEXT NOT NULL,
                categories TEXT,
                locations TEXT,
                published_at TEXT,
                received_at TEXT NOT NULL,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
            );

            CREATE TABLE IF NOT EXISTS incident_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                source_name TEXT,
                source_url TEXT,
                evidence_description TEXT,
                evidence_type TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
            );

            CREATE TABLE IF NOT EXISTS official_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_number TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT,
                valid_from TEXT,
                valid_until TEXT,
                raw_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(alert_number, source_name)
            );

            CREATE TABLE IF NOT EXISTS official_alert_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                zone_number INTEGER NOT NULL,
                territory TEXT,
                alert_level TEXT,
                risks TEXT,
                FOREIGN KEY (alert_id)
                    REFERENCES official_alerts(id)
                    ON DELETE CASCADE,
                UNIQUE(alert_id, zone_number)
            );
        """)

        # Migrazioni per database creati con versioni precedenti.

        incident_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(incidents)"
            )
        }

        if "latitude" not in incident_columns:
            connection.execute(
                "ALTER TABLE incidents ADD COLUMN latitude REAL"
            )

        if "longitude" not in incident_columns:
            connection.execute(
                "ALTER TABLE incidents ADD COLUMN longitude REAL"
            )

        report_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(social_reports)"
            )
        }

        if "author_did" not in report_columns:
            connection.execute(
                "ALTER TABLE social_reports ADD COLUMN author_did TEXT"
            )

        # Indice per le ricerche degli incidenti aperti.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status)
        """)

        # Indice per recuperare le segnalazioni di un incidente.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_social_reports_incident
            ON social_reports(incident_id)
        """)

        connection.commit()

    finally:
        connection.close()


def save_report(
    post_uri,
    text,
    categories,
    locations,
    author_did=None,
    published_at=None
):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO social_reports (
                post_uri,
                source,
                author_did,
                text,
                categories,
                locations,
                published_at,
                received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_uri,
            "bluesky",
            author_did,
            text,
            json.dumps(categories, ensure_ascii=False),
            json.dumps(locations, ensure_ascii=False),
            published_at,
            datetime.now(timezone.utc).isoformat()
        ))

        connection.commit()

        return cursor.rowcount == 1

    finally:
        connection.close()
