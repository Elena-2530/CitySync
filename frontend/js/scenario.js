
/* =========================================================
   CITYSYNC - GESTIONE E INVIO SCENARI AL BACKEND
   ========================================================= */

(function (NP) {

    // -----------------------------------------------------
    // 1. ELEMENTI HTML
    // -----------------------------------------------------

    const startButton = document.getElementById("btn-avvia");
    const resetButton = document.getElementById("btn-reset");

    const descriptionInput = document.getElementById(
        "scenario-description"
    );

    const statusElement = document.getElementById(
        "scenario-status"
    );

    const logElement = document.getElementById("log");


    // -----------------------------------------------------
    // 2. CONFIGURAZIONE
    // -----------------------------------------------------

    const API_URL =
        "http://127.0.0.1:8000/api/scenarios/analyze";

    let currentRequest = null;
    let activeController = null;


    // -----------------------------------------------------
    // 3. VERIFICA COMPONENTI
    // -----------------------------------------------------

    if (
        !startButton ||
        !resetButton ||
        !descriptionInput ||
        !statusElement ||
        !logElement ||
        !NP.geocoding
    ) {
        console.error(
            "CitySync: componenti dello scenario non inizializzati."
        );

        return;
    }


    // -----------------------------------------------------
    // 4. MESSAGGI INTERFACCIA
    // -----------------------------------------------------

    function showStatus(message, type = "") {

        statusElement.textContent = message;
        statusElement.className = type;
    }


    function addLog(message, type = "") {

        const line = document.createElement("div");

        line.className = "log-line " + type;
        line.textContent = message;

        logElement.appendChild(line);
    }


    // -----------------------------------------------------
    // 5. RACCOLTA DATI
    // -----------------------------------------------------

    function collectScenarioData() {

        const description = descriptionInput.value.trim();

        if (description.length < 10) {

            showStatus(
                "Descrivi lo scenario con almeno 10 caratteri.",
                "error"
            );

            descriptionInput.focus();

            return null;
        }

        const location = NP.geocoding.getSelectedLocation();

        if (!location) {

            showStatus(
                "Seleziona prima una località sulla mappa.",
                "error"
            );

            return null;
        }

        return {

            description: description,

            location: {
                name: location.name,
                display_name: location.display_name,
                latitude: location.latitude,
                longitude: location.longitude,
                osm_type: location.osm_type || null,
                osm_id: location.osm_id || null
            }

        };
    }


    // -----------------------------------------------------
    // 6. INVIO AL BACKEND
    // -----------------------------------------------------

    async function sendScenarioToBackend(scenarioData) {

        if (activeController) {
            activeController.abort();
        }

        activeController = new AbortController();

        const controller = activeController;

        startButton.disabled = true;
        startButton.textContent = "Invio in corso...";

        showStatus(
            "Invio dello scenario al backend...",
            ""
        );

        try {

            const response = await fetch(API_URL, {

                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },

                body: JSON.stringify(scenarioData),

                signal: controller.signal

            });

            const responseData = await response.json();

            if (!response.ok) {

                const message =
                    responseData.detail ||
                    "Errore durante l'elaborazione dello scenario.";

                throw new Error(
                    typeof message === "string"
                        ? message
                        : JSON.stringify(message)
                );
            }

            // Ignora una risposta appartenente a una richiesta precedente.
            if (activeController !== controller) {
                return;
            }

            currentRequest = {
                ...scenarioData,
                response: responseData
            };

            showStatus(
                "Scenario ricevuto correttamente dal backend.",
                "success"
            );

            renderBackendResponse(responseData);

            console.log(
                "CITYSYNC - Risposta backend:",
                responseData
            );

        } catch (error) {

            if (error.name === "AbortError") {
                return;
            }

            console.error(
                "CitySync - Errore invio scenario:",
                error
            );

            showStatus(
                error.message ||
                "Impossibile comunicare con il backend.",
                "error"
            );

            addLog(
                "Errore: " + error.message,
                "event"
            );

        } finally {

            if (activeController === controller) {

                activeController = null;

                startButton.disabled = false;
                startButton.innerHTML =
                    '<i class="ph-fill ph-play"></i> Avvia scenario';
            }
        }
    }


    // -----------------------------------------------------
    // 7. VISUALIZZAZIONE RISPOSTA
    // -----------------------------------------------------

    function renderBackendResponse(data) {

        logElement.replaceChildren();

        addLog(
            "Nuovo scenario acquisito."
        );

        addLog(
            "Identificativo: " + data.scenario_id
        );

        addLog(
            "Stato backend: " + data.status
        );

        addLog(
            "Località: " + data.scenario.location.display_name
        );

        addLog(
            "Descrizione: " + data.scenario.description
        );

        addLog(
            "Janara: " + data.janara.status
        );

        addLog(
            data.janara.message
        );
    }


    // -----------------------------------------------------
    // 8. AVVIO SCENARIO
    // -----------------------------------------------------

    async function avviaScenario() {

        const scenarioData = collectScenarioData();

        if (!scenarioData) {
            return;
        }

        await sendScenarioToBackend(scenarioData);
    }


    // -----------------------------------------------------
    // 9. RESET
    // -----------------------------------------------------

    function resetScenario() {

        if (activeController) {

            activeController.abort();
            activeController = null;
        }

        currentRequest = null;

        descriptionInput.value = "";

        showStatus("", "");

        logElement.innerHTML =
            '<div class="empty-message">In attesa di eventi...</div>';

        startButton.disabled = false;

        startButton.innerHTML =
            '<i class="ph-fill ph-play"></i> Avvia scenario';

        console.log(
            "CitySync: scenario azzerato."
        );
    }


    // -----------------------------------------------------
    // 10. EVENTI
    // -----------------------------------------------------

    startButton.addEventListener(
        "click",
        avviaScenario
    );

    resetButton.addEventListener(
        "click",
        resetScenario
    );


    // -----------------------------------------------------
    // 11. ESPORTAZIONE
    // -----------------------------------------------------

    NP.scenario = {

        getCurrentRequest: function () {
            return currentRequest;
        },

        reset: resetScenario

    };

})((globalThis.NP = globalThis.NP || {}));
