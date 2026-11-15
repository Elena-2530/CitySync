
from datetime import datetime, timezone


def simulate_scenario(description, location):
    """
    Elabora uno scenario ipotetico.
    Non consulta eventi reali e non dichiara che
    lo scenario si sia effettivamente verificato.
    """

    text = description.casefold()
    location_name = location.get("name", "Località indicata")

    impacts = []
    actions = []
    affected_services = []

    # -------------------------------------------------
    # CLASSIFICAZIONE DELLO SCENARIO
    # -------------------------------------------------

    weather_words = [
        "temporale", "pioggia", "nubifragio",
        "alluvione", "allagamento", "maltempo"
    ]

    fire_words = [
        "incendio", "fiamme", "rogo", "fumo"
    ]

    earthquake_words = [
        "terremoto", "sisma", "scossa", "crollo"
    ]

    traffic_words = [
        "traffico", "incidente stradale",
        "strada bloccata", "blocco stradale"
    ]

    if any(word in text for word in weather_words):
        scenario_type = "maltempo"

    elif any(word in text for word in fire_words):
        scenario_type = "incendio"

    elif any(word in text for word in earthquake_words):
        scenario_type = "terremoto"

    elif any(word in text for word in traffic_words):
        scenario_type = "mobilità"

    else:
        scenario_type = "generico"

    # -------------------------------------------------
    # ANALISI DEGLI IMPATTI
    # -------------------------------------------------

    if scenario_type == "maltempo":

        impacts = [
            {
                "area": "Mobilità",
                "description": (
                    "Possibili rallentamenti, strade allagate "
                    "e difficoltà nella circolazione."
                ),
                "priority": "alta"
            },
            {
                "area": "Infrastrutture",
                "description": (
                    "Possibili criticità nei sottopassi, "
                    "nelle aree depresse e nei sistemi di drenaggio."
                ),
                "priority": "alta"
            },
            {
                "area": "Cittadini",
                "description": (
                    "Possibili disagi per anziani, persone fragili "
                    "e cittadini che si spostano a piedi."
                ),
                "priority": "media"
            }
        ]

        affected_services = [
            "Viabilità",
            "Trasporto pubblico",
            "Protezione civile",
            "Servizi di emergenza"
        ]

        actions = [
            "Monitorare le condizioni meteorologiche e gli aggiornamenti ufficiali.",
            "Individuare preventivamente le strade e i sottopassi più esposti.",
            "Informare i cittadini sulle condizioni della viabilità.",
            "Predisporre percorsi alternativi per i mezzi di emergenza.",
            "Verificare le condizioni delle infrastrutture di drenaggio."
        ]

    elif scenario_type == "incendio":

        impacts = [
            {
                "area": "Salute pubblica",
                "description": (
                    "Possibile esposizione al fumo e peggioramento "
                    "della qualità dell'aria."
                ),
                "priority": "alta"
            },
            {
                "area": "Mobilità",
                "description": (
                    "Possibili limitazioni alla circolazione "
                    "nelle aree interessate."
                ),
                "priority": "alta"
            },
            {
                "area": "Infrastrutture",
                "description": (
                    "Possibili danni agli edifici e alle strutture "
                    "vicine al focolaio."
                ),
                "priority": "alta"
            }
        ]

        affected_services = [
            "Vigili del fuoco",
            "Servizi sanitari",
            "Viabilità",
            "Protezione civile"
        ]

        actions = [
            "Allertare i servizi competenti attraverso i canali ufficiali.",
            "Valutare l'estensione dell'area interessata.",
            "Diffondere indicazioni sanitarie basate sulle comunicazioni ufficiali.",
            "Valutare eventuali limitazioni alla circolazione.",
            "Informare i cittadini attraverso canali istituzionali."
        ]

    elif scenario_type == "terremoto":

        impacts = [
            {
                "area": "Edifici",
                "description": (
                    "Possibili danni strutturali, distacchi "
                    "e necessità di verifiche tecniche."
                ),
                "priority": "alta"
            },
            {
                "area": "Mobilità",
                "description": (
                    "Possibili interruzioni stradali e difficoltà "
                    "di accesso ai soccorsi."
                ),
                "priority": "alta"
            },
            {
                "area": "Servizi essenziali",
                "description": (
                    "Possibili interruzioni di elettricità, acqua "
                    "e telecomunicazioni."
                ),
                "priority": "alta"
            }
        ]

        affected_services = [
            "Protezione civile",
            "Servizi sanitari",
            "Vigili del fuoco",
            "Reti di distribuzione"
        ]

        actions = [
            "Verificare le comunicazioni ufficiali degli enti competenti.",
            "Valutare la necessità di verifiche tecniche sugli edifici.",
            "Verificare la percorribilità delle principali vie di accesso.",
            "Predisporre informazioni sui servizi essenziali disponibili.",
            "Diffondere esclusivamente indicazioni di sicurezza ufficiali."
        ]

    elif scenario_type == "mobilità":

        impacts = [
            {
                "area": "Traffico",
                "description": (
                    "Possibili code, congestione e aumento "
                    "dei tempi di percorrenza."
                ),
                "priority": "alta"
            },
            {
                "area": "Trasporto pubblico",
                "description": (
                    "Possibili ritardi e modifiche ai percorsi "
                    "dei mezzi pubblici."
                ),
                "priority": "media"
            }
        ]

        affected_services = [
            "Viabilità",
            "Trasporto pubblico",
            "Servizi di emergenza"
        ]

        actions = [
            "Individuare percorsi alternativi.",
            "Verificare eventuali limitazioni alla circolazione.",
            "Informare gli utenti del trasporto pubblico.",
            "Mantenere accessibili le vie per i mezzi di emergenza."
        ]

    else:

        impacts = [
            {
                "area": "Territorio",
                "description": (
                    "Gli effetti dipendono dalla natura, "
                    "dall'estensione e dalla durata dello scenario."
                ),
                "priority": "da valutare"
            }
        ]

        affected_services = [
            "Servizi comunali",
            "Protezione civile",
            "Servizi di emergenza"
        ]

        actions = [
            "Verificare la natura e l'estensione dello scenario.",
            "Individuare le persone e le infrastrutture potenzialmente coinvolte.",
            "Valutare le possibili conseguenze sui servizi essenziali.",
            "Definire le priorità di intervento con gli enti competenti."
        ]

    # -------------------------------------------------
    # RISULTATO
    # -------------------------------------------------

    return {
        "simulation_id": datetime.now(timezone.utc).strftime(
            "%Y%m%d%H%M%S%f"
        ),
        "type": "hypothetical_simulation",
        "label": "SIMULAZIONE IPOTETICA",
        "is_real_event": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "description": description,
            "location": location_name,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "category": scenario_type
        },
        "impacts": impacts,
        "affected_services": affected_services,
        "action_plan": actions,
        "limitations": [
            "Le conseguenze sono ipotesi e non previsioni certe.",
            "Non sono stati consultati dati in tempo reale.",
            "Non sono state verificate le condizioni effettive del territorio.",
            "Le decisioni operative spettano agli enti competenti."
        ]
    }
