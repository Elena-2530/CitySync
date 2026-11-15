
/* =========================================================
   CITYSYNC - MAPPA E RICERCA GEOGRAFICA
   ========================================================= */

(function (NP) {

    // -----------------------------------------------------
    // 1. INIZIALIZZAZIONE MAPPA
    // -----------------------------------------------------

    const map = L.map("map", {
        zoomControl: true
    }).setView(NP.data.center, NP.data.zoom);

    const streetLayer = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }
    );

    const satelliteLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
            attribution: "Tiles &copy; Esri",
            maxZoom: 19
        }
    );

    streetLayer.addTo(map);

    L.control.layers(
        {
            "Vista stradale": streetLayer,
            "Vista satellitare": satelliteLayer
        },
        {},
        {
            collapsed: true,
            position: "topright"
        }
    ).addTo(map);

    map.zoomControl.setPosition("bottomright");


    // -----------------------------------------------------
    // 2. ELEMENTI HTML
    // -----------------------------------------------------

    const searchForm = document.getElementById(
        "location-search-form"
    );

    const searchInput = document.getElementById(
        "location-search-input"
    );

    const searchButton = document.getElementById(
        "location-search-button"
    );

    const searchStatus = document.getElementById(
        "location-search-status"
    );

    const searchResults = document.getElementById(
        "location-search-results"
    );

    const locationLabel = document.getElementById(
        "map-location-label"
    );


    // -----------------------------------------------------
    // 3. STATO DELLA RICERCA
    // -----------------------------------------------------

    let selectedMarker = null;
    let activeRequest = null;

    // Posizione selezionata dall'utente.
    let selectedLocation = null;


    // -----------------------------------------------------
    // 4. FUNZIONI DI SUPPORTO
    // -----------------------------------------------------

    function showStatus(message, type = "") {

        searchStatus.textContent = message;
        searchStatus.className = "search-status";

        if (type) {
            searchStatus.classList.add(type);
        }
    }


    function clearResults() {

        searchResults.replaceChildren();
    }


    function setLoading(loading) {

        searchButton.disabled = loading;

        searchButton.textContent = loading
            ? "Ricerca..."
            : "Cerca";
    }


    // -----------------------------------------------------
    // 5. RICERCA NEL BACKEND
    // -----------------------------------------------------

    async function searchLocation(query) {

        // Interrompe un'eventuale ricerca precedente.
        if (activeRequest) {
            activeRequest.abort();
        }

        activeRequest = new AbortController();

        clearResults();

        showStatus("Ricerca delle località in corso...");

        setLoading(true);

        try {

            const url = new URL(
                "http://127.0.0.1:8000/api/geocode"
            );

            url.searchParams.set("q", query);

            const response = await fetch(url, {
                method: "GET",
                headers: {
                    "Accept": "application/json"
                },
                signal: activeRequest.signal
            });

            if (!response.ok) {

                let errorMessage =
                    "Errore durante la ricerca della località.";

                try {
                    const errorData = await response.json();

                    if (typeof errorData.detail === "string") {
                        errorMessage = errorData.detail;
                    }
                } catch (_) {
                    // Mantiene il messaggio predefinito.
                }

                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (!data.results || data.results.length === 0) {

                showStatus(
                    "Nessuna località trovata. Prova a inserire un indirizzo più preciso."
                );

                return;
            }

            renderResults(data.results);

            showStatus(
                `${data.count} corrispondenze trovate. Seleziona quella corretta.`
            );

        } catch (error) {

            if (error.name === "AbortError") {
                return;
            }

            console.error("Errore geocodifica:", error);

            showStatus(
                "Impossibile contattare il backend. Verifica che FastAPI sia attivo.",
                "error"
            );

        } finally {

            // Evita che una vecchia richiesta sblocchi
            // il pulsante mentre una nuova è ancora in corso.
            if (!activeRequest || !activeRequest.signal.aborted) {
                setLoading(false);
            }
        }
    }


    // -----------------------------------------------------
    // 6. VISUALIZZAZIONE RISULTATI
    // -----------------------------------------------------

    function renderResults(results) {

        clearResults();

        results.forEach((result) => {

            const button = document.createElement("button");

            button.type = "button";
            button.className = "search-result";

            const icon = document.createElement("i");

            icon.className = "ph ph-map-pin";

            const content = document.createElement("div");

            content.className = "search-result-content";

            const name = document.createElement("strong");

            name.textContent =
                result.name || "Località senza nome";

            const address = document.createElement("span");

            address.textContent =
                result.display_name || "Indirizzo non disponibile";

            content.append(name, address);

            button.append(icon, content);

            button.addEventListener("click", () => {

                selectLocation(result);

            });

            searchResults.appendChild(button);

        });
    }


    // -----------------------------------------------------
    // 7. SELEZIONE DELLA LOCALITÀ
    // -----------------------------------------------------

    function selectLocation(location) {

        const latitude = Number(location.latitude);
        const longitude = Number(location.longitude);

        if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude) ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180
        ) {

            showStatus(
                "Le coordinate della località non sono valide.",
                "error"
            );

            return;
        }

        // Memorizza la posizione selezionata.
        selectedLocation = {
            name: location.name,
            display_name: location.display_name,
            latitude: latitude,
            longitude: longitude,
            osm_type: location.osm_type,
            osm_id: location.osm_id
        };

        // Centra la mappa.
        map.flyTo(
            [latitude, longitude],
            16,
            {
                duration: 1.5
            }
        );

        // Rimuove il precedente indicatore.
        if (selectedMarker) {
            map.removeLayer(selectedMarker);
        }

        // Crea il nuovo indicatore.
        selectedMarker = L.marker(
            [latitude, longitude]
        ).addTo(map);

        selectedMarker.bindPopup(
            `<strong>${escapeHTML(location.name || "Località selezionata")}</strong>`
        ).openPopup();

        // Aggiorna il testo sopra la mappa.
        locationLabel.textContent =
            location.display_name || location.name;

        // Nasconde i risultati.
        clearResults();

        showStatus(
            "Località selezionata correttamente.",
            "success"
        );

        console.log(
            "Località selezionata per CitySync:",
            selectedLocation
        );

    }


    // -----------------------------------------------------
    // 8. PROTEZIONE TESTO POPUP
    // -----------------------------------------------------

    function escapeHTML(value) {

        return String(value).replace(/[&<>"']/g, (character) => {

            const entities = {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            };

            return entities[character];

        });
    }


    // -----------------------------------------------------
    // 9. EVENTO INVIO FORM
    // -----------------------------------------------------

    searchForm.addEventListener("submit", (event) => {

        event.preventDefault();

        const query = searchInput.value.trim();

        if (query.length < 2) {

            showStatus(
                "Inserisci almeno due caratteri.",
                "error"
            );

            return;
        }

        searchLocation(query);

    });


    // -----------------------------------------------------
    // 10. ESPORTAZIONE NEL NAMESPACE CITYSYNC
    // -----------------------------------------------------

    NP.map = map;

    NP.geocoding = {

        search: searchLocation,

        getSelectedLocation: function () {
            return selectedLocation;
        },

        selectLocation: selectLocation

    };

})((globalThis.NP = globalThis.NP || {}));
