/* NEURAPOLIS - orchestratore.
   Legge la bacheca degli agenti, risolve i conflitti, produce raccomandazioni
   spiegate e le REVISIONA quando le condizioni cambiano. */
(function (NP) {
  const A = NP.assumptions, M = NP.model, D = NP.data, fmt = NP.fmtTime;

  function cite(m) {
    const who = NP.agentLabels[m.agent];
    const st = m.status === "confirmed" ? "confermato" : "stima";
    return `[${who} · ${st} ${Math.round(m.confidence * 100)}%] ${m.text}`;
  }

  function allocateShelters(total) {
    const sh = D.shelters;
    const capSum = sh.reduce((a, s) => a + s.capacity, 0);
    return sh.map((s) => ({
      name: s.name, c: s.c,
      n: Math.min(s.capacity, Math.round((total * s.capacity) / capSum / 10) * 10)
    }));
  }

  function Orchestrator() {
    this.plan = {};
    this.log = [];
  }

  Orchestrator.prototype.run = function (state, t, messages) {
    const by = (id) => messages.find((m) => m.id === id);
    const desired = [];

    const fault = by("mobilita:guasto");
    const stadTrans = by("mobilita:stadio");
    const porto = by("folla:porto");
    const stadio = by("folla:stadio");
    const rain = by("meteo:pioggia");

    // R1 - guasto metro: navette
    if (fault) {
      const why = [cite(fault)];
      if (porto) why.push(cite(porto));
      why.push(`Calcolo: ${fault.data.buses} bus da ${A.busCapacity} posti con 3 corse in 30 minuti smaltiscono circa ${fault.data.buses * A.busCapacity * 3} persone.`);
      desired.push({
        key: "shuttle", variant: "v1", priority: 3,
        title: `Attivare ${fault.data.buses} bus navetta Municipio ↔ Garibaldi`,
        rationale: why, sources: [fault.id].concat(porto ? [porto.id] : []),
        geometry: { lines: [{ pts: D.shuttleRoute, style: "rec" }] }, data: {}
      });
    }

    // R2 - zona porto affollata con croceristi: scegliere il percorso, tenendo conto del meteo
    if (porto && porto.severity >= 2 && state.cruise) {
      const toRedirect = Math.round(M.cruiseAshore(state, t) * A.cruiseShareInPortZone / 10) * 10;
      if (rain) {
        const alloc = allocateShelters(toRedirect);
        const why = [cite(porto), cite(rain),
          "Conflitto risolto: il percorso all'aperto verso Plebiscito e lungomare è in contrasto con la previsione di pioggia. Priorità a sicurezza e comfort dei visitatori."];
        alloc.forEach((a) => why.push(`Smistamento: circa ${a.n} persone verso ${a.name}.`));
        desired.push({
          key: "cruise-redirect", variant: "covered", priority: 3,
          title: `Dirottare circa ${toRedirect} croceristi verso percorsi coperti`,
          rationale: why, sources: [porto.id, rain.id],
          geometry: {
            lines: alloc.map((a) => ({ pts: [D.hotspots[0].c, a.c], style: "rec" })),
            points: alloc.map((a) => ({ c: a.c, label: `${a.name}: ~${a.n}` }))
          },
          data: { toRedirect }
        });
      } else {
        desired.push({
          key: "cruise-redirect", variant: "open", priority: 3,
          title: "Indirizzare i croceristi verso Plebiscito e il lungomare (a piedi)",
          rationale: [cite(porto), "Nessuna criticità meteo segnalata: il percorso pedonale verso Plebiscito disperde la folla senza usare la metro."],
          sources: [porto.id],
          geometry: { lines: [{ pts: D.openRoute, style: "rec" }] }, data: { toRedirect }
        });
      }
    }

    // R3 - stadio: rinforzi
    if (stadio) {
      const why = [cite(stadio)];
      if (stadTrans) why.push(cite(stadTrans));
      const cross = !!state.metroFault;
      if (cross) why.push("Dipendenza tra agenti: il guasto della Linea 1 porta persone a Garibaldi, nodo della Linea 2 usata anche per lo stadio.");
      desired.push({
        key: "stadium", variant: "v1", priority: cross || stadio.severity >= 2 ? 3 : 2,
        title: "Rinforzare Linea 2 e Cumana e aprire varchi pedonali allo stadio",
        rationale: why, sources: [stadio.id].concat(stadTrans ? [stadTrans.id] : []),
        geometry: { points: [{ c: D.hotspots[1].c, label: "Stadio" }, { c: D.linea2[4].c, label: "Campi Flegrei" }] }, data: {}
      });
    }

    // R4 - meteo: avviso ai visitatori
    if (rain) {
      desired.push({
        key: "weather-notice", variant: "v1", priority: 2,
        title: rain.data.phase === "forecast"
          ? `Avviso a cittadini e turisti: pioggia in arrivo alle ${fmt(rain.data.onset)}`
          : "Avviso a cittadini e turisti: pioggia in corso, usare i rifugi al coperto",
        rationale: [cite(rain), "Rifugi al coperto disponibili: " + D.shelters.map((s) => s.name).join(", ") + "."],
        sources: [rain.id],
        geometry: { points: D.shelters.map((s) => ({ c: s.c, label: s.name })) }, data: {}
      });
    }

    this.reconcile(desired, t, rain);
    return Object.values(this.plan).sort((a, b) => b.priority - a.priority || a.issuedAt - b.issuedAt);
  };

  Orchestrator.prototype.reconcile = function (desired, t, rain) {
    const keys = desired.map((d) => d.key);

    desired.forEach((d) => {
      const prev = this.plan[d.key];
      if (!prev) {
        this.plan[d.key] = Object.assign({}, d, { issuedAt: t, status: "new", revisedAt: null, revisions: 0 });
        this.log.push({ t, type: "decision", text: `Nuova raccomandazione: ${d.title}` });
      } else if (prev.variant !== d.variant) {
        this.plan[d.key] = Object.assign({}, d, {
          issuedAt: prev.issuedAt, status: "revised", revisedAt: t, revisions: prev.revisions + 1
        });
        const reason = rain
          ? `L'agente Meteo segnala pioggia (confidenza ${Math.round(rain.confidence * 100)}%): il piano precedente "${prev.title}" non è più adeguato.`
          : "Le condizioni sono cambiate.";
        this.log.push({ t, type: "revision", text: `REVISIONE: ${reason} Nuova decisione: ${d.title}` });
      } else {
        this.plan[d.key] = Object.assign({}, d, {
          issuedAt: prev.issuedAt, status: prev.revisedAt === t ? "revised" : "active",
          revisedAt: prev.revisedAt, revisions: prev.revisions
        });
      }
    });

    Object.keys(this.plan).forEach((k) => {
      if (!keys.includes(k)) {
        this.log.push({ t, type: "closed", text: `Raccomandazione chiusa: ${this.plan[k].title}` });
        delete this.plan[k];
      }
    });
  };

  NP.Orchestrator = Orchestrator;
})((globalThis.NP = globalThis.NP || {}));
