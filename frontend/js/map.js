/* NEURAPOLIS - inizializzazione della mappa (usa il namespace NP). */
(function (NP) {
  const map = L.map("map").setView(NP.data.center, NP.data.zoom);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(map);

  NP.map = map;
})((globalThis.NP = globalThis.NP || {}));
