"""
Comprensione delle domande rivolte al Tourism Agent.

Regole esplicite, senza modelli AI: dalla frase si ricavano l'intento,
l'eventuale categoria di luoghi e se si chiede come raggiungere un posto
(in quel caso la risposta è del Mobility Agent).
"""

from agents.tourism.tourism_data.places import normalize

INTENTS = ("indoor", "nearby", "hours", "tickets", "where", "history", "search", "general")

_INTENT_KEYWORDS = [
    ("indoor", ["piove", "pioggia", "maltempo", "al coperto", "al chiuso", "temporale"]),
    ("nearby", ["vicino", "vicina", "nei pressi", "intorno", "a due passi", "nelle vicinanze", "dintorni"]),
    ("hours", ["orari", "orario", "aperto", "aperta", "aperti", "chiuso", "chiusa", "chiusi",
               "apre", "chiude", "a che ora", "fino a che ora", "quando apre", "quando chiude"]),
    ("tickets", ["biglietto", "biglietti", "prezzo", "prezzi", "costo", "quanto costa", "gratis",
                 "gratuito", "gratuita", "ingresso"]),
    ("where", ["dove si trova", "dov e", "dove sta", "indirizzo", "in che zona", "in che quartiere"]),
    ("history", ["storia", "racconta", "raccontami", "parlami", "cos e", "che cos e", "cosa e",
                 "informazioni", "curiosita", "chi lo ha", "chi la ha", "quando e stato", "quando e stata",
                 "descrizione", "perche e famos"]),
    ("search", ["cosa vedere", "cosa visitare", "da vedere", "da visitare", "attrazioni", "monumenti",
                "luoghi", "consigli", "cosa fare"]),
]

_ROUTE_WORDS = ["come arrivo", "come arrivare", "come raggiungo", "come posso raggiungere",
                "come si arriva", "come ci arrivo", "come si raggiunge", "come ci vado",
                "come andare", "percorso per", "indicazioni per"]

# parola chiave → categoria nei dati
_CATEGORY_KEYWORDS = [
    ("museum", ["museo", "musei"]),
    ("castle", ["castello", "castelli", "castel"]),
    ("church", ["chiesa", "chiese", "cattedrale", "cattedrali", "basilica"]),
    ("palace", ["palazzo", "palazzi", "reggia"]),
    ("theatre", ["teatro", "teatri"]),
    ("square", ["piazza", "piazze"]),
    ("street", ["strada", "strade", "vicoli", "vicolo"]),
    ("panorama", ["panorama", "panoramico", "panoramici", "vista", "belvedere"]),
    ("seafront", ["lungomare", "passeggiata sul mare", "sul mare"]),
]


def detect_intent(question):
    text = normalize(question or "")
    for intent, words in _INTENT_KEYWORDS:
        if any(normalize(word) in text for word in words):
            return intent
    return "general"


def detect_category(question):
    text = normalize(question or "")
    for category, words in _CATEGORY_KEYWORDS:
        if any(normalize(word) in text.split() or f" {normalize(word)} " in f" {text} " for word in words):
            return category
    return None


def asks_for_route(question):
    text = normalize(question or "")
    return any(normalize(word) in text for word in _ROUTE_WORDS)


def parse_question(question):
    """Intento, categoria richiesta e se serve un percorso."""
    return {
        "intent": detect_intent(question),
        "category": detect_category(question),
        "asks_route": asks_for_route(question),
    }
