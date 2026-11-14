import json
import logging

from collections import Counter
from datetime import datetime, timezone

from services.database import get_connection


logger = logging.getLogger("neurapolis.social_intelligence")


# ============================================================
# FUNZIONI DI SUPPORTO
# ============================================================

def parse_json_list(value):
    """
    Converte un campo JSON del database in una lista Python.

    In caso di valore vuoto o JSON non valido restituisce
    una lista vuota.
    """

    if not value:
        return []

    try:
        result = json.loads(value)

        if isinstance(result, list):
            return result

        return []

    except (json.JSONDecodeError, TypeError):
        return []


def parse_datetime(value):
    """
    Converte una data ISO in datetime.

    Gestisce anche il suffisso Z utilizzato per UTC.
    """

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    except (ValueError, TypeError, AttributeError):
        return None


def extract_categories(reports):
    """
    Conta le categorie presenti nelle segnalazioni.

    Le categorie sono quelle già individuate dal social_filter.
    """

    counter = Counter()

    for report in reports:
        categories = parse_json_list(report["categories"])

        for item in categories:

            if isinstance(item, dict):
                category = item.get("category")
            else:
                category = item

            if category:
                counter[str(category)] += 1

    return dict(counter)


def extract_locations(reports):
    """
    Conta le località individuate nelle segnalazioni.
    """

    counter = Counter()

    for report in reports:
        locations = parse_json_list(report["locations"])

        for location in locations:

            if isinstance(location, str) and location.strip():
                counter[location.strip()] += 1

    return dict(counter)


def get_report_time_range(reports):
    """
    Restituisce la data della prima e dell'ultima
    segnalazione, quando disponibili.
    """

    dates = []

    for report in reports:
        parsed = parse_datetime(report["published_at"])

        if parsed:
            dates.append(parsed)

    if not dates:
        return {
            "first_report_at": None,
            "last_report_at": None
        }

    return {
        "first_report_at": min(dates).isoformat(),
        "last_report_at": max(dates).isoformat()
    }


# ============================================================
# ANALISI DELLE SEGNALAZIONI SOCIAL
# ============================================================

def analyze_social_reports(reports):
    """
    Analizza le segnalazioni associate a un incidente.

    Produce statistiche e osservazioni descrittive.

    Non verifica la veridicità delle segnalazioni e non
    considera automaticamente autori distinti come fonti
    indipendenti.
    """

    total_reports = len(reports)

    distinct_authors = {
        report["author_did"]
        for report in reports
        if report["author_did"]
    }

    categories = extract_categories(reports)
    locations = extract_locations(reports)

    time_range = get_report_time_range(reports)

    observations = []
    limitations = []

    if total_reports == 0:

        observations.append(
            "Non sono presenti segnalazioni social associate."
        )

        limitations.append(
            "Non sono disponibili dati social da analizzare."
        )

    else:

        observations.append(
            f"Sono presenti {total_reports} segnalazioni social."
        )

        if len(distinct_authors) == 1:
            observations.append(
                "Le segnalazioni provengono da un solo autore identificato."
            )

        elif len(distinct_authors) > 1:
            observations.append(
                f"Sono presenti {len(distinct_authors)} autori distinti."
            )

        else:
            observations.append(
                "Non è stato possibile identificare gli autori."
            )

        if len(distinct_authors) > 1:
            limitations.append(
                "Autori distinti non equivalgono necessariamente "
                "a fonti indipendenti o a conferme dell'evento."
            )

        if not categories:
            limitations.append(
                "Non sono disponibili categorie tematiche."
            )

        if not locations:
            limitations.append(
                "Non sono disponibili località nelle segnalazioni."
            )

        if not time_range["first_report_at"]:
            limitations.append(
                "Non sono disponibili date di pubblicazione valide."
            )

    return {
        "total_reports": total_reports,
        "distinct_authors": len(distinct_authors),
        "categories": categories,
        "locations": locations,
        "first_report_at": time_range["first_report_at"],
        "last_report_at": time_range["last_report_at"],
        "observations": observations,
        "limitations": limitations
    }


# ============================================================
# SOCIAL INTELLIGENCE AGENT
# ============================================================

def get_social_intelligence(incident_id):
    """
    Recupera un incidente e le relative segnalazioni social.

    Restituisce un'analisi strutturata destinata a Janara
    Orchestrator e agli altri agenti.

    Questa funzione è di sola lettura: non modifica il database.
    """

    connection = get_connection()

    try:

        # ----------------------------------------------------
        # 1. RECUPERO INCIDENTE
        # ----------------------------------------------------

        incident = connection.execute(
            """
            SELECT
                id,
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
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,)
        ).fetchone()

        if incident is None:
            return None

        # ----------------------------------------------------
        # 2. RECUPERO SEGNALAZIONI SOCIAL
        # ----------------------------------------------------

        reports = connection.execute(
            """
            SELECT
                id,
                post_uri,
                source,
                author_did,
                text,
                categories,
                locations,
                published_at,
                received_at
            FROM social_reports
            WHERE incident_id = ?
            ORDER BY published_at ASC
            """,
            (incident_id,)
        ).fetchall()

        # ----------------------------------------------------
        # 3. ANALISI DELLE SEGNALAZIONI
        # ----------------------------------------------------

        social_analysis = analyze_social_reports(reports)

        # ----------------------------------------------------
        # 4. PREPARAZIONE DEI DATI PER GLI ALTRI AGENTI
        # ----------------------------------------------------

        report_details = []

        for report in reports:

            report_details.append({
                "report_id": report["id"],
                "source": report["source"],
                "author_did": report["author_did"],
                "text": report["text"],
                "published_at": report["published_at"],
                "categories": parse_json_list(
                    report["categories"]
                ),
                "locations": parse_json_list(
                    report["locations"]
                )
            })

        # ----------------------------------------------------
        # 5. RISULTATO FINALE
        # ----------------------------------------------------

        result = {
            "agent": "social_intelligence_agent",
            "analysis_type": "descriptive",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),

            "incident": {
                "id": incident["id"],
                "event_type": incident["event_type"],
                "description": incident["description"],
                "location": incident["location"],
                "latitude": incident["latitude"],
                "longitude": incident["longitude"],
                "priority": incident["priority"],
                "verification_status": incident["verification_status"],
                "status": incident["status"],
                "created_at": incident["created_at"],
                "updated_at": incident["updated_at"]
            },

            "social_analysis": social_analysis,

            "reports": report_details
        }

        logger.info(
            "Analisi social completata per incidente %s",
            incident_id
        )

        return result

    except Exception:

        logger.exception(
            "Errore nell'analisi social dell'incidente %s",
            incident_id
        )

        raise

    finally:
        connection.close()


# ============================================================
# TEST MANUALE
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    try:

        incident_id = int(
            input("Inserisci l'ID dell'incidente da analizzare: ")
        )

        result = get_social_intelligence(incident_id)

        if result is None:

            print("Incidente non trovato.")

        else:

            print("\n===== SOCIAL INTELLIGENCE AGENT =====")

            print(
                json.dumps(
                    result,
                    indent=4,
                    ensure_ascii=False
                )
            )

    except ValueError:
        print("Inserisci un ID numerico valido.")

    except Exception:
        logger.exception("Errore durante il test dell'agente.")