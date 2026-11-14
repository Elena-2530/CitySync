
def analyze(incident=None, traffic_analysis=None,
            transport_analysis=None):
    """
    Valuta i possibili impatti sulla mobilità.

    Le conseguenze sono ipotesi da verificare, non fatti accertati.
    """

    incident = incident or {}
    traffic_analysis = traffic_analysis or {}
    transport_analysis = transport_analysis or {}

    description = (
        incident.get("description") or ""
    ).lower()

    possible_impacts = []
    missing_information = []

    if any(word in description for word in [
        "incidente", "collisione", "scontro"
    ]):
        possible_impacts.extend([
            "Possibili rallentamenti della circolazione.",
            "Possibili code nelle strade limitrofe.",
            "Possibili ritardi per il trasporto pubblico."
        ])

    if any(word in description for word in [
        "allagamento", "allagata", "acqua sulla strada"
    ]):
        possible_impacts.extend([
            "Possibile riduzione della percorribilità stradale.",
            "Possibili deviazioni dei mezzi pubblici."
        ])

    if any(word in description for word in [
        "strada chiusa", "strada bloccata", "chiusura"
    ]):
        possible_impacts.extend([
            "Possibile interruzione della circolazione.",
            "Possibile necessità di percorsi alternativi."
        ])

    if not description:
        missing_information.append(
            "Descrizione dell'evento non disponibile."
        )

    if not traffic_analysis.get("traffic_conditions"):
        missing_information.append(
            "Mancano dati aggiornati sul traffico."
        )

    if not transport_analysis.get("services"):
        missing_information.append(
            "Mancano dati aggiornati sui trasporti pubblici."
        )

    return {
        "agent": "mobility_impact_agent",
        "possible_impacts": list(dict.fromkeys(possible_impacts)),
        "missing_information": missing_information,
        "assessment_type": "potential_impact"
    }
