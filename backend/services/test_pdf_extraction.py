
import ssl
import certifi
from io import BytesIO
from urllib.request import Request, urlopen
from pypdf import PdfReader


PDF_URL = (
    "https://portaleprotezionecivile.regione.campania.it/"
    "/wp-content/uploads/"
    "Avviso-di-allerta-meteo-idrogeologica-ed-idraulica-di-sabato-14-novembre-2026.pdf"
)


def test_pdf_extraction():
    print("1. Connessione al PDF...")

    request = Request(
        PDF_URL,
        headers={"User-Agent": "NEURAPOLIS/1.0"}
    )

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    with urlopen(request, context=ssl_context, timeout=30) as response:
        pdf_bytes = response.read()

    print(f"2. PDF scaricato: {len(pdf_bytes)} byte")

    print("3. Lettura del documento...")

    reader = PdfReader(BytesIO(pdf_bytes))

    print(f"Numero di pagine: {len(reader.pages)}")

    extracted_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        extracted_text.append(text)

        print(f"\n--- PAGINA {page_number} ---")
        print(text[:2000] if text.strip() else "Nessun testo estratto")

    complete_text = "\n".join(extracted_text)

    print("\n--- RISULTATO ---")

    if complete_text.strip():
        print("ESTRAZIONE RIUSCITA!")
        print(f"Caratteri estratti: {len(complete_text)}")
    else:
        print("NESSUN TESTO ESTRATTO.")
        print("Potrebbe essere necessario utilizzare OCR.")


if __name__ == "__main__":
    test_pdf_extraction()
