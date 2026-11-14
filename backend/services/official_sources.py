
import logging
import ssl
import re
from urllib.request import Request, urlopen
from urllib.parse import urljoin

import certifi
import feedparser
from bs4 import BeautifulSoup

from services.database import get_connection
from agents.verification_agent import add_evidence


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# FONTI UFFICIALI
# --------------------------------------------------

OFFICIAL_SOURCES = [
    {
        "name": "Protezione Civile Regione Campania",
        "url": "https://portaleprotezionecivile.regione.campania.it/?feed=rss2"
    }
]


# --------------------------------------------------
# PAROLE CHIAVE PER TIPOLOGIA DI INCIDENTE
# --------------------------------------------------

EVENT_KEYWORDS = {
    "mobility": [
        "traffico",
        "viabilità",
        "incidente",
        "strada chiusa",
        "trasporto",
        "metropolitana",
        "autobus",
        "treno"
    ],

    "environment": [
        "allagamento",
        "alluvione",
        "temporale",
        "pioggia",
        "frana",
        "incendio",
        "fumo",
        "rifiuti",
        "inquinamento"
    ],

    "civil_protection": [
        "emergenza",
        "terremoto",
        "scossa",
        "crollo",
        "esplosione",
        "evacuazione",
        "fuga di gas",
        "blackout"
    ],

    "tourism": [
        "concerto",
        "manifestazione",
        "evento",
        "affollamento"
    ]
}


# --------------------------------------------------
# CONNESSIONE HTTP
# --------------------------------------------------

def download_url(url):
    """Scarica una risorsa web usando HTTPS e certifi."""

    request = Request(
        url,
        headers={
            "User-Agent": "NEURAPOLIS/1.0 (prototype)"
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

        return response.read()


# --------------------------------------------------
# ESTRAZIONE DEI PDF
# --------------------------------------------------

def extract_pdf_links(soup, article_url):
    """Individua i PDF allegati a una notizia."""

    pdf_links = []

    for link in soup.select("a[href]"):
        href = link.get("href", "").strip()

        if not href:
            continue

        absolute_url = urljoin(article_url, href)

        if ".pdf" in absolute_url.lower().split("?")[0]:
            pdf_links.append({
                "title": link.get_text(" ", strip=True),
                "url": absolute_url
            })

    return pdf_links


# --------------------------------------------------
# ESTRAZIONE DEL TESTO PRINCIPALE
# --------------------------------------------------

def extract_main_content(soup):
    """
    Cerca il contenuto principale dell'articolo,
    evitando menu, footer e altri elementi secondari.
    """

    # Rimuoviamo elementi che non contengono il contenuto
    for element in soup.select(
        """
        script,
        style,
        nav,
        footer,
        header,
        aside,
        form,
        iframe,
        noscript,
        .cookie-notice,
        .cookie-banner,
        #cookie-notice,
        #cookie-banner,
        .widget-area,
        .sidebar
        """
    ):
        element.decompose()

    # Proviamo diversi contenitori tipici di WordPress
    selectors = [
        ".entry-content",
        ".post-content",
        ".article-content",
        "article",
        "main",
        "#content",
        "#primary"
    ]

    for selector in selectors:
        content = soup.select_one(selector)

        if content:
            text = content.get_text(" ", strip=True)

            if len(text) > 100:
                return text

    # Ultimo tentativo: tutto il body
    if soup.body:
        return soup.body.get_text(" ", strip=True)

    return ""


# --------------------------------------------------
# LETTURA DI UNA PAGINA
# --------------------------------------------------

def fetch_article(article_url):
    """Scarica una pagina e ne estrae testo e allegati."""

    try:
        html = download_url(article_url)

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        pdf_links = extract_pdf_links(
            soup,
            article_url
        )

        article_text = extract_main_content(
            soup
        )

        return {
            "text": article_text,
            "pdf_links": pdf_links
        }

    except Exception as error:
        logger.warning(
            "Errore durante la lettura di %s: %s",
            article_url,
            error
        )

        return {
            "text": "",
            "pdf_links": []
        }


# --------------------------------------------------
# RECUPERO DEL FEED RSS
# --------------------------------------------------

def fetch_source_entries(source):
    """Recupera le notizie da una fonte RSS."""

    try:
        content = download_url(
            source["url"]
        )

        parsed_feed = feedparser.parse(
            content
        )

        if parsed_feed.bozo and not parsed_feed.entries:
            logger.warning(
                "Feed non leggibile: %s",
                source["name"]
            )

            return []

        entries = []

        for entry in parsed_feed.entries:

            title = entry.get(
                "title", ""
            ).strip()

            link = entry.get(
                "link", ""
            ).strip()

            if not title or not link:
                continue

            # Leggiamo la pagina originale
            article = fetch_article(link)

            entries.append({
                "source_name": source["name"],
                "title": title,
                "summary": article["text"],
                "link": link,
                "published": entry.get(
                    "published", ""
                ),
                "pdf_links": article["pdf_links"]
            })

        logger.info(
            "%s: recuperate %s notizie",
            source["name"],
            len(entries)
        )

        return entries

    except Exception as error:
        logger.exception(
            "Errore nel recupero della fonte %s: %s",
            source["name"],
            error
        )

        return []


# --------------------------------------------------
# RICERCA DI CORRISPONDENZE
# --------------------------------------------------

def normalize_text(text):
    """Normalizza il testo per il confronto."""

    return re.sub(
        r"\s+",
        " ",
        (text or "").casefold()
    ).strip()


def matches_incident(article, incident):
    """
    Verifica preliminarmente se una notizia
    può essere collegata a un incidente.

    La corrispondenza non costituisce conferma.
    """

    article_text = normalize_text(
        article["title"] + " " + article["summary"]
    )

    location = normalize_text(
        incident["location"]
    )

    if not location:
        return False

    # Deve esserci un riferimento alla località
    if location not in article_text:
        return False

    event_type = incident["event_type"]

    keywords = EVENT_KEYWORDS.get(
        event_type,
        []
    )

    if not keywords:
        return False

    return any(
        normalize_text(keyword) in article_text
        for keyword in keywords
    )


# --------------------------------------------------
# RECUPERO DEGLI INCIDENTI APERTI
# --------------------------------------------------

def find_incident_candidates(article):
    """Trova gli incidenti compatibili con una notizia."""

    connection = get_connection()

    try:
        incidents = connection.execute(
            """
            SELECT
                id,
                event_type,
                description,
                location,
                created_at
            FROM incidents
            WHERE status = 'open'
            """
        ).fetchall()

        return [
            incident
            for incident in incidents
            if matches_incident(article, incident)
        ]

    finally:
        connection.close()


# --------------------------------------------------
# STAMPA DELLE NOTIZIE RECUPERATE
# --------------------------------------------------

def print_articles(articles):
    """Mostra le informazioni recuperate dalle fonti."""

    for article in articles:

        print("\n" + "=" * 60)
        print("FONTE:", article["source_name"])
        print("TITOLO:", article["title"])

        print(
            "DESCRIZIONE:",
            article["summary"][:700]
        )

        print("LINK:", article["link"])
        print("DATA:", article["published"])

        print("\nPDF ALLEGATI:")

        if article["pdf_links"]:
            for pdf in article["pdf_links"]:
                print(
                    "-",
                    pdf["title"],
                    pdf["url"]
                )
        else:
            print("Nessun PDF individuato.")

        print("=" * 60)


# --------------------------------------------------
# RACCOLTA DELLE EVIDENZE
# --------------------------------------------------

def collect_official_evidence():
    """
    Recupera le notizie ufficiali e cerca
    possibili corrispondenze con gli incidenti.

    Le notizie vengono registrate come evidenze
    contestuali, non come conferme automatiche.
    """

    total_articles = 0
    total_matches = 0

    for source in OFFICIAL_SOURCES:

        articles = fetch_source_entries(
            source
        )

        total_articles += len(articles)

        # Stampiamo le notizie recuperate
        print_articles(articles)

        for article in articles:

            candidates = find_incident_candidates(
                article
            )

            for incident in candidates:

                description = (
                    f"Titolo: {article['title']}\n"
                    f"Descrizione: {article['summary']}\n"
                    f"Data pubblicazione: {article['published']}"
                )

                result = add_evidence(
                    incident_id=incident["id"],
                    source_name=article["source_name"],
                    source_url=article["link"],
                    description=description,
                    evidence_type="context"
                )

                total_matches += 1

                logger.info(
                    "Notizia associata all'incidente %s. "
                    "Stato verifica: %s",
                    incident["id"],
                    result["verification_status"]
                )

    return {
        "articles_retrieved": total_articles,
        "incident_matches": total_matches
    }


# --------------------------------------------------
# AVVIO DEL MODULO
# --------------------------------------------------

if __name__ == "__main__":

    result = collect_official_evidence()

    print("\nRISULTATO RACCOLTA FONTI UFFICIALI")
    print(result)
