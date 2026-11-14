
import json
import sqlite3

from datetime import datetime, timedelta, timezone

from services.database import get_connection


CORRELATION_WINDOW_MINUTES = 60


def parse_datetime(value):
    """Converte una data ISO in un datetime con timezone."""

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except ValueError:
        return None


def find_matching_incident(
    connection,
    categories,
    locations,
    published_at
):
    """Cerca un incidente candidato compatibile."""

    post_time = parse_datetime(published_at)

    if not post_time or not categories or not locations:
        return None

    category_names = {
        item["category"]
        for item in categories
    }

    location_names = {
        location.casefold()
        for location in locations
    }

    rows = connection.execute("""
        SELECT *
        FROM incidents
        WHERE status = 'open'
        ORDER BY created_at DESC
    """).fetchall()

    for incident in rows:

        incident_time = parse_datetime(
            incident["created_at"]
        )

        if not incident_time:
            continue

        time_difference = abs(
            post_time - incident_time
        )

        if time_difference > timedelta(
            minutes=CORRELATION_WINDOW_MINUTES
        ):
            continue

        incident_location = (
            incident["location"] or ""
        ).casefold()

        if incident_location not in location_names:
            continue

        if incident["event_type"] not in category_names:
            continue

        return incident["id"]

    return None


def correlate_report(
    post_uri,
    text,
    categories,
    locations,
    author_did,
    published_at
):
    """Collega una segnalazione a un incidente candidato."""

    connection = get_connection()

    try:
        # Controlla se il post è già stato salvato
        existing = connection.execute("""
            SELECT id, incident_id
            FROM social_reports
            WHERE post_uri = ?
        """, (post_uri,)).fetchone()

        if existing:
            return existing["incident_id"]

        incident_id = find_matching_incident(
            connection,
            categories,
            locations,
            published_at
        )

        now = datetime.now(timezone.utc).isoformat()

# L'incidente prende come riferimento l'orario
# di pubblicazione della prima segnalazione
        event_time = parse_datetime(published_at)

        incident_created_at = (
            event_time.isoformat()
            if event_time
            else now
)
        # Se non esiste un incidente compatibile, ne crea uno
        if incident_id is None:

            category = categories[0]["category"]
            location = locations[0]

            cursor = connection.execute("""
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
            """, (
                category,
                text,
                location,
                "pending",
                "unverified",
                "open",
                incident_created_at,
                now
            ))

            incident_id = cursor.lastrowid

        # Salva il post e lo associa all'incidente
        connection.execute("""
            INSERT INTO social_reports (
                post_uri,
                incident_id,
                source,
                author_did,
                text,
                categories,
                locations,
                published_at,
                received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_uri,
            incident_id,
            "bluesky",
            author_did,
            text,
            json.dumps(categories, ensure_ascii=False),
            json.dumps(locations, ensure_ascii=False),
            published_at,
            now
        ))

        connection.execute("""
            UPDATE incidents
            SET updated_at = ?
            WHERE id = ?
        """, (now, incident_id))

        connection.commit()

        return incident_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
