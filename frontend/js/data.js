/* NEURAPOLIS - dati geografici DIMOSTRATIVI.
   Le coordinate sono approssimate: vanno sostituite/verificate con dati reali
   (OpenStreetMap via Overpass, GTFS) prima di dichiararle "reali" in presentazione. */
(function (NP) {
  const st = (name, c) => ({ name, c });

  const linea1 = [
    st("Garibaldi", [40.853, 14.2717]),
    st("Università", [40.8465, 14.2575]),
    st("Municipio", [40.8387, 14.2527]),
    st("Toledo", [40.8396, 14.249]),
    st("Dante", [40.8466, 14.2508]),
    st("Museo", [40.8537, 14.2506])
  ];
  const linea2 = [
    st("Garibaldi", [40.853, 14.2717]),
    st("Montesanto", [40.8438, 14.2467]),
    st("Piazza Amedeo", [40.8372, 14.2271]),
    st("Mergellina", [40.8285, 14.221]),
    st("Campi Flegrei", [40.8267, 14.1955])
  ];

  NP.data = {
    center: [40.84, 14.232],
    zoom: 13,
    linea1,
    linea2,
    faultSegment: [linea1[1].c, linea1[2].c], // Università – Municipio
    shuttleRoute: [linea1[2].c, linea1[1].c, linea1[0].c], // Municipio → Università → Garibaldi (indicativo)
    openRoute: [[40.841, 14.255], [40.8383, 14.2528], [40.8359, 14.2488]], // porto → Plebiscito
    hotspots: [
      { id: "porto", label: "Porto e Municipio", c: [40.841, 14.255], radius: 450, sensor: 0.9 },
      { id: "stadio", label: "Stadio Maradona", c: [40.8279, 14.193], radius: 700, sensor: 0.8 },
      { id: "centro", label: "Centro storico", c: [40.8359, 14.2488], radius: 500, sensor: 0.6 }
    ],
    pois: [
      { name: "Piazza del Plebiscito", c: [40.8359, 14.2488] },
      { name: "Castel Nuovo", c: [40.838, 14.2525] },
      { name: "Duomo di Napoli", c: [40.853, 14.258] },
      { name: "Stazione Marittima", c: [40.842, 14.2565] },
      { name: "Stadio Maradona", c: [40.8279, 14.193] }
    ],
    // Rifugi al coperto con capienza SIMULATA
    shelters: [
      { name: "Galleria Umberto I", c: [40.8383, 14.2492], capacity: 1500 },
      { name: "Museo Archeologico (MANN)", c: [40.8535, 14.2505], capacity: 2500 },
      { name: "Castel Nuovo (interno)", c: [40.838, 14.2525], capacity: 1200 }
    ],
    rainArea: { c: [40.84, 14.232], radius: 8000 }
  };
})((globalThis.NP = globalThis.NP || {}));
