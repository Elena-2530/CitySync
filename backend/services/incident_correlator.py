
import json
import re
import unicodedata
import logging
import math

from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone

from services.database import get_connection
from services.geocoding import geocode_location


# ============================================================
# CONFIGURAZIONE
# ============================================================

CORRELATION_WINDOW_MINUTES = 60
MIN_TEXT_SIMILARITY = 0.20

# Distanza massima per considerare due località compatibili.
# Le coordinate possono rappresentare centroidi di quartiere.
MAX_CORRELATION_DISTANCE_KM = 1.5

# Pesi del punteggio complessivo.
TEXT_WEIGHT = 0.55
TIME_WEIGHT = 0.25
GEOGRAPHIC_WEIGHT = 0.20


STOPWORDS = {
    "a", "ad", "da", "di", "in", "il", "lo", "la",
    "i", "gli", "le", "un", "uno", "una", "e", "o",
    "per", "con", "su", "del", "della", "delle",
    "dei", "degli", "al", "alla", "alle", "ai",
    "agli", "che", "si", "sono", "ce", "c", "mi",
    "attenzione", "oggi", "qui", "zona"
}


SYNONYMS = {
    "allagata": "allagamento",
    "allagato": "allagamento",
    "allagamenti": "allagamento",
    "inondazione": "allagamento",
    "inondato": "allagamento",
    "inondazioni": "allagamento",

    "carreggiata": "strada",
    "carreggiate": "strada",
    "via": "strada",
    "viale": "strada",

    "automobili": "auto",
    "macchine": "auto",
    "veicoli": "auto",

    "rallentamenti": "traffico",
    "congestione": "traffico",
    "congestionato": "traffico"
}


DISTINCTIVE_ENTITIES = {
    "capannone",
    "fabbrica",
    "stabilimento",
    "automobile",
    "auto",
    "moto",
    "autobus",
    "treno",
    "edificio",
    "abitazione",
    "appartamento",
    "negozio",
    "magazzino",
    "scuola",
    "ospedale",
    "sottopasso",
    "ponte",
    "galleria",
    "albero",
    "palo"
}


GENERIC_LOCATIONS = {
    "napoli",
    "naples"
}


# ============================================================
# NORMALIZZAZIONE TESTI
# ============================================================

def normalize_text(value):
    """Normalizza un testo eliminando accenti e caratteri speciali."""

    value = (value or "").casefold()

    value = unicodedata.normalize("NFD", value)

    value = "".join(
        char for char in value
        if unicodedata.category(char) != "Mn"
    )

    value = re.sub(r"[^a-z0-9\s]", " ", value)

    return re.sub(r"\s+", " ", value).strip()


def tokenize(text):
    """Estrae le parole significative di un testo."""

    normalized = normalize_text(text)
    words = normalized.split()

    tokens = set()

    for word in words:
        if word in STOPWORDS or len(word) < 3:
            continue

        tokens.add(SYNONYMS.get(word, word))

    return tokens


def extract_distinctive_entities(text):
    """Individua gli oggetti concreti citati nella segnalazione."""

    tokens = tokenize(text)

    return tokens.intersection(DISTINCTIVE_ENTITIES)


def calculate_text_similarity(text_a, text_b):
    """
    Calcola la similarità testuale.

    Se entrambe le segnalazioni citano oggetti concreti
    differenti, le considera incompatibili.
    """

    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    entities_a = extract_distinctive_entities(text_a)
    entities_b = extract_distinctive_entities(text_b)

    if entities_a and entities_b and entities_a.isdisjoint(entities_b):
        return 0.0

    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)

    jaccard = len(intersection) / len(union)

    sequence_similarity = SequenceMatcher(
        None,
        " ".join(sorted(tokens_a)),
        " ".join(sorted(tokens_b))
    ).ratio()

    return max(jaccard, sequence_similarity)


# ============================================================
# GESTIONE DATE
# ============================================================

def parse_datetime(value):
    """Converte una data ISO in un datetime UTC."""

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, AttributeError):
        return None


def calculate_time_score(post_time, incident_time):
    """Restituisce un punteggio temporale tra 0 e 1."""

    difference = abs(
        (post_time - incident_time).total_seconds()
    )

    maximum = CORRELATION_WINDOW_MINUTES * 60

    return max(0.0, 1 - difference / maximum)


# ============================================================
# CATEGORIE E LOCALITA'
# ============================================================

def extract_category_names(categories):
    """Estrae i nomi delle categorie dal formato del filtro social."""

    names = set()

    for item in categories or []:

        if isinstance(item, dict):
            category = item.get("category")
        else:
            category = item

        if category:
            names.add(str(category).casefold().strip())

    return names


def normalize_locations(locations):
    """Normalizza le località ricevute dal filtro."""

    return {
        normalize_text(location)
        for location in (locations or [])
        if location
    }


def select_most_specific_location(locations):
    """
    Seleziona la località più specifica disponibile.

    Esempio:
    Napoli + Bagnoli -> Bagnoli.
    """

    valid_locations = [
        location.strip()
        for location in (locations or [])
        if isinstance(location, str) and location.strip()
    ]

    if not valid_locations:
        return None

    specific_locations = [
        location
        for location in valid_locations
        if normalize_text(location) not in GENERIC_LOCATIONS
    ]

    if specific_locations:
        return max(specific_locations, key=len)

    return max(valid_locations, key=len)


# ============================================================
# CALCOLO DISTANZA GEOGRAFICA - HAVERSINE
# ============================================================

def calculate_geographic_distance(
    latitude_a,
    longitude_a,
    latitude_b,
    longitude_b
):
    """
    Calcola la distanza in chilometri tra due coordinate
    geografiche utilizzando la formula di Haversine.

    Le coordinate devono essere espresse in gradi decimali.
    """

    values = [
        latitude_a,
        longitude_a,
        latitude_b,
        longitude_b
    ]

    if any(value is None for value in values):
        return None

    try:
        latitude_a, longitude_a, latitude_b, longitude_b = [
            float(value) for value in values
        ]

    except (TypeError, ValueError):
        return None

    if not all(math.isfinite(value) for value in [
        latitude_a, longitude_a, latitude_b, longitude_b
    ]):
        return None

    if not (-90 <= latitude_a <= 90):
        return None

    if not (-90 <= latitude_b <= 90):
        return None

    if not (-180 <= longitude_a <= 180):
        return None

    if not (-180 <= longitude_b <= 180):
        return None

    earth_radius_km = 6371.0088

    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)

    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a)
        * math.cos(lat_b)
        * math.sin(delta_lon / 2) ** 2
    )

    # Protezione contro piccoli errori numerici.
    haversine = min(1.0, max(0.0, haversine))

    central_angle = 2 * math.asin(math.sqrt(haversine))

    return earth_radius_km * central_angle


def calculate_geographic_score(
    post_coordinates,
    incident
):
    """
    Calcola la compatibilità geografica.

    Restituisce:
    - 1.0 per coordinate identiche;
    - un valore tra 0 e 1 se la distanza è entro il raggio;
    - None se le coordinate non sono disponibili.
    """

    if not post_coordinates:
        return None

    latitude = incident["latitude"]
    longitude = incident["longitude"]

    if latitude is None or longitude is None:
        return None

    distance = calculate_geographic_distance(
        post_coordinates["latitude"],
        post_coordinates["longitude"],
        latitude,
        longitude
    )

    if distance is None:
        return None

    if distance > MAX_CORRELATION_DISTANCE_KM:
        return 0.0

    return 1 - (
        distance / MAX_CORRELATION_DISTANCE_KM
    )


# ============================================================
# GEOCODIFICA DEGLI INCIDENTI
# ============================================================

def get_location_coordinates(location):
    """
    Recupera le coordinate di una località tramite geocoding.

    La funzione usa la cache locale quando disponibile.
    In caso di errore o località non trovata restituisce None.
    """

    if not location:
        return None

    try:
        result = geocode_location(location)

        if not result:
            return None

        latitude = result.get("latitude")
        longitude = result.get("longitude")

        if latitude is None or longitude is None:
            return None

        return {
            "latitude": float(latitude),
            "longitude": float(longitude)
        }

    except Exception:
        logging.exception(
            "Impossibile recuperare le coordinate di %s",
            location
        )

        return None


def update_incident_coordinates(
    connection,
    incident_id,
    location
):
    """
    Completa le coordinate di un incidente se mancanti.

    Non sovrascrive coordinate già presenti.
    """

    incident = connection.execute(
        """
        SELECT latitude, longitude
        FROM incidents
        WHERE id = ?
        """,
        (incident_id,)
    ).fetchone()

    if incident is None:
        return

    if (
        incident["latitude"] is not None
        and incident["longitude"] is not None
    ):
        return

    coordinates = get_location_coordinates(location)

    if coordinates is None:
        return

    connection.execute(
        """
        UPDATE incidents
        SET latitude = ?,
            longitude = ?
        WHERE id = ?
        """,
        (
            coordinates["latitude"],
            coordinates["longitude"],
            incident_id
        )
    )


# ============================================================
# RECUPERO DATI DEGLI INCIDENTI
# ============================================================

def get_incident_texts(connection, incident):
    """Recupera descrizione iniziale e post già associati."""

    texts = []

    if incident["description"]:
        texts.append(incident["description"])

    reports = connection.execute(
        """
        SELECT text
        FROM social_reports
        WHERE incident_id = ?
        """,
        (incident["id"],)
    ).fetchall()

    texts.extend(
        report["text"]
        for report in reports
        if report["text"]
    )

    return texts


def get_latest_incident_report_time(connection, incident):
    """
    Restituisce la data dell'ultima segnalazione associata.

    Se non ci sono segnalazioni valide, usa created_at.
    """

    reports = connection.execute(
        """
        SELECT published_at
        FROM social_reports
        WHERE incident_id = ?
        """,
        (incident["id"],)
    ).fetchall()

    report_times = [
        parse_datetime(report["published_at"])
        for report in reports
        if report["published_at"]
    ]

    valid_times = [
        report_time
        for report_time in report_times
        if report_time is not None
    ]

    if valid_times:
        return max(valid_times)

    return parse_datetime(incident["created_at"])


# ============================================================
# RICERCA INCIDENTE COMPATIBILE
# ============================================================

def find_matching_incident(
    connection,
    categories,
    locations,
    published_at,
    text,
    post_coordinates=None
):
    """
    Cerca l'incidente più compatibile.

    Controlla:
    - finestra temporale dall'ultima segnalazione;
    - compatibilità geografica;
    - corrispondenza della categoria;
    - similarità testuale;
    - compatibilità degli elementi distintivi.

    Se le località testuali coincidono, il sistema mantiene
    la compatibilità anche quando le coordinate mancano.

    Se le località sono differenti, sono necessarie coordinate
    valide e una distanza entro il raggio massimo.
    """

    post_time = parse_datetime(published_at)

    category_names = extract_category_names(categories)

    selected_location = select_most_specific_location(locations)
    post_location = normalize_text(selected_location)

    if not post_time or not category_names or not post_location:
        return None

    incidents = connection.execute(
        """
        SELECT *
        FROM incidents
        WHERE status = 'open'
        ORDER BY created_at DESC
        """
    ).fetchall()

    best_candidate = None
    best_score = 0.0

    for incident in incidents:

        incident_time = get_latest_incident_report_time(
            connection,
            incident
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

        incident_location = normalize_text(
            incident["location"]
        )

        if not incident_location:
            continue

        same_location = incident_location == post_location

        geographic_score = calculate_geographic_score(
            post_coordinates,
            incident
        )

        # Località differenti: richiediamo coordinate valide
        # e una distanza entro il raggio massimo.
        if not same_location:
            if geographic_score is None:
                continue

            if geographic_score <= 0:
                continue

        incident_category = (
            incident["event_type"] or ""
        ).casefold().strip()

        if incident_category not in category_names:
            continue

        existing_texts = get_incident_texts(
            connection,
            incident
        )

        similarities = [
            calculate_text_similarity(text, old_text)
            for old_text in existing_texts
        ]

        text_similarity = max(
            similarities,
            default=0.0
        )

        if text_similarity < MIN_TEXT_SIMILARITY:
            continue

        time_score = calculate_time_score(
            post_time,
            incident_time
        )

        # Se le località coincidono ma le coordinate non sono
        # disponibili, manteniamo il comportamento precedente.
        if geographic_score is None:
            geographic_score = 1.0

        total_score = (
            text_similarity * TEXT_WEIGHT
            + time_score * TIME_WEIGHT
            + geographic_score * GEOGRAPHIC_WEIGHT
        )

        if total_score > best_score:
            best_score = total_score
            best_candidate = incident["id"]

    return best_candidate


# ============================================================
# STATISTICHE SEGNALAZIONI
# ============================================================

def get_incident_report_stats(incident_id):
    """
    Restituisce il numero di segnalazioni e di autori distinti.

    Gli autori distinti indicano diffusione della segnalazione,
    non conferma indipendente dell'evento.
    """

    connection = get_connection()

    try:
        result = connection.execute(
            """
            SELECT
                COUNT(*) AS total_reports,
                COUNT(DISTINCT author_did) AS distinct_authors
            FROM social_reports
            WHERE incident_id = ?
            """,
            (incident_id,)
        ).fetchone()

        return {
            "incident_id": incident_id,
            "total_reports": result["total_reports"],
            "distinct_authors": result["distinct_authors"]
        }

    finally:
        connection.close()


# ============================================================
# CORRELAZIONE E SALVATAGGIO
# ============================================================

def correlate_report(
    post_uri,
    text,
    categories,
    locations,
    author_did,
    published_at
):
    """Collega una segnalazione a un incidente compatibile."""

    if not categories or not locations:
        raise ValueError(
            "Categorie e località sono necessarie "
            "per correlare una segnalazione."
        )

    connection = get_connection()

    try:
        # Evitiamo di salvare due volte lo stesso post.
        existing = connection.execute(
            """
            SELECT id, incident_id
            FROM social_reports
            WHERE post_uri = ?
            """,
            (post_uri,)
        ).fetchone()

        if existing:
            return existing["incident_id"]

        now = datetime.now(timezone.utc).isoformat()

        event_time = parse_datetime(published_at)

        incident_created_at = (
            event_time.isoformat()
            if event_time
            else now
        )

        selected_location = select_most_specific_location(
            locations
        )

        # Geocodifichiamo la località del nuovo post.
        # La cache evita richieste ripetute per località note.
        post_coordinates = get_location_coordinates(
            selected_location
        )

        incident_id = find_matching_incident(
            connection,
            categories,
            locations,
            published_at,
            text,
            post_coordinates=post_coordinates
        )

        if incident_id is None:

            category_names = extract_category_names(categories)

            category = sorted(category_names)[0]

            latitude = (
                post_coordinates["latitude"]
                if post_coordinates
                else None
            )

            longitude = (
                post_coordinates["longitude"]
                if post_coordinates
                else None
            )

            cursor = connection.execute(
                """
                INSERT INTO incidents (
                    event_type,
                    description,
                    location,
                    latitude,
                    longitude,
                    priority,
                    verification_status,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category,
                    text,
                    selected_location,
                    latitude,
                    longitude,
                    "pending",
                    "unverified",
                    "open",
                    incident_created_at,
                    now
                )
            )

            incident_id = cursor.lastrowid

        else:
            # Se l'incidente esiste ma non ha coordinate,
            # proviamo a recuperarle senza sovrascrivere
            # eventuali coordinate già presenti.
            update_incident_coordinates(
                connection,
                incident_id,
                selected_location
            )

        # Salviamo il post associandolo all'incidente.
        connection.execute(
            """
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
            """,
            (
                post_uri,
                incident_id,
                "bluesky",
                author_did,
                text,
                json.dumps(categories, ensure_ascii=False),
                json.dumps(locations, ensure_ascii=False),
                published_at,
                now
            )
        )

        connection.execute(
            """
            UPDATE incidents
            SET updated_at = ?
            WHERE id = ?
            """,
            (now, incident_id)
        )

        connection.commit()

        return incident_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
