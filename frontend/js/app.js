/* NEURAPOLIS - interfaccia: controlli, pannelli, ciclo di simulazione. */
(function (NP) {
  const $ = (id) => document.getElementById(id);
  const sim = new NP.Simulation();
  let timer = null;
  let lastSnap = null;
  const openKeys = new Set();
  const explanations = {};

  const PRIORITY_LABEL = { 3: "P1 · CRITICA", 2: "P2 · ALTA", 1: "P3" };

  // --- filtri cartografici ---
  function toggle(id, layer) {
    $(id).addEventListener("change", (e) => {
      if (e.target.checked) layer.addTo(NP.map); else NP.map.removeLayer(layer);
    });
  }
  toggle("transport-toggle", NP.layers.transport);
  toggle("tourism-toggle", NP.layers.tourism);
  toggle("events-toggle", NP.layers.events);
  toggle("recs-toggle", NP.layers.recs);
  toggle("weather-toggle", NP.layers.weather);

  // --- rendering ---
  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function renderRecs(snap) {
    const el = $("rec-list");
    if (!snap.recs.length) {
      el.innerHTML = '<p class="empty-message">Nessuna raccomandazione: la situazione è sotto controllo.</p>';
      return;
    }
    el.innerHTML = snap.recs.map((r) => {
      const k = r.key + ":" + r.variant;
      const badge = r.status === "new" ? '<span class="badge b-new">NUOVA</span>'
        : r.status === "revised" ? `<span class="badge b-rev">RIVISTA ${NP.fmtTime(r.revisedAt)}</span>`
        : r.revisions ? `<span class="badge b-rev">RIVISTA ${NP.fmtTime(r.revisedAt)}</span>` : "";
      return `
      <div class="rec p${r.priority}" data-key="${r.key}">
        <div class="rec-top"><span class="badge b-p${r.priority}">${PRIORITY_LABEL[r.priority]}</span>${badge}</div>
        <strong>${esc(r.title)}</strong>
        <details data-k="${k}" ${openKeys.has(k) ? "open" : ""}>
          <summary>Perché?</summary>
          <ul>${r.rationale.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        </details>
        <button class="explain" data-key="${r.key}">Spiega con l'assistente</button>
        <div class="explain-out">${explanations[k] ? esc(explanations[k]) : ""}</div>
      </div>`;
    }).join("");
  }

  function renderBoard(snap) {
    const el = $("board");
    if (!snap.messages.length) { el.innerHTML = '<p class="empty-message">Nessun segnale dagli agenti.</p>'; return; }
    el.innerHTML = snap.messages.slice().sort((a, b) => b.severity - a.severity).map((m) => `
      <div class="msg sev${m.severity}">
        <div class="msg-top"><b>${NP.agentLabels[m.agent]}</b>
          <span class="badge ${m.status === "confirmed" ? "b-ok" : "b-est"}">${m.status === "confirmed" ? "confermato" : "stima"} ${Math.round(m.confidence * 100)}%</span>
        </div>
        <p>${esc(m.text)}</p>
      </div>`).join("");
  }

  function renderLog(snap) {
    const icon = { event: "●", decision: "▶", revision: "↻", closed: "✓" };
    $("log").innerHTML = snap.log.slice().reverse().map((l) =>
    `<div class="log-line ${l.type}"><span>${NP.fmtTime(l.t)}</span><span>${icon[l.type] || ""}</span><p>${esc(l.text)}</p></div>`
    ).join("");
}

  function renderMetrics() {
    const el = $("metrics");
    if (!sim.finished) { el.innerHTML = '<p class="empty-message">I risultati compaiono a fine scenario (18:30).</p>'; return; }
    const m = NP.computeMetrics(sim.history);
    el.innerHTML = `
      <table class="mtable">
        <tr><th></th><th>Senza</th><th>Con</th></tr>
        <tr><td>Picco persone zona porto (capacità ${m.cap})</td><td>${m.peakWithout}</td><td>${m.peakWith}</td></tr>
        <tr><td>Minuti sopra capacità</td><td>${m.minWithout}</td><td>${m.minWith}</td></tr>
        <tr><td>Reazione operatore (min)</td><td>${m.reactionWithout}</td><td>${m.reactionWith}</td></tr>
      </table>
      <p class="note">Persone smistate verso rifugi coperti: circa ${m.sheltered}. Valori SIMULATI dalle ipotesi sotto, non misure reali.</p>`;
  }

  function render(snap) {
    lastSnap = snap;
    $("clock").textContent = NP.fmtTime(snap.t);
    $("event-count").textContent = snap.activeEvents;
    $("alert-count").textContent = snap.recs.filter((r) => r.priority === 3).length;
    $("rec-count").textContent = snap.recs.length;
    renderRecs(snap);
    renderBoard(snap);
    renderLog(snap);
    renderMetrics();
    NP.layers.update(snap);
  }

  // --- controlli ---
  function stepOnce() {
    const snap = sim.step();
    if (snap) render(snap);
    if (sim.finished) stop();
  }

  function speedMs() { return Number($("speed").value); }

  function play() {
    if (sim.finished) reset();
    stop();
    $("btn-play").textContent = "⏸ Pausa";
    stepOnce();
    timer = setInterval(stepOnce, speedMs());
  }

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    $("btn-play").textContent = sim.finished ? "↺ Riavvia" : "▶ Avvia scenario";
  }

  function reset() {
    stop();
    sim.reset();
    openKeys.clear();
    Object.keys(explanations).forEach((k) => delete explanations[k]);
    $("btn-play").textContent = "▶ Avvia scenario";
    $("clock").textContent = NP.fmtTime(NP.scenario.start);
    $("event-count").textContent = "0";
    $("alert-count").textContent = "0";
    $("rec-count").textContent = "0";
    $("rec-list").innerHTML = '<p class="empty-message">Avvia lo scenario per vedere le raccomandazioni.</p>';
    $("board").innerHTML = '<p class="empty-message">Nessun segnale dagli agenti.</p>';
    $("log").innerHTML = "";
    renderMetrics();
    NP.layers.update({ crowd: { porto: 0, stadio: 0, centro: 0 }, state: {}, messages: [], recs: [] });
  }

  $("btn-play").addEventListener("click", () => { if (timer) stop(); else play(); });
  $("btn-step").addEventListener("click", () => { stop(); if (sim.finished) reset(); stepOnce(); });
  $("btn-reset").addEventListener("click", reset);
  $("speed").addEventListener("change", () => { if (timer) { clearInterval(timer); timer = setInterval(stepOnce, speedMs()); } });

  // elenco raccomandazioni: apri/chiudi "Perché?", spiegazione LLM, zoom sulla mappa
  $("rec-list").addEventListener("toggle", (e) => {
    const d = e.target;
    if (d.dataset && d.dataset.k) { if (d.open) openKeys.add(d.dataset.k); else openKeys.delete(d.dataset.k); }
  }, true);

  $("rec-list").addEventListener("click", async (e) => {
    const card = e.target.closest(".rec");
    if (!card || !lastSnap) return;
    const rec = lastSnap.recs.find((r) => r.key === card.dataset.key);
    if (!rec) return;
    if (e.target.classList.contains("explain")) {
      const out = card.querySelector(".explain-out");
      out.textContent = "Elaborazione…";
      const res = await NP.llm.explain(rec);
      explanations[rec.key + ":" + rec.variant] = res.text + " (" + res.source + ")";
      out.textContent = explanations[rec.key + ":" + rec.variant];
    } else if (!e.target.closest("details")) {
      NP.layers.focusRec(rec);
    }
  });

  // chiave Gemini (resta solo nel browser)
  $("llm-key").value = NP.llm.getKey();
  $("llm-key").addEventListener("change", (e) => NP.llm.setKey(e.target.value));

  // ipotesi
  $("assumptions").innerHTML = "<ul>" + NP.assumptionLabels.map(([k, label]) =>
    `<li>${label}: <b>${NP.assumptions[k]}</b></li>`).join("") + "</ul>" +
    "<p class='note'>Dati geografici e numeri di folla/guasto sono simulati. Le coordinate delle fermate sono approssimate.</p>";

  $("scenario-title").textContent = NP.scenario.title;
  reset();
})((globalThis.NP = globalThis.NP || {}));
