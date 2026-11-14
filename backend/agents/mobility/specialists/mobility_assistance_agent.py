
def generate_response(sender, question=None, traffic=None,
                      transport=None, routes=None, impact=None):
    """
    Prepara una risposta adeguata al destinatario.
    """

    sender = (sender or "user").lower()

    traffic = traffic or {}
    transport = transport or {}
    routes = routes or {}
    impact = impact or {}

    missing = []

    missing.extend(traffic.get("missing_information", []))
    missing.extend(transport.get("missing_information", []))
    missing.extend(routes.get("missing_information", []))

    missing = list(dict.fromkeys(missing))

    route = routes.get("recommended_route")

    if sender == "janara":
        response = (
            "Analisi della mobilità completata. "
            "Sono disponibili le valutazioni degli specialisti. "
            "Le informazioni mancanti e le verifiche necessarie "
            "sono riportate nell'analisi."
        )

    elif sender == "operator":
        response = (
            "Analisi della mobilità disponibile. "
            "È necessario valutare le criticità segnalate e "
            "completare le verifiche indicate prima di assumere "
            "decisioni operative."
        )

    else:
        if route:
            response = (
                "È disponibile un percorso suggerito. "
                "Prima di utilizzarlo, verifica che le condizioni "
                "e i servizi indicati siano aggiornati."
            )
        else:
            response = (
                "Al momento non dispongo di informazioni sufficienti "
                "per indicarti un percorso verificato. "
                "Non voglio fornirti indicazioni non attendibili."
            )

    return {
        "recipient": sender,
        "question": question,
        "response": response,
        "missing_information": missing,
        "possible_impacts": impact.get("possible_impacts", [])
    }
