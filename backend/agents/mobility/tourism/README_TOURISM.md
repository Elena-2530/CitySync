# Tourism Agent

Agente di NEURAPOLIS che risponde a Janara, operatori e utenti su monumenti e musei di Napoli:
dove si trovano, storia, orari, prezzi, cosa vedere nei dintorni e cosa fare se piove.
Usa regole esplicite (nessun modello AI) e **dichiara sempre cosa non sa**.

## Come si usa

```python
from agents.tourism.tourism_agent import analyze_tourism_request

risultato = analyze_tourism_request({
    "request_id": "R1",
    "sender": "user",                # janara | user | operator
    "request_type": "question",      # question | place_info | search | nearby
    "question": "Quando apre il Castel Nuovo?",
    "context": {}                    # vedi sotto
})
print(risultato["response"]["response"])
```

`context` (tutti opzionali): `place`, `location` (nome di zona/luogo oppure `{"lat":..,"lon":..}`),
`category` (museum, castle, church, palace, theatre, square, street, panorama, seafront),
`when` (data/ora ISO), `weather` ("rain"), `radius_m`, `limit`, `origin`.

Altri campi del risultato: `places` (schede dei luoghi), `confidence`, `missing_information`,
`required_checks`, `suggested_handoffs` (per chiamare il Mobility Agent), `limitations`.

Esempi pronti: `python -m agents.tourism.tourism_agent` (dalla cartella `backend`).
Test: `python -m pytest agents/tourism/tests -q`.

## Dati (`tourism_data/places_napoli.json`)

13 luoghi e 8 zone. Descrizioni, indirizzi e coordinate sono di conoscenza generale (coordinate **approssimate**).
Gli orari sono riportati **solo se trovati in una fonte**, con tipo di fonte e data (controllati il 14/11/2026):

| Luogo | Orari | Affidabilità |
|---|---|---|
| Castel Nuovo | Comune di Napoli, agg. 20/10/2026 | alta |
| Palazzo Reale, Duomo | fonte ufficiale, senza data | media |
| MANN, Cappella Sansevero, Certosa di San Martino | elenco di musei non ufficiale, 2024 | bassa (datati) |
| Castel dell'Ovo, Teatro di San Carlo | nessuna fonte affidabile | assente: l'agente dice che non lo sa |
| Piazze, strade, lungomare | luoghi all'aperto | nessun orario |

Prima della consegna conviene **verificare sui siti ufficiali** MANN, Sansevero e Certosa e aggiornare il file:
cambiare `status` in `official`, `source.type`, `source.url` e `source.as_of`.

## Regole di progetto

- Mai un orario o un prezzo senza fonte; se la fonte è non ufficiale o datata, l'agente lo dice.
- Un luogo non presente nei dati viene dichiarato, mai indovinato.
- Per i percorsi non risponde: restituisce in `suggested_handoffs` una richiesta pronta per il Mobility Agent.
- Con la pioggia propone solo luoghi al coperto e segnala quelli chiusi a quell'ora.
