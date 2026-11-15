
import json
import logging
import ssl
import time
import unicodedata

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

from services.database import get_connection


logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

USER_AGENT = "NEURAPOLIS/0.1"

_last_request_time = 0.0


def normalize_location(location):
    """Normalizza il nome di una località."""

    if not location:
        return ""

    text = unicodedata.normalize("NFKD", location)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    return " ".join(text.lower().strip().split())



def build_search_query(location):
    """Prepara una ricerca geografica senza imporre Napoli."""

    location = location.strip()

    if "italia" not in normalize_location(location):
        return f"{location}, Italia"

    return location


def init_geocoding_table():
    """Crea la tabella che conserva le coordinate già trovate."""

    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS location_cache (
                normalized_name TEXT PRIMARY KEY,
                display_name TEXT,
                latitude REAL,
                longitude REAL,
                osm_type TEXT,
                osm_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


def get_cached_location(normalized_name):
    """Recupera una località dalla cache."""

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM location_cache
            WHERE normalized_name = ?
            """,
            (normalized_name,)
        ).fetchone()

        if row is None:
            return None

        if row["status"] != "found":
            return None

        return {
            "name": normalized_name,
            "display_name": row["display_name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "osm_type": row["osm_type"],
            "osm_id": row["osm_id"],
            "source": "cache"
        }

    finally:
        connection.close()


def respect_nominatim_rate_limit():
    """Rispetta il limite di una richiesta al secondo."""

    global _last_request_time

    elapsed = time.monotonic() - _last_request_time

    if elapsed < 1:
        time.sleep(1 - elapsed)

    _last_request_time = time.monotonic()



def search_nominatim(query, limit=5):
    """Interroga OpenStreetMap Nominatim."""

    respect_nominatim_rate_limit()

    parameters = urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": limit,
        "addressdetails": 1
    })

    url = f"{NOMINATIM_URL}?{parameters}"

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "it"
        }
    )

    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    with urlopen(
        request,
        context=ssl_context,
        timeout=20
    ) as response:

        return json.loads(response.read().decode("utf-8"))


def save_location(normalized_name, result):
    """Salva il risultato della geocodifica nella cache."""

    now = datetime.now(timezone.utc).isoformat()

    if result:
        latitude = float(result["lat"])
        longitude = float(result["lon"])

        display_name = result.get("display_name")
        osm_type = result.get("osm_type")
        osm_id = str(result.get("osm_id", ""))

        status = "found"

    else:
        latitude = None
        longitude = None
        display_name = None
        osm_type = None
        osm_id = None

        status = "not_found"

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO location_cache (
                normalized_name,
                display_name,
                latitude,
                longitude,
                osm_type,
                osm_id,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_name)
            DO UPDATE SET
                display_name = excluded.display_name,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                osm_type = excluded.osm_type,
                osm_id = excluded.osm_id,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                normalized_name,
                display_name,
                latitude,
                longitude,
                osm_type,
                osm_id,
                status,
                now,
                now
            )
        )

        connection.commit()

    finally:
        connection.close()


def geocode_location(location, search_function=None):
    """
    Cerca le coordinate di una località.

    Prima controlla la cache.
    Se non trova il dato, interroga Nominatim.
    """

    init_geocoding_table()

    normalized_name = normalize_location(location)

    if not normalized_name:
        return None

    cached = get_cached_location(normalized_name)

    if cached is not None:
        logger.info("Località recuperata dalla cache: %s", location)
        return cached

    # Verifica se esiste già una ricerca senza risultati.
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT status
            FROM location_cache
            WHERE normalized_name = ?
            """,
            (normalized_name,)
        ).fetchone()

        if row is not None and row["status"] == "not_found":
            logger.info("Località già cercata senza risultati: %s", location)
            return None

    finally:
        connection.close()

    query = build_search_query(location)

    search = search_function or search_nominatim

    try:
        results = search(query)

    except Exception:
        logger.exception(
            "Errore durante la geocodifica di %s",
            location
        )
        return None

    if not results:
        save_location(normalized_name, None)
        logger.warning("Nessuna coordinata trovata per: %s", location)
        return None

    result = results[0]

    coordinates = {
        "lat": result["lat"],
        "lon": result["lon"],
        "display_name": result.get("display_name"),
        "osm_type": result.get("osm_type"),
        "osm_id": result.get("osm_id")
    }

    save_location(normalized_name, coordinates)

    logger.info(
        "Località geocodificata: %s -> %s, %s",
        location,
        coordinates["lat"],
        coordinates["lon"]
    )

    return {
        "name": normalized_name,
        "display_name": coordinates["display_name"],
        "latitude": float(coordinates["lat"]),
        "longitude": float(coordinates["lon"]),
        "osm_type": coordinates["osm_type"],
        "osm_id": str(coordinates["osm_id"]),
        "source": "nominatim"
    }


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    location = input("Inserisci una località di Napoli: ")

    result = geocode_location(location)

    if result:
        print("\nLOCALITÀ TROVATA")
        print("Nome:", result["name"])
        print("Descrizione:", result["display_name"])
        print("Latitudine:", result["latitude"])
        print("Longitudine:", result["longitude"])
        print("Fonte:", result["source"])

    else:
        print("\nLocalità non trovata o servizio momentaneamente non disponibile.")

