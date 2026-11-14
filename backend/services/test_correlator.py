

from datetime import datetime, timezone
from uuid import uuid4

from services.incident_correlator import correlate_report
from services.database import get_connection


# Identificativo diverso a ogni esecuzione del test
test_id = uuid4().hex[:8]

# Cinque post simulati, pubblicati da cinque autori diversi
posts = [
    "Strada allagata a Fuorigrotta dopo il temporale.",
    "Diverse auto bloccate dall'acqua a Fuorigrotta.",
    "Allagamento vicino alla stazione di Fuorigrotta.",
    "Traffico fermo per l'acqua sulla strada a Fuorigrotta.",
    "Situazione critica per la pioggia a Fuorigrotta."
]

# Usiamo la stessa categoria e località per tutti i post
categories = [
    {
        "category": "environment",
        "matched_keywords": ["allagamento"]
    }
]

locations = [f"fuorigrotta_test_{test_id}"]

# Orario attuale in formato UTC
published_at = datetime.now(timezone.utc).isoformat()

incident_ids = []

for index, post_text in enumerate(posts):

    incident_id = correlate_report(
        post_uri=f"at://test-author-{test_id}/app.bsky.feed.post/post{index}",
        text=post_text,
        categories=categories,
        locations=locations,
        author_did=f"test-author-{index}-{test_id}",
        published_at=published_at
    )

    incident_ids.append(incident_id)

    print(
        f"Post {index + 1} associato all'incidente "
        f"{incident_id}"
    )


# Verifica il risultato direttamente nel database
connection = get_connection()

try:
    unique_incidents = set(incident_ids)

    report_count = connection.execute("""
        SELECT COUNT(*) AS total
        FROM social_reports
        WHERE incident_id = ?
    """, (incident_ids[0],)).fetchone()["total"]

    author_count = connection.execute("""
        SELECT COUNT(DISTINCT author_did) AS total
        FROM social_reports
        WHERE incident_id = ?
    """, (incident_ids[0],)).fetchone()["total"]

    print("\n----- RISULTATO DEL TEST -----")
    print("Incident ID:", incident_ids[0])
    print("Incidenti distinti:", len(unique_incidents))
    print("Segnalazioni associate:", report_count)
    print("Autori distinti:", author_count)

    if (
        len(unique_incidents) == 1
        and report_count == 5
        and author_count == 5
    ):
        print("\nTEST SUPERATO!")
    else:
        print("\nTEST NON SUPERATO.")

finally:
    connection.close()
