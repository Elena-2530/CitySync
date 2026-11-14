"""
Comprensione delle domande rivolte al Mobility Agent.

Regole esplicite, senza modelli AI: dalla frase si ricavano l'intento,
l'eventuale partenza/destinazione e le preferenze di viaggio.
"""

import re

from agents.mobility.mobility_data.transport_data import normalize

INTENTS = (
    "route", "missing_info", "affected_roads", "avoid_traffic",
    "impact", "transport_status", "general",
)

_END = r"(?=\s+(?:con|usando|utilizzando|in|evitando|senza|oggi|adesso|ora|stasera|domani|cosa|quale|qual|che|conviene)\b|[?.,!;]|$)"
_FROM = r"(?:dall['’]|dalla|dallo|dagli|dalle|dal|dai|da)(?:\s+|(?<=['’]))"
_TO = r"(?:fino\s+all['’]|fino\s+alla|fino\s+allo|fino\s+al|fino\s+a|verso|all['’]|alla|allo|ad|al|a|nella|nel|in)(?:\s+|(?<=['’]))"
_VERB = r"(?:arriv\w*|and\w*|vad\w*|raggiung\w*|muov\w*|spost\w*)"

_ROUTE_PATTERNS = [
    # "da X a Y" / "da X fino a Y" / "da X verso Y"
    rf"\b{_FROM}(?P<o>.+?)\s+{_TO}(?P<d>.+?){_END}",
    # "come arrivo a Y da X" / "per andare a Y da X"
    rf"\b{_VERB}\s+{_TO}(?P<d>.+?)\s+{_FROM}(?P<o>.+?){_END}",
    # "sono a X e voglio andare/raggiungere Y"
    rf"\bsono\s+{_TO}(?P<o>.+?)\s*(?:,|\be\b|\bma\b)?\s*(?:voglio|devo|vorrei|come)\s+(?:{_VERB}\s+)?(?:{_TO})?(?P<d>.+?){_END}",
]

_INTENT_KEYWORDS = [
    ("missing_info", ["informazioni manc", "cosa manca", "cosa mancano", "quali verifiche", "cosa devo verificare",
                      "cosa verificare", "dati manc", "verifiche necessarie", "cosa non sappiamo"]),
    ("affected_roads", ["quali strade", "strade interessate", "strade coinvolte", "quali vie",
                        "strade potrebbero", "strade potrebbe"]),
    ("avoid_traffic", ["evitare il traffico", "evitare traffico", "come evito", "evito il traffico",
                       "aggirare il traffico", "evitare le code"]),
    ("impact", ["conseguenze", "impatto", "ripercussioni", "effetti sulla mobilita"]),
    ("transport_status", ["funziona", "funzionano", "in servizio", "e sospesa", "e sospeso",
                          "sono sospese", "ritardo", "ritardi", "circola", "circolano"]),
]

_ROUTE_WORDS = ["come arrivo", "come posso arrivare", "come raggiungo", "come posso raggiungere",
                "come mi sposto", "come mi muovo", "come si va", "percorso", "itinerario",
                "come arrivare", "come andare", "come ci arrivo"]

_PROFILE_KEYWORDS = [
    ("accessible", ["carrozzina", "disabil", "mobilita ridotta", "accessibil", "ascensore", "passeggino"]),
    ("fewest_transfers", ["senza cambi", "pochi cambi", "meno cambi", "turista", "tourist", "con le valigie", "bagagli"]),
    ("fastest", ["piu veloce", "piu rapido", "velocemente", "il prima possibile", "in fretta"]),
]


def _clean_place(value):
    if not value:
        return None
    value = value.strip(" ,.;:!?\"'")
    value = re.sub(r"^(?:la|il|lo|l'|i|gli|le)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+(?:e|ma|per favore|grazie)$", "", value, flags=re.IGNORECASE)
    return value.strip() or None


def extract_route(question):
    """Restituisce (origine, destinazione) trovate nella frase, o (None, None)."""
    if not isinstance(question, str):
        return None, None
    text = " ".join(question.split())
    for pattern in _ROUTE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            origin = _clean_place(match.group("o"))
            destination = _clean_place(match.group("d"))
            if origin and destination:
                return origin, destination
    return None, None


def detect_profile(question, user_type=None):
    text = normalize(question or "")
    for profile, words in _PROFILE_KEYWORDS:
        if any(word in text for word in words):
            return profile
    if user_type in {"tourist", "turista"}:
        return "fewest_transfers"
    return None


def detect_intent(question, origin=None, destination=None):
    text = normalize(question or "")
    if origin and destination:
        return "route"
    for intent, words in _INTENT_KEYWORDS:
        if any(word in text for word in words):
            return intent
    if any(normalize(word) in text for word in _ROUTE_WORDS):
        return "route"
    return "general"


def parse_question(question, user_type=None):
    """Analizza una domanda e restituisce intento, luoghi e profilo di viaggio."""
    origin, destination = extract_route(question)
    return {
        "intent": detect_intent(question, origin, destination),
        "origin": origin,
        "destination": destination,
        "profile": detect_profile(question, user_type),
    }
