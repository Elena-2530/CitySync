
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "social_reports.db"


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

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
        """)
        # Aggiunge author_did anche ai database già esistenti
        columns = [
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(social_reports)"
            )
        ]

        if "author_did" not in columns:
            connection.execute(
                "ALTER TABLE social_reports ADD COLUMN author_did TEXT"
            )
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
    import json

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
