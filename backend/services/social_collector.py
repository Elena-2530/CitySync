
import ssl
import certifi
import asyncio
import json
import logging
from urllib.parse import urlencode

import websockets

from services.social_filter import analyze_social_text


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("neurapolis.social")


BASE_URL = "wss://jetstream2.us-east.bsky.network/subscribe"

PARAMETERS = {
    "wantedCollections": ["app.bsky.feed.post"],
}

URL = BASE_URL + "?" + urlencode(PARAMETERS, doseq=True)


async def process_event(event: dict):
    """Elabora un evento ricevuto dal flusso Bluesky."""

    if event.get("kind") != "commit":
        return

    commit = event.get("commit", {})

    # Consideriamo solo la pubblicazione di nuovi post.
    if commit.get("operation") != "create":
        return

    if commit.get("collection") != "app.bsky.feed.post":
        return

    record = commit.get("record", {})
    text = record.get("text", "")

    if not text:
        return

    result = analyze_social_text(text)

    if not result["relevant"]:
        return

    post_uri = (
        f"at://{event.get('did')}/"
        f"app.bsky.feed.post/{commit.get('rkey')}"
    )

    logger.info("=" * 60)
    logger.info("NUOVA SEGNALAZIONE POTENZIALMENTE RILEVANTE")
    logger.info("Testo: %s", text)
    logger.info("Categorie: %s", result["categories"])
    logger.info("Località: %s", result["locations"])
    logger.info("Post URI: %s", post_uri)
    logger.info("Motivazione: %s", result["reason"])
    logger.info("=" * 60)


async def start_collector():
    """Mantiene attiva la connessione e gestisce le riconnessioni."""

    while True:

        try:
            logger.info("Connessione a Bluesky Jetstream...")
            logger.info("Endpoint: %s", BASE_URL)

            ssl_context = ssl.create_default_context(cafile=certifi.where())

            async with websockets.connect(
    URL,
    ssl=ssl_context,
    ping_interval=20,
    ping_timeout=20,
    close_timeout=10,
    max_size=2**20
) as websocket:
                logger.info("CONNESSIONE BLUESKY ATTIVA")

                async for message in websocket:

                    try:
                        event = json.loads(message)
                        await process_event(event)

                    except json.JSONDecodeError:
                        logger.warning(
                            "Ricevuto messaggio JSON non valido"
                        )

                    except Exception:
                        logger.exception(
                            "Errore durante l'elaborazione dell'evento"
                        )

        except asyncio.CancelledError:
            logger.info("Collector arrestato.")
            raise

        except Exception:
            logger.exception(
                "Connessione interrotta. Nuovo tentativo tra 5 secondi."
            )

            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(start_collector())

    except KeyboardInterrupt:
        logger.info("Arresto richiesto dall'utente.")
