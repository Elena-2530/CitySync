/* NEURAPOLIS - inizializzazione della mappa (usa il namespace NP). */
(function (NP) {
  const map = L.map("map").setView(NP.data.center, NP.data.zoom);

 // Rimuovi o commenta il vecchio tileLayer e inserisci questo:
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
}).addTo(map);

// Opzionale: Aggiungi anche le etichette delle strade sopra il satellite
L.tileLayer('https://stamen-tiles-{s}.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}{r}.png', {
    attribution: 'Map tiles by Stamen Design, CC BY 3.0',
    opacity: 0.8,
    //color: '#ffffff' // Colore bianco per le etichette
}).addTo(map);


  NP.map = map;
})((globalThis.NP = globalThis.NP || {}));
