
import ssl
import certifi
import asyncio
import json
import logging

from urllib.parse import urlencode

import websockets

from services.database import init_db
from services.incident_correlator import correlate_report
from services.social_filter import analyze_social_text


# --------------------------------------------------
# CONFIGURAZIONE LOG
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("neurapolis.social")


# --------------------------------------------------
# CONFIGURAZIONE BLUESKY JETSTREAM
# --------------------------------------------------

BASE_URL = "wss://jetstream2.us-east.bsky.network/subscribe"

PARAMETERS = {
    "wantedCollections": ["app.bsky.feed.post"],
}

URL = BASE_URL + "?" + urlencode(PARAMETERS, doseq=True)


# --------------------------------------------------
# ELABORAZIONE DEGLI EVENTI
# --------------------------------------------------

async def process_event(event: dict):
    """Elabora i post ricevuti da Bluesky."""

    # Controlliamo il tipo di evento
    if event.get("kind") != "commit":
        return

    commit = event.get("commit", {})

    # Consideriamo soltanto la creazione di nuovi post
    if commit.get("operation") != "create":
        return

    # Verifichiamo che si tratti di un post
    if commit.get("collection") != "app.bsky.feed.post":
        return

    # Estraiamo il contenuto del post
    record = commit.get("record", {})
    text = record.get("text", "")

    if not text:
        return

    # --------------------------------------------------
    # ANALISI DEL CONTENUTO
    # --------------------------------------------------

    result = analyze_social_text(text)

    # Mostriamo i primi 20 post analizzati
    if not hasattr(process_event, "_debug_count"):
        process_event._debug_count = 0

    if process_event._debug_count < 20:
        logger.info("POST ANALIZZATO: %s", text[:250])
        logger.info("RISULTATO FILTRO: %s", result)
        process_event._debug_count += 1

    # Se il post non è rilevante, lo ignoriamo
    if not result["relevant"]:
        return

    # --------------------------------------------------
    # ESTRAZIONE DEI DATI DEL POST
    # --------------------------------------------------

    post_uri = (
        f"at://{event.get('did')}/"
        f"app.bsky.feed.post/{commit.get('rkey')}"
    )

    author_did = event.get("did")
    published_at = record.get("createdAt")

    # --------------------------------------------------
    # CORRELAZIONE E SALVATAGGIO
    # --------------------------------------------------

    try:
        incident_id = correlate_report(
            post_uri=post_uri,
            text=text,
            categories=result["categories"],
            locations=result["locations"],
            author_did=author_did,
            published_at=published_at
        )

        logger.info("SEGNALAZIONE ELABORATA")
        logger.info("Incidente associato: %s", incident_id)
        logger.info("Testo: %s", text)
        logger.info("Categorie: %s", result["categories"])
        logger.info("Località: %s", result["locations"])
        logger.info("Autore: %s", author_did)
        logger.info("Pubblicazione: %s", published_at)
        logger.info("Post URI: %s", post_uri)

    except Exception:
        logger.exception(
            "Errore durante il salvataggio della segnalazione"
        )


# --------------------------------------------------
# AVVIO DEL COLLECTOR
# --------------------------------------------------

async def start_collector():
    """Mantiene attiva la connessione a Bluesky."""

    # Inizializzazione del database
    init_db()

    logger.info("Database inizializzato correttamente.")

    while True:

        try:
            logger.info("Connessione a Bluesky Jetstream...")
            logger.info("Endpoint: %s", BASE_URL)

            # Configurazione SSL
            ssl_context = ssl.create_default_context(
                cafile=certifi.where()
            )

            # Connessione WebSocket
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
                "Connessione interrotta. "
                "Nuovo tentativo tra 5 secondi."
            )

            await asyncio.sleep(5)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    try:
        asyncio.run(start_collector())

    except KeyboardInterrupt:
        logger.info("Arresto richiesto dall'utente.")
