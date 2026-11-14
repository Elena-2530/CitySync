/* NEURAPOLIS - modello di simulazione e ipotesi dichiarate.
   Tutto vive dentro il namespace globale NP, così nessun file ridichiara
   variabili degli altri (era il bug: "const map" in tre file diversi). */
(function (NP) {
  NP.fmtTime = function (m) {
    const h = Math.floor(m / 60), mm = m % 60;
    return String(h).padStart(2, "0") + ":" + String(mm).padStart(2, "0");
  };

  // IPOTESI: sono numeri inventati ma dichiarati. Mostrali nella slide "Ipotesi".
  const A = (NP.assumptions = {
    cruiseDisembarkMin: 90,          // minuti per sbarcare tutti i croceristi
    cruiseShareInPortZone: 0.35,     // quota di croceristi nella zona porto in ogni momento
    cruiseShareInCentro: 0.3,        // quota che si sposta verso il centro storico
    metroStrandedPerMin: 60,         // persone/min che restano a terra per il guasto
    strandedCap: 4000,               // massimo di persone accumulate in zona Municipio
    stadiumRampMin: 120,             // l'afflusso allo stadio dura 2 ore prima del calcio d'inizio
    stadiumZoneShare: 0.7,           // quota di spettatori presenti nell'area stadio
    capacity: { porto: 3000, stadio: 30000, centro: 4000 },
    busCapacity: 80,                 // passeggeri per bus navetta
    complianceRate: 0.4,             // quota di persone che segue davvero l'indicazione
    commsDelayMin: 5,                // minuti per far arrivare l'indicazione alle persone
    operatorReactionWithoutSystemMin: 12, // operatore che raccoglie dati da sistemi separati
    operatorReactionWithSystemMin: 1      // operatore che legge la raccomandazione
  });

  NP.assumptionLabels = [
    ["cruiseDisembarkMin", "Durata sbarco croceristi (min)"],
    ["cruiseShareInPortZone", "Quota croceristi in zona porto"],
    ["metroStrandedPerMin", "Persone/min bloccate dal guasto Linea 1"],
    ["strandedCap", "Massimo di persone bloccate"],
    ["stadiumZoneShare", "Quota spettatori in area stadio"],
    ["busCapacity", "Passeggeri per bus navetta"],
    ["complianceRate", "Quota che segue l'indicazione"],
    ["commsDelayMin", "Ritardo di comunicazione (min)"],
    ["operatorReactionWithoutSystemMin", "Reazione operatore SENZA sistema (min)"],
    ["operatorReactionWithSystemMin", "Reazione operatore CON sistema (min)"]
  ];

  function ramp(x, d) {
    return Math.max(0, Math.min(1, x / d));
  }

  NP.model = {
    ramp,
    stranded(state, t) {
      if (!state.metroFault) return 0;
      return Math.min(A.strandedCap, A.metroStrandedPerMin * Math.max(0, t - state.metroFault.since));
    },
    cruiseAshore(state, t) {
      if (!state.cruise) return 0;
      return state.cruise.pax * ramp(t - state.cruise.arrive, A.cruiseDisembarkMin);
    },
    // Persone presenti nei tre punti caldi SENZA alcun intervento.
    crowd(state, t) {
      const ashore = NP.model.cruiseAshore(state, t);
      const stranded = NP.model.stranded(state, t);
      const porto = Math.round(ashore * A.cruiseShareInPortZone + stranded);
      const stadio = state.match
        ? Math.round(state.match.attendance * A.stadiumZoneShare * ramp(t - state.match.inflowStart, A.stadiumRampMin))
        : 0;
      const centro = Math.round(2000 + ashore * A.cruiseShareInCentro);
      return { porto, stadio, centro };
    },
    // 0 normale, 1 attenzione, 2 alto, 3 critico
    level(persons, cap) {
      const r = persons / cap;
      return r < 0.6 ? 0 : r < 0.9 ? 1 : r < 1.2 ? 2 : 3;
    }
  };
})((globalThis.NP = globalThis.NP || {}));
