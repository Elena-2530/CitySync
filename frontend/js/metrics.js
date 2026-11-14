/* NEURAPOLIS - confronto SENZA sistema / CON sistema.
   Sono numeri SIMULATI, calcolati dalle ipotesi in model.js: vanno presentati come tali. */
(function (NP) {
  const A = NP.assumptions, M = NP.model;

  NP.computeMetrics = function (history) {
    const step = NP.scenario.step;
    let minWithout = 0, minWith = 0, peakWithout = 0, peakWith = 0, sheltered = 0;

    history.forEach((h) => {
      const shuttle = h.recs.find((r) => r.key === "shuttle");
      const red = h.recs.find((r) => r.key === "cruise-redirect");
      let diverted = 0;
      if (shuttle && h.t >= shuttle.issuedAt + A.commsDelayMin) diverted += A.complianceRate * M.stranded(h.state, h.t);
      if (red && h.t >= red.issuedAt + A.commsDelayMin) {
        diverted += A.complianceRate * M.cruiseAshore(h.state, h.t) * A.cruiseShareInPortZone;
      }
      const without = h.crowd.porto;
      const withSys = Math.max(0, without - diverted);
      peakWithout = Math.max(peakWithout, without);
      peakWith = Math.max(peakWith, withSys);
      if (without > A.capacity.porto) minWithout += step;
      if (withSys > A.capacity.porto) minWith += step;
    });

    const last = history[history.length - 1];
    const red = last && last.recs.find((r) => r.key === "cruise-redirect");
    if (red && red.variant === "covered") sheltered = Math.round(A.complianceRate * red.data.toRedirect);

    return {
      cap: A.capacity.porto,
      peakWithout: Math.round(peakWithout), peakWith: Math.round(peakWith),
      minWithout, minWith,
      reactionWithout: A.operatorReactionWithoutSystemMin,
      reactionWith: A.operatorReactionWithSystemMin,
      sheltered
    };
  };
})((globalThis.NP = globalThis.NP || {}));
