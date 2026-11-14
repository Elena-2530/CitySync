
import ssl
import certifi
import re

from io import BytesIO
from urllib.request import Request, urlopen
from pathlib import Path
from pypdf import PdfReader


PDF_URL = (
    "https://portaleprotezionecivile.regione.campania.it/"
    "/wp-content/uploads/"
    "Avviso-di-allerta-meteo-idrogeologica-ed-idraulica-di-sabato-14-novembre-2026.pdf"
)


def download_pdf(url):
    request = Request(
        url,
        headers={"User-Agent": "NEURAPOLIS/1.0"}
    )

    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    with urlopen(
        request,
        context=ssl_context,
        timeout=30
    ) as response:
        return response.read()


def main():
    print("1. Download PDF...")
    pdf_bytes = download_pdf(PDF_URL)

    print("2. Estrazione testo...")
    reader = PdfReader(BytesIO(pdf_bytes))

    pages_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages_text.append(
            f"\n========== PAGINA {page_number} ==========\n{text}"
        )

    full_text = "\n".join(pages_text)

    # Salva tutto il testo estratto
    backend_dir = Path(__file__).resolve().parent.parent
    output_path = backend_dir / "data" / "avviso_094_2026_estratto.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")

    print(f"\n3. Testo salvato in:\n{output_path}")

    # Mostra le righe che potrebbero contenere informazioni sulle allerte
    print("\n4. RIGHE INTERESSANTI:\n")

    keywords = re.compile(
        r"zona|allerta|gialla|arancione|rossa|verde|napoli|"
        r"caserta|avellino|benevento|salerno",
        re.IGNORECASE
    )

    for line in full_text.splitlines():
        line = line.strip()

        if line and keywords.search(line):
            print(line)


if __name__ == "__main__":
    main()
