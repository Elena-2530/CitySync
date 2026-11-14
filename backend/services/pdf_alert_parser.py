
import re
import json
from pathlib import Path


def normalize_text(text):
    """Rimuove spazi e interruzioni di riga superflue."""
    return re.sub(r"\s+", " ", text).strip()


def extract_alert_number(text):
    match = re.search(
        r"AVVISO REGIONALE DI ALLERTA N\.\s*(\d+/\d{4})",
        text,
        re.IGNORECASE
    )

    return match.group(1) if match else None


def extract_validity(text):
    start = re.search(
        r"Valido dalle\s+(\d{2}:\d{2}\s+.*?\d{4})",
        text,
        re.IGNORECASE
    )

    end = re.search(
        r"Valido fino alle\s+(\d{2}:\d{2}\s+.*?\d{4})",
        text,
        re.IGNORECASE
    )

    return {
        "valid_from": normalize_text(start.group(1)) if start else None,
        "valid_until": normalize_text(end.group(1)) if end else None
    }


def extract_zones(text):
    """
    Estrae i blocchi della tabella delle allerte
    dalle pagine 3 e 4.
    """

    # Individua le righe contenenti solo il numero della zona.
    markers = list(
        re.finditer(r"(?m)^\s*([1-8])\s*$", text)
    )

    zones = []

    for index, marker in enumerate(markers):
        zone_number = int(marker.group(1))

        start = marker.end()

        if index + 1 < len(markers):
            end = markers[index + 1].start()
        else:
            end = len(text)

        block = text[start:end]

        # Estrae il livello di allerta.
        level_match = re.search(
            r"\b(VERDE|GIALLA|ARANCIONE|ROSSA)\b",
            block,
            re.IGNORECASE
        )

        if not level_match:
            continue

        alert_level = level_match.group(1).lower()

        # Estrae le tipologie di rischio.
        risks = []

        if re.search(r"Idrogeologico\s+Localizzato", block, re.IGNORECASE):
            risks.append("idrogeologico")

        if re.search(r"Idraulico\s+Localizzato", block, re.IGNORECASE):
            risks.append("idraulico")

        zones.append({
            "zone": zone_number,
            "alert_level": alert_level,
            "risks": risks
        })

    return zones



def extract_territories(text):
    """Associa a ogni zona il territorio indicato nella legenda."""

    legend_match = re.search(
        r"Legenda\s+Zone\s+di\s+Allerta Meteo:\s*(.*)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not legend_match:
        return {}

    legend = legend_match.group(1)

    # La legenda termina dopo la descrizione della zona 8.
    legend_end = re.search(
        r"Zona\s+8:\s*(.*?)(?:\.\s|$)",
        legend,
        re.IGNORECASE | re.DOTALL
    )

    if not legend_end:
        return {}

    # Manteniamo solo il testo della legenda.
    legend = legend[:legend_end.end()]

    matches = re.finditer(
        r"Zona\s+(\d+):\s*(.*?)(?=;\s*Zona\s+\d+:|$)",
        legend,
        re.IGNORECASE | re.DOTALL
    )

    territories = {}

    for match in matches:
        zone_number = int(match.group(1))
        territory = normalize_text(match.group(2)).rstrip(".; ")

        territories[zone_number] = territory

    return territories

def parse_alert(text):
    """Costruisce il risultato strutturato dell'avviso."""

    # Le tabelle si trovano nelle pagine 3 e 4.
    pages = text.split("========== PAGINA ")

    table_text = ""

    for page in pages:
        if page.startswith("3 ") or page.startswith("4 "):
            table_text += page

    zones = extract_zones(table_text)
    territories = extract_territories(table_text)

    for zone in zones:
        zone["territory"] = territories.get(zone["zone"])

    validity = extract_validity(table_text)

    return {
        "alert_number": extract_alert_number(text),
        "valid_from": validity["valid_from"],
        "valid_until": validity["valid_until"],
        "zones": zones
    }


if __name__ == "__main__":

    backend_dir = Path(__file__).resolve().parent.parent

    input_path = backend_dir / "data" / "avviso_094_2026_estratto.txt"

    text = input_path.read_text(encoding="utf-8")

    result = parse_alert(text)

    print("\nRISULTATO ESTRAZIONE AVVISO\n")

    print(json.dumps(result, indent=4, ensure_ascii=False))

    output_path = backend_dir / "data" / "avviso_094_2026.json"

    output_path.write_text(
        json.dumps(result, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\nJSON salvato in: {output_path}")
