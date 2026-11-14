/* NEURAPOLIS - livelli cartografici (statici e dinamici). */
(function (NP) {
  const map = NP.map, D = NP.data;
  const LEVEL_COLORS = ["#22c55e", "#eab308", "#f97316", "#ef4444"];
  const PRIORITY_COLORS = { 1: "#38bdf8", 2: "#f59e0b", 3: "#ef4444" };

  const layers = {
    transport: L.layerGroup(),
    tourism: L.layerGroup(),
    events: L.layerGroup(),
    recs: L.layerGroup(),
    weather: L.layerGroup(),
    fault: L.layerGroup() // vive dentro "transport"
  };

  // --- statici: linee e fermate (approssimate) ---
  L.polyline(D.linea1.map((s) => s.c), { color: "#ffee00", weight: 4, opacity: 0.8 }).bindPopup(" Linea 1 ").addTo(layers.transport);
  L.polyline(D.linea2.map((s) => s.c), { color: "#ff0000", weight: 4, opacity: 0.8 }).bindPopup(" Linea 6 ").addTo(layers.transport);
  const seen = new Set();
  D.linea1.concat(D.linea2).forEach((s) => {
    if (seen.has(s.name)) return;
    seen.add(s.name);
    L.circleMarker(s.c, { radius: 6, color: "#0284c7", fillColor: "#38bdf8", fillOpacity: 0.9 })
      .bindPopup(`<strong>${s.name}</strong><br>Fermata (posizione approssimativa)`).addTo(layers.transport);
  });
  layers.fault.addTo(layers.transport);

  D.pois.forEach((p) => {
    L.marker(p.c).bindPopup(`<strong>${p.name}</strong><br>Punto di interesse`).addTo(layers.tourism);
  });

  Object.values(layers).forEach((l) => { if (l !== layers.fault) l.addTo(map); });

  // --- dinamici ---
  layers.update = function (snap) {
    // punti caldi colorati per livello di affollamento
    layers.events.clearLayers();
    D.hotspots.forEach((h) => {
      const persons = snap.crowd[h.id];
      const cap = NP.assumptions.capacity[h.id];
      const lvl = NP.model.level(persons, cap);
      L.circle(h.c, { radius: h.radius, color: LEVEL_COLORS[lvl], fillColor: LEVEL_COLORS[lvl], fillOpacity: 0.28, weight: 2 })
        .bindPopup(`<strong>${h.label}</strong><br>~${persons} persone su capacità ${cap}<br>Livello: ${["normale", "attenzione", "alto", "critico"][lvl]}<br><em>Stima simulata</em>`)
        .addTo(layers.events);
    });

    // tratto guasto
    layers.fault.clearLayers();
    if (snap.state.metroFault) {
      L.polyline(D.faultSegment, { color: "#ef4444", weight: 7, dashArray: "8 8" })
        .bindPopup("<strong>Linea 1 interrotta</strong><br>Università – Municipio").addTo(layers.fault);
    }

    // meteo
    layers.weather.clearLayers();
    const rain = snap.messages.find((m) => m.id === "meteo:pioggia");
    if (rain) {
      const observed = rain.data.phase === "observed";
      L.circle(D.rainArea.c, {
        radius: D.rainArea.radius, color: "#3b82f6", weight: 1, dashArray: observed ? null : "6 6",
        fillColor: "#3b82f6", fillOpacity: observed ? 0.18 : 0.07, interactive: false
      }).addTo(layers.weather);
    }

    // raccomandazioni
    layers.recs.clearLayers();
    snap.recs.forEach((r) => drawRec(r));
  };


      // 1. Aggiunge il layer dei trasporti alla mappa all'avvio (coerente con il checkbox "checked" nell'HTML)
    layers.transport.addTo(map);

    // 2. Seleziona tutti i checkbox a cui abbiamo assegnato la classe 'layer-toggle'
    const layerCheckboxes = document.querySelectorAll('.layer-toggle');

    // 3. Aggiunge un "ascoltatore" di eventi a ciascun checkbox
    layerCheckboxes.forEach(checkbox => {
         
    document.addEventListener('change', function(event) {
        // Controlla se l'elemento modificato è uno dei nostri checkbox
        if (event.target && event.target.classList.contains('layer-toggle')) {
            const layerName = event.target.value;
            const targetLayer = layers[layerName];

            if (targetLayer) {
                if (event.target.checked) {
                    map.addLayer(targetLayer);
                } else {
                    map.removeLayer(targetLayer);
                }
            }
        }
    });

    });


  function drawRec(r) {
    const color = PRIORITY_COLORS[r.priority] || "#38bdf8";
    const g = r.geometry || {};
    (g.lines || []).forEach((ln) => {
      L.polyline(ln.pts, { color: "#22d3ee", weight: 5, opacity: 0.9, dashArray: "2 9" }).bindPopup(r.title).addTo(layers.recs);
    });
    (g.points || []).forEach((p) => {
      L.circleMarker(p.c, { radius: 9, color, fillColor: color, fillOpacity: 0.85, weight: 2 })
        .bindTooltip(p.label, { permanent: false }).bindPopup(`<strong>${r.title}</strong><br>${p.label}`).addTo(layers.recs);
    });
  }

  layers.focusRec = function (rec) {
    const pts = [];
    const g = rec.geometry || {};
    (g.lines || []).forEach((ln) => ln.pts.forEach((p) => pts.push(p)));
    (g.points || []).forEach((p) => pts.push(p.c));
    if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.4), { maxZoom: 15 });
  };

  NP.layers = layers;
})((globalThis.NP = globalThis.NP || {}));
