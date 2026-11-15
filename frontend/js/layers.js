
/* CitySync - gestione dei livelli cartografici */
(function (NP) {
  const map = NP.map;
  const D = NP.data;

  const LEVEL_COLORS = ["#22c55e", "#eab308", "#f97316", "#ef4444"];
  const PRIORITY_COLORS = {
    1: "#38bdf8",
    2: "#f59e0b",
    3: "#ef4444"
  };

  // Creazione dei livelli
  const layers = {
    transport: L.layerGroup(),
    tourism: L.layerGroup(),
    events: L.layerGroup(),
    recs: L.layerGroup(),
    weather: L.layerGroup(),
    fault: L.layerGroup()
  };

  // -----------------------------
  // TRASPORTI
  // -----------------------------

  L.polyline(
    D.linea1.map(s => s.c),
    { color: "#ffee00", weight: 4, opacity: 0.9 }
  )
    .bindPopup("Metro Linea 1 - percorso dimostrativo")
    .addTo(layers.transport);

  L.polyline(
    D.linea2.map(s => s.c),
    { color: "#ff0000", weight: 4, opacity: 0.9 }
  )
    .bindPopup("Metro Linea 2 - percorso dimostrativo")
    .addTo(layers.transport);

  const seen = new Set();

  D.linea1.concat(D.linea2).forEach(s => {
    if (seen.has(s.name)) return;

    seen.add(s.name);

    L.circleMarker(s.c, {
      radius: 6,
      color: "#0284c7",
      fillColor: "#38bdf8",
      fillOpacity: 0.9
    })
      .bindPopup(
        `<strong>${s.name}</strong><br>Fermata - posizione approssimativa`
      )
      .addTo(layers.transport);
  });

  // Il livello guasti è contenuto nel livello trasporti
  layers.fault.addTo(layers.transport);

  // -----------------------------
  // TURISMO E PUNTI DI INTERESSE
  // -----------------------------

  D.pois.forEach(p => {
    L.marker(p.c)
      .bindPopup(`<strong>${p.name}</strong><br>Punto di interesse`)
      .addTo(layers.tourism);
  });

  // -----------------------------
  // VISIBILITÀ DEI LIVELLI
  // -----------------------------

  const layerControls = [
    {
      id: "chk-mobilita",
      name: "transport",
      defaultVisible: true
    },
    {
      id: "chk-turismo",
      name: "tourism",
      defaultVisible: false
    },
    {
      id: "chk-affollamento",
      name: "events",
      defaultVisible: false
    },
    {
      id: "chk-meteo",
      name: "weather",
      defaultVisible: false
    }
  ];

  layerControls.forEach(control => {
    const checkbox = document.getElementById(control.id);

    if (!checkbox) {
      console.warn(
        `CitySync: checkbox non trovato: ${control.id}`
      );

      return;
    }

    const layer = layers[control.name];

    // Imposta la visibilità iniziale in base al checkbox
    if (checkbox.checked) {
      map.addLayer(layer);
    } else {
      map.removeLayer(layer);
    }

    // Aggiorna la mappa quando cambia la selezione
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        map.addLayer(layer);
      } else {
        map.removeLayer(layer);
      }
    });
  });

  // -----------------------------
  // AGGIORNAMENTO DEI DATI DINAMICI
  // -----------------------------

  layers.update = function (snap) {
    if (!snap) return;

    // Affollamento
    if (NP.model && NP.assumptions && snap.crowd) {
      layers.events.clearLayers();

      D.hotspots.forEach(h => {
        const persons = snap.crowd[h.id];
        const capacity = NP.assumptions.capacity[h.id];

        if (persons === undefined || capacity === undefined) return;

        const level = NP.model.level(persons, capacity);

        L.circle(h.c, {
          radius: h.radius,
          color: LEVEL_COLORS[level],
          fillColor: LEVEL_COLORS[level],
          fillOpacity: 0.28,
          weight: 2
        })
          .bindPopup(
            `<strong>${h.label}</strong><br>` +
            `~${persons} persone su capacità ${capacity}<br>` +
            `Livello: ${["normale", "attenzione", "alto", "critico"][level]}<br>` +
            `<em>Stima simulata</em>`
          )
          .addTo(layers.events);
      });
    }

    // Guasti ai trasporti
    layers.fault.clearLayers();

    if (snap.state && snap.state.metroFault) {
      L.polyline(D.faultSegment, {
        color: "#ef4444",
        weight: 7,
        dashArray: "8 8"
      })
        .bindPopup("<strong>Linea 1 interrotta</strong><br>Università – Municipio")
        .addTo(layers.fault);
    }

    // Meteo
    layers.weather.clearLayers();

    const messages = snap.messages || [];
    const rain = messages.find(m => m.id === "meteo:pioggia");

    if (rain) {
      const observed = rain.data.phase === "observed";

      L.circle(D.rainArea.c, {
        radius: D.rainArea.radius,
        color: "#3b82f6",
        weight: 1,
        dashArray: observed ? null : "6 6",
        fillColor: "#3b82f6",
        fillOpacity: observed ? 0.18 : 0.07,
        interactive: false
      }).addTo(layers.weather);
    }

    // Raccomandazioni
    layers.recs.clearLayers();

    (snap.recs || []).forEach(r => drawRec(r));
  };

  // -----------------------------
  // DISEGNO DELLE RACCOMANDAZIONI
  // -----------------------------

  function drawRec(r) {
    const color = PRIORITY_COLORS[r.priority] || "#38bdf8";
    const geometry = r.geometry || {};

    (geometry.lines || []).forEach(line => {
      L.polyline(line.pts, {
        color: "#22d3ee",
        weight: 5,
        opacity: 0.9,
        dashArray: "2 9"
      })
        .bindPopup(r.title)
        .addTo(layers.recs);
    });

    (geometry.points || []).forEach(point => {
      L.circleMarker(point.c, {
        radius: 9,
        color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 2
      })
        .bindTooltip(point.label)
        .bindPopup(
          `<strong>${r.title}</strong><br>${point.label}`
        )
        .addTo(layers.recs);
    });
  }

  // Centra la mappa su una raccomandazione
  layers.focusRec = function (rec) {
    const points = [];
    const geometry = rec.geometry || {};

    (geometry.lines || []).forEach(line => {
      line.pts.forEach(point => points.push(point));
    });

    (geometry.points || []).forEach(point => {
      points.push(point.c);
    });

    if (points.length) {
      map.fitBounds(
        L.latLngBounds(points).pad(0.4),
        { maxZoom: 15 }
      );
    }
  };

  // Rende i livelli disponibili agli altri script
  NP.layers = layers;

})((globalThis.NP = globalThis.NP || {}));
