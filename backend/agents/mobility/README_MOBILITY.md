# Mobility Agent

Agente di NEURAPOLIS che analizza segnalazioni di mobilità e risponde a Janara, operatori e utenti.
Usa solo regole esplicite (nessun modello AI) e **dichiara sempre cosa non sa**.

## Come si usa

```python
from agents.mobility.mobility_agent import analyze_mobility_request

risultato = analyze_mobility_request({
    "request_id": "R1",
    "sender": "janara",              # janara | operator | user
    "request_type": "incident_analysis",   # incident_analysis | route_request | question
    "question": None,
    "incident": {"id": 15, "description": "...", "location": "Fuorigrotta, Napoli",
                 "verification_status": "unverified"},   # campi della tabella incidents
    "context": {}
})
print(risultato["response"]["response"])   # testo per il destinatario
```

Altri campi del risultato: `problem_type`, `action_plan`, `missing_information`, `required_checks`,
`confidence` (livello e motivi), `specialist_analyses`, `route_plan`, `limitations`.

Esempi pronti: `python -m agents.mobility.mobility_agent` (dalla cartella `backend`).
Test: `python -m pytest agents/mobility/tests -q`.

## Dati

| Cosa | Stato |
|---|---|
| Rete di trasporto | **Dimostrativa** (`mobility_data/network_demo.json`: 3 linee, 12 fermate). Non è la rete reale. |
| Traffico in tempo reale | **Non disponibile**: l'agente lo dice e non lo inventa. |
| Interruzioni e ritardi | Arrivano dal chiamante in `context["transport_data"]["services"]`. |

### Usare un feed GTFS reale (per esempio EAV)

1. Scaricare il GTFS e decomprimerlo in una cartella (deve contenere `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`).
2. PowerShell: `$env:NEURAPOLIS_GTFS_DIR="C:\percorso\gtfs"`, poi avviare Python nello stesso terminale.
3. L'agente usa il GTFS al posto della rete dimostrativa. Gli orari GTFS sono **programmati**, non in tempo reale.

## Regole di progetto

- Una segnalazione non verificata resta "ipotesi": l'affidabilità non è mai alta.
- Percorsi e tempi sono stime sulla rete programmata e portano sempre l'avvertenza.
- Un luogo non riconosciuto viene dichiarato, mai indovinato.
- L'agente non decide chiusure o deviazioni: suggerisce verifiche e alternative.
