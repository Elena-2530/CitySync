/* NEURAPOLIS - scenario della demo e motore di simulazione. */
(function (NP) {
  const S = (NP.scenario = {
    title: "Sabato pomeriggio a Napoli: crociere + partita + guasto metro + pioggia",
    start: 930, // 15:30
    end: 1110, // 18:30
    step: 10,
    events: [
      {
        at: 930, id: "cruise",
        label: "Arrivano 2 navi da crociera (circa 5.200 passeggeri) alla Stazione Marittima",
        apply: (s) => { s.cruise = { pax: 5200, arrive: 930 }; }
      },
      {
        at: 960, id: "match",
        label: "Partita al Maradona (42.000 spettatori, calcio d'inizio 18:00): inizia l'afflusso",
        apply: (s) => { s.match = { attendance: 42000, inflowStart: 960, kickoff: 1080 }; }
      },
      {
        at: 980, id: "metro",
        label: "Guasto sulla Linea 1 tra Università e Municipio",
        apply: (s) => { s.metroFault = { since: 980 }; }
      },
      {
        at: 1020, id: "rain",
        label: "Allerta meteo: pioggia intensa prevista dalle 17:20",
        apply: (s) => { s.rain = { alertAt: 1020, onset: 1040 }; }
      }
    ],
    stateAt(t) {
      const s = {};
      S.events.forEach((e) => { if (e.at <= t) e.apply(s); });
      return s;
    }
  });

  function Simulation() { this.reset(); }

  Simulation.prototype.reset = function () {
    this.t = null;
    this.history = [];
    this.orch = new NP.Orchestrator();
    this.finished = false;
  };

  // Avanza di un passo e restituisce lo snapshot, oppure null se finita.
  Simulation.prototype.step = function () {
    if (this.finished) return null;
    this.t = this.t === null ? S.start : this.t + S.step;
    const t = this.t;
    const state = S.stateAt(t);

    S.events.filter((e) => e.at === t).forEach((e) => {
      this.orch.log.push({ t, type: "event", text: e.label });
    });

    const messages = NP.runAgents(state, t);
    const crowd = NP.model.crowd(state, t);
    const recs = this.orch.run(state, t, messages);

    const snap = {
      t, state, messages, crowd,
      recs: recs.map((r) => Object.assign({}, r)),
      log: this.orch.log.slice(),
      activeEvents: S.events.filter((e) => e.at <= t).length
    };
    this.history.push(snap);
    if (t >= S.end) this.finished = true;
    return snap;
  };

  NP.Simulation = Simulation;
})((globalThis.NP = globalThis.NP || {}));
