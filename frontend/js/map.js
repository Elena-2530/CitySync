
/* =========================================================
   CITYSYNC - MAPPA E RICERCA GEOGRAFICA
   ========================================================= */

(function (NP) {

    // 1. INIZIALIZZAZIONE MAPPA

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


    // 2. ELEMENTI HTML

    const searchForm = document.getElementById("location-search-form");
    const searchInput = document.getElementById("location-search-input");
    const searchButton = document.getElementById("location-search-button");
    const searchStatus = document.getElementById("location-search-status");
    const searchResults = document.getElementById("location-search-results");
    const locationLabel = document.getElementById("map-location-label");


    // 3. STATO

    let selectedMarker = null;
    let analysisMarker = null;
    let activeRequest = null;
    let selectedLocation = null;


    // 4. FUNZIONI DI SUPPORTO

    function showStatus(message, type = "") {
        if (!searchStatus) return;

        searchStatus.textContent = message;
        searchStatus.className = "search-status";

        if (type) {
            searchStatus.classList.add(type);
        }
    }

    function clearResults() {
        if (searchResults) {
            searchResults.replaceChildren();
        }
    }

    function setLoading(loading) {
        if (!searchButton) return;

        searchButton.disabled = loading;
        searchButton.textContent = loading ? "Ricerca..." : "Cerca";
    }

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => {
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


    // 5. RICERCA GEOGRAFICA

    async function searchLocation(query) {

        if (activeRequest) {
            activeRequest.abort();
        }

        const controller = new AbortController();
        activeRequest = controller;

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
                signal: controller.signal
            });

            if (!response.ok) {

                let errorMessage =
                    "Errore durante la ricerca della località.";

                try {
                    const errorData = await response.json();

                    if (typeof errorData.detail === "string") {
                        errorMessage = errorData.detail;
                    }
                } catch (_) {}

                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (!data.results || data.results.length === 0) {
                showStatus(
                    "Nessuna località trovata. Prova con un indirizzo più preciso."
                );
                return;
            }

            renderResults(data.results);

            showStatus(
                `${data.count} corrispondenze trovate. Seleziona quella corretta.`
            );

        } catch (error) {

            if (error.name === "AbortError") return;

            console.error("Errore geocodifica:", error);

            showStatus(
                "Impossibile contattare il backend. Verifica che FastAPI sia attivo.",
                "error"
            );

        } finally {

            if (activeRequest === controller) {
                activeRequest = null;
                setLoading(false);
            }
        }
    }


    // 6. RISULTATI DELLA RICERCA

    function renderResults(results) {

        clearResults();

        results.forEach(result => {

            const button = document.createElement("button");
            button.type = "button";
            button.className = "search-result";

            const icon = document.createElement("i");
            icon.className = "ph ph-map-pin";

            const content = document.createElement("div");
            content.className = "search-result-content";

            const name = document.createElement("strong");
            name.textContent = result.name || "Località senza nome";

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


    // 7. SELEZIONE DELLA LOCALITÀ

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

        selectedLocation = {
            name: location.name,
            display_name: location.display_name,
            latitude,
            longitude,
            osm_type: location.osm_type,
            osm_id: location.osm_id
        };

        map.flyTo(
            [latitude, longitude],
            16,
            { duration: 1.5 }
        );

        if (selectedMarker) {
            map.removeLayer(selectedMarker);
        }

        selectedMarker = L.marker(
            [latitude, longitude]
        ).addTo(map);

        selectedMarker.bindPopup(
            `<strong>${escapeHTML(location.name || "Località selezionata")}</strong>`
        ).openPopup();

        // Una nuova località richiede una nuova analisi.
        clearAnalysisMarker();

        if (locationLabel) {
            locationLabel.textContent =
                location.display_name || location.name;
        }

        clearResults();

        showStatus(
            "Località selezionata correttamente.",
            "success"
        );

        console.log(
            "CitySync - Località selezionata:",
            selectedLocation
        );
    }


    // 8. RISULTATI DELL'ANALISI SULLA MAPPA

    function clearAnalysisMarker() {

        if (analysisMarker) {
            map.removeLayer(analysisMarker);
            analysisMarker = null;
        }
    }

    function showAnalysis(data) {

        const scenario = data.scenario || {};
        const location = scenario.location || selectedLocation;

        if (!location) return;

        const latitude = Number(location.latitude);
        const longitude = Number(location.longitude);

        if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude)
        ) {
            return;
        }

        const janara = data.janara || {};
        const responseText =
            typeof janara.response === "string"
                ? janara.response
                : "Analisi completata da Janara.";

        const alertMatch = responseText.match(
            /allerta ufficiale attiva[^:]*:\s*([^\.\n]+)/i
        );

        const levelMatch = responseText.match(
            /livello di allerta:\s*([^\.\n]+)/i
        );

        const zoneMatch = responseText.match(
            /Zona\s+\d+:\s*([^\.\n]+)/i
        );

        const alertCode = alertMatch
            ? alertMatch[1].trim()
            : "Verificare il dettaglio dell'analisi";

        const alertLevel = levelMatch
            ? levelMatch[1].trim()
            : "Non specificato";

        const zone = zoneMatch
            ? zoneMatch[1].trim()
            : "Non specificata";

        clearAnalysisMarker();

        // Non disegniamo un'area geografica non disponibile.
        // Il marker indica esclusivamente la località analizzata.

        analysisMarker = L.marker(
            [latitude, longitude],
            {
                title: "Risultato analisi CitySync"
            }
        ).addTo(map);

        const popup = `
            <div class="citysync-map-popup">
                <strong>Analisi CitySync</strong>
                <hr>
                <b>Località:</b>
                ${escapeHTML(location.display_name || location.name)}
                <br><br>
                <b>Allerta:</b>
                ${escapeHTML(alertCode)}
                <br>
                <b>Livello:</b>
                ${escapeHTML(alertLevel)}
                <br>
                <b>Zona:</b>
                ${escapeHTML(zone)}
                <hr>
                <small>
                    Il marker indica la località analizzata,
                    non il confine geografico dell'area di allerta.
                </small>
            </div>
        `;

        analysisMarker.bindPopup(popup).openPopup();

        map.flyTo(
            [latitude, longitude],
            Math.max(map.getZoom(), 14),
            { duration: 1.2 }
        );

        console.log(
            "CitySync - Marker dell'analisi aggiornato:",
            location
        );
    }


    // 9. EVENTO FORM DI RICERCA

    if (searchForm) {

        searchForm.addEventListener("submit", event => {

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
    }


    // 10. ESPORTAZIONE FUNZIONI

    NP.map = map;

    NP.geocoding = {
        search: searchLocation,

        getSelectedLocation: function () {
            return selectedLocation;
        },

        selectLocation: selectLocation
    };

    NP.mapAnalysis = {
        show: showAnalysis,
        clear: clearAnalysisMarker
    };

})(globalThis.NP = globalThis.NP || {});
