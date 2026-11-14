
import re
import unicodedata


# Zone e riferimenti geografici di Napoli.
NAPLES_TERMS = [
    "napoli",
    "naples",
    "fuorigrotta",
    "chiaia",
    "vomero",
    "bagnoli",
    "posillipo",
    "scampia",
    "pianura",
    "secondigliano",
    "forcella",
    "sanita",
    "sanità",
    "spaccanapoli",
    "via toledo",
    "via marina",
    "piazza municipio",
    "piazza garibaldi",
    "piazza plebiscito",
    "capodichino",
    "porto di napoli",
    "stazione centrale",
]

# Eventi di interesse per NEURAPOLIS.
EVENT_KEYWORDS = {
    "mobility": [
        "traffico",
        "incidente",
        "strada chiusa",
        "strada bloccata",
        "autobus",
        "bus",
        "metro",
        "metropolitana",
        "treno",
        "ritardo",
        "sciopero",
        "bloccato",
        "viabilita",
        "viabilità",
    ],

    "environment": [
        "allagamento",
        "allagata",
        "pioggia",
        "temporale",
        "vento forte",
        "frana",
        "rifiuti",
        "inquinamento",
        "incendio",
        "fumo",
    ],

    "civil_protection": [
        "terremoto",
        "scossa",
        "emergenza",
        "crollo",
        "esplosione",
        "evacuazione",
        "fuga di gas",
        "blackout",
    ],

    "tourism": [
        "evento",
        "concerto",
        "manifestazione",
        "corteo",
        "turisti",
        "affollamento",
    ],
}


def normalize_text(text: str) -> str:
    """Normalizza il testo per facilitare la ricerca."""

    text = text.lower()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    return re.sub(r"\s+", " ", text).strip()


def contains_term(text: str, term: str) -> bool:
    """Cerca una parola o espressione senza falsi match parziali."""

    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return re.search(pattern, text) is not None


def analyze_social_text(text: str) -> dict:
    """
    Esegue il primo filtraggio territoriale e tematico.

    Non stabilisce se una notizia sia vera:
    identifica soltanto contenuti potenzialmente rilevanti.
    """

    normalized = normalize_text(text)

    locations = [
        term for term in NAPLES_TERMS
        if contains_term(normalized, normalize_text(term))
    ]

    categories = []

    for category, keywords in EVENT_KEYWORDS.items():

        matches = [
            keyword for keyword in keywords
            if contains_term(normalized, normalize_text(keyword))
        ]

        if matches:
            categories.append({
                "category": category,
                "matched_keywords": matches
            })

    relevant = bool(locations and categories)

    return {
        "relevant": relevant,
        "locations": locations,
        "categories": categories,
        "reason": (
            "Riferimento territoriale e tematico individuati"
            if relevant
            else "Non supera il filtro territoriale e tematico"
        )
    }
