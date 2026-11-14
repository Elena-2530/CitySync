/* NEURAPOLIS - agenti specializzati.
   Ogni agente è una funzione che legge lo stato e scrive messaggi strutturati
   sulla "bacheca". Nessuno inventa dati: calcolano da modello e fonti. */
(function (NP) {
  const A = NP.assumptions, M = NP.model, D = NP.data, fmt = NP.fmtTime;

  const LEVELS = ["normale", "attenzione", "alto", "critico"];

  function mk(m) {
    m.status = m.confidence >= 0.8 ? "confirmed" : "estimate";
    return m;
  }

  function mobilityAgent(state, t) {
    const out = [];
    if (state.metroFault) {
      const stranded = M.stranded(state, t);
      const buses = Math.max(2, Math.ceil(stranded / (A.busCapacity * 3)));
      out.push(mk({
        id: "mobilita:guasto", agent: "mobilita", t, kind: "disruption",
        severity: stranded >= 2400 ? 3 : 2, confidence: 0.95,
        title: "Linea 1 interrotta tra Università e Municipio",
        text: `Linea 1 interrotta tra Università e Municipio dalle ${fmt(state.metroFault.since)}; circa ${Math.round(stranded)} persone bloccate o deviate (stima).`,
        data: { stranded, buses },
        geometry: { lines: [{ pts: D.faultSegment, style: "fault" }] }
      }));
    }
    if (state.match) {
      const c = M.crowd(state, t);
      const lvl = M.level(c.stadio, A.capacity.stadio);
      if (lvl >= 1) {
        const hub = !!state.metroFault;
        out.push(mk({
          id: "mobilita:stadio", agent: "mobilita", t, kind: "load", severity: hub ? Math.max(lvl, 2) : lvl,
          confidence: 0.7,
          title: "Carico trasporti verso lo stadio",
          text: `Afflusso allo stadio in crescita (circa ${c.stadio} persone nell'area): Linea 2 e Cumana sono le alternative principali.` +
            (hub ? " Il guasto sulla Linea 1 scarica passeggeri sul nodo di Garibaldi, da cui parte la Linea 2." : ""),
          data: { hubLoad: hub },
          geometry: { points: [{ c: D.linea2[4].c, label: "Campi Flegrei (Linea 2)" }] }
        }));
      }
    }
    return out;
  }

  function crowdAgent(state, t) {
    const c = M.crowd(state, t);
    const out = [];
    D.hotspots.forEach((h) => {
      const persons = c[h.id];
      const cap = A.capacity[h.id];
      const lvl = M.level(persons, cap);
      if (lvl >= 1) {
        out.push(mk({
          id: "folla:" + h.id, agent: "folla", t, kind: "crowd", severity: lvl, confidence: h.sensor,
          title: `Affollamento ${h.label}: ${LEVELS[lvl]}`,
          text: `${h.label}: circa ${persons} presenti su una capacità di ${cap} (${Math.round((persons / cap) * 100)}%).`,
          data: { persons, cap, level: lvl },
          geometry: { circles: [{ c: h.c, radius: h.radius }] }
        }));
      }
    });
    return out;
  }

  function weatherAgent(state, t) {
    const r = state.rain;
    if (!r || t < r.alertAt) return [];
    const phase = t < r.onset ? "forecast" : "observed";
    const mins = r.onset - t;
    return [mk({
      id: "meteo:pioggia", agent: "meteo", t, kind: phase, severity: phase === "forecast" ? 2 : 3,
      confidence: phase === "forecast" ? 0.8 : 0.95,
      title: phase === "forecast" ? "Pioggia intensa in arrivo" : "Pioggia intensa in corso",
      text: phase === "forecast"
        ? `Pioggia intensa prevista alle ${fmt(r.onset)} (tra ${mins} min). Percorsi all'aperto e lungomare a rischio.`
        : `Pioggia intensa in corso dalle ${fmt(r.onset)}. Percorsi all'aperto e lungomare sconsigliati.`,
      data: { phase, onset: r.onset },
      geometry: { circles: [{ c: D.rainArea.c, radius: D.rainArea.radius, style: "rain" }] }
    })];
  }

  NP.agentLabels = { mobilita: "Mobilità", folla: "Folla ed eventi", meteo: "Meteo e rischio" };

  NP.runAgents = function (state, t) {
    return [].concat(mobilityAgent(state, t), crowdAgent(state, t), weatherAgent(state, t));
  };
})((globalThis.NP = globalThis.NP || {}));
