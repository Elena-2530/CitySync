"""
Conoscenza di base sulla viabilità di Napoli per il Mobility Agent.

ATTENZIONE: questo modulo NON contiene traffico in tempo reale. Contiene solo
un elenco INDICATIVO degli assi stradali principali di alcune zone, utile per
rispondere a domande come "quali strade potrebbero essere interessate?".
Le strade restituite sono ipotesi da verificare, non strade accertate come
coinvolte da un evento.

Per collegare una fonte reale (traffico, cantieri, chiusure) basta
implementare get_live_traffic() e far restituire i dati nello stesso formato
di context["traffic_data"] (conditions, affected_roads, max_age_minutes).
"""

from agents.mobility.mobility_data.transport_data import normalize_place

ZONE_MAIN_ROADS = {
    "fuorigrotta": {
        "label": "Fuorigrotta",
        "roads": ["Via Giulio Cesare", "Viale Augusto", "Via Terracina",
                  "Via Leopardi", "Piazzale Tecchio", "Via Cinthia"],
        "other": ["Tangenziale di Napoli (svincoli della zona)"],
    },
    "stadio maradona": {"same_as": "fuorigrotta"},
    "mergellina": {
        "label": "Mergellina e Chiaia",
        "roads": ["Via Caracciolo", "Riviera di Chiaia", "Via Mergellina", "Via Piedigrotta"],
        "other": [],
    },
    "chiaia": {"same_as": "mergellina"},
    "centro storico": {
        "label": "Centro storico",
        "roads": ["Via Toledo", "Via Medina", "Via Marina", "Corso Umberto I", "Via Depretis"],
        "other": [],
    },
    "centro": {"same_as": "centro storico"},
    "municipio": {"same_as": "centro storico"},
    "garibaldi": {
        "label": "Piazza Garibaldi e stazione centrale",
        "roads": ["Corso Garibaldi", "Corso Novara", "Via Marina", "Corso Umberto I"],
        "other": [],
    },
    "vomero": {
        "label": "Vomero",
        "roads": ["Via Cilea", "Via Scarlatti", "Via Luca Giordano"],
        "other": [],
    },
    "porto": {
        "label": "Porto e Stazione Marittima",
        "roads": ["Via Marina", "Via Acton", "Via Cristoforo Colombo"],
        "other": [],
    },
    "marittima": {"same_as": "porto"},
}

KNOWLEDGE_NOTE = (
    "Elenco indicativo degli assi principali della zona, non una previsione: "
    "le strade realmente interessate vanno verificate."
)


def roads_for_location(location):
    """
    Assi stradali principali della zona indicata, oppure None se la zona non
    è nota. Il risultato è una base di conoscenza, non un dato verificato.
    """
    text = normalize_place(location)
    if not text:
        return None

    best = None
    for key in ZONE_MAIN_ROADS:
        alias = normalize_place(key)
        if alias and (alias == text or f" {alias} " in f" {text} "):
            if best is None or len(alias) > len(best):
                best = key
    if best is None:
        return None

    entry = ZONE_MAIN_ROADS[best]
    entry = ZONE_MAIN_ROADS[entry["same_as"]] if "same_as" in entry else entry
    return {
        "zone": entry["label"],
        "roads": list(entry["roads"]),
        "other": list(entry["other"]),
        "basis": "knowledge_base",
        "verified": False,
        "note": KNOWLEDGE_NOTE,
    }


def get_live_traffic(location=None):
    """
    Punto di collegamento per una fonte di traffico in tempo reale.

    Al momento nessuna fonte è collegata: la funzione lo dichiara e non
    inventa dati. Quando ci sarà una fonte, deve restituire un dizionario
    come context["traffic_data"], con "updated_at" in formato ISO 8601.
    """
    return {
        "available": False,
        "reason": "Nessuna fonte di traffico in tempo reale è collegata.",
    }
