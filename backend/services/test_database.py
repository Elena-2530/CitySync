
from services.database import init_db, save_report, DB_PATH

init_db()

print("Database inizializzato:", DB_PATH)

saved = save_report(
    post_uri="at://test123/app.bsky.feed.post/test001",
    text="Traffico intenso a Fuorigrotta.",
    categories=[
        {
            "category": "mobility",
            "matched_keywords": ["traffico"]
        }
    ],
    locations=["fuorigrotta"],
    published_at="2026-11-14T15:00:00Z"
)

print(
    "Segnalazione salvata!"
    if saved
    else "Segnalazione già presente."
)
