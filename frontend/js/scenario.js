
/* =========================================================
   CITYSYNC - GESTIONE SCENARI E RISULTATI
   ========================================================= */

(function (NP) {

    const startButton = document.getElementById("btn-avvia");
    const resetButton = document.getElementById("btn-reset");
    const descriptionInput = document.getElementById("scenario-description");
    const statusElement = document.getElementById("scenario-status");
    const logElement = document.getElementById("log");

    const API_URL = "http://127.0.0.1:8000/api/scenarios/analyze";

    let currentRequest = null;
    let activeController = null;

    if (!startButton || !resetButton || !descriptionInput || !statusElement || !logElement || !NP.geocoding) {
        console.error("CitySync: componenti non inizializzati.");
        return;
    }

    // -----------------------------------------------------
    // STILE RISULTATI
    // -----------------------------------------------------

    const style = document.createElement("style");

    style.textContent = `
        #citysync-result {
            margin: 20px 0;
            padding: 22px;
            background: #fff;
            border: 1px solid #dce5ef;
            border-radius: 14px;
            color: #172b4d;
            box-shadow: 0 4px 16px rgba(15,23,42,.06);
        }

        #citysync-result .result-heading {
            font-size: 19px;
            font-weight: 700;
            margin-bottom: 14px;
        }

        #citysync-result .result-summary {
            font-size: 14px;
            line-height: 1.65;
            white-space: pre-line;
            margin-bottom: 18px;
        }

        #citysync-result .alert-card {
            padding: 15px;
            margin: 15px 0;
            border-radius: 10px;
            background: #fff8e8;
            border: 1px solid #f1d49a;
        }

        #citysync-result .alert-title {
            font-weight: 700;
            margin-bottom: 7px;
        }

        #citysync-result .alert-info {
            font-size: 13px;
            line-height: 1.6;
            white-space: pre-line;
        }

        #citysync-result .advice-title {
            font-size: 16px;
            font-weight: 700;
            margin: 18px 0 10px;
        }

        #citysync-result .advice-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        #citysync-result .advice-list li {
            padding: 10px 0;
            border-bottom: 1px solid #edf1f5;
            font-size: 14px;
            line-height: 1.5;
        }

        #citysync-result .details-button {
            border: 0;
            background: transparent;
            color: #1674c8;
            cursor: pointer;
            padding: 12px 0 0;
            font-weight: 600;
        }

        #citysync-result .details-content {
            display: none;
            margin-top: 10px;
            font-size: 12px;
            line-height: 1.6;
            color: #64748b;
        }

        #citysync-result .details-content.visible {
            display: block;
        }

        #citysync-result .result-footer {
            margin-top: 16px;
            font-size: 11px;
            color: #8793a3;
        }
    `;

    document.head.appendChild(style);

    // -----------------------------------------------------
    // INTERFACCIA
    // -----------------------------------------------------

    function showStatus(message, type = "") {
        statusElement.textContent = message;
        statusElement.className = type;
    }

    function addText(parent, tag, className, text) {
        const element = document.createElement(tag);
        element.className = className || "";
        element.textContent = text || "";
        parent.appendChild(element);
        return element;
    }

    function createResultPanel() {
        let panel = document.getElementById("citysync-result");

        if (panel) panel.remove();

        panel = document.createElement("section");
        panel.id = "citysync-result";

        statusElement.insertAdjacentElement("afterend", panel);

        return panel;
    }

    // -----------------------------------------------------
    // DATI RISPOSTA
    // -----------------------------------------------------

    function getCivilProtectionResult(janara) {
        const results = janara.agent_results?.civil_protection;

        if (!results) return null;

        const items = Array.isArray(results) ? results : [results];

        return items.find(item => item && item.safety_assessment) || items[0] || null;
    }

    // -----------------------------------------------------
    // VISUALIZZAZIONE RISULTATO
    // -----------------------------------------------------

    function renderResult(data) {

        const panel = createResultPanel();
        const janara = data.janara || {};
        const civil = getCivilProtectionResult(janara);

        addText(panel, "div", "result-heading", "Risultato dell'analisi");

        addText(
            panel,
            "div",
            "result-summary",
            janara.response || "Analisi completata. Non sono disponibili ulteriori informazioni."
        );

        // Allerte

        const alerts = civil?.official_alert_analysis?.alerts || [];

        alerts.filter(alert => alert.validity_status === "active").forEach(alert => {

            const card = document.createElement("div");
            card.className = "alert-card";

            addText(
                card,
                "div",
                "alert-title",
                "Allerta attiva – livello " + (alert.level || "non specificato")
            );

            addText(
                card,
                "div",
                "alert-info",
                [
                    "Rischio: " + (alert.risk || alert.risk_type || "Idrogeologico"),
                    alert.valid_from ? "Dalle: " + alert.valid_from : "",
                    alert.valid_until ? "Fino alle: " + alert.valid_until : ""
                ].filter(Boolean).join("\n")
            );

            panel.appendChild(card);
        });

        // Consigli

        addText(panel, "div", "advice-title", "Consigli di gestione");

        const recommendations = civil?.safety_assessment?.recommendations || [];

        if (recommendations.length) {

            const list = document.createElement("ul");
            list.className = "advice-list";

            recommendations.forEach(item => {
                const li = document.createElement("li");
                li.textContent = "✓  " + (
                    typeof item === "string"
                        ? item
                        : item.text || item.description || ""
                );
                list.appendChild(li);
            });

            panel.appendChild(list);

        } else {
            addText(
                panel,
                "p",
                "",
                "Per questo scenario non sono disponibili consigli specifici. Consulta le indicazioni delle autorità competenti."
            );
        }

        // Dettagli facoltativi

        const detailsButton = addText(
            panel,
            "button",
            "details-button",
            "Mostra fonte e limitazioni ▾"
        );

        detailsButton.type = "button";

        const details = addText(panel, "div", "details-content", "");

        const limitations = janara.limitations || [];

        limitations.forEach(item => {
            addText(
                details,
                "p",
                "",
                typeof item === "string" ? item : JSON.stringify(item)
            );
        });

        const source = document.createElement("a");
        source.href = "https://portaleprotezionecivile.regione.campania.it/";
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        source.textContent = "Protezione Civile Regione Campania";
        details.appendChild(source);

        detailsButton.addEventListener("click", () => {
            const visible = details.classList.toggle("visible");
            detailsButton.textContent = visible
                ? "Nascondi dettagli ▴"
                : "Mostra fonte e limitazioni ▾";
        });

        addText(
            panel,
            "div",
            "result-footer",
            "CitySync è uno strumento informativo di supporto e non sostituisce le comunicazioni ufficiali."
        );

        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // -----------------------------------------------------
    // RACCOLTA DATI
    // -----------------------------------------------------

    function collectScenarioData() {

        const description = descriptionInput.value.trim();

        if (description.length < 10) {
            showStatus("Descrivi lo scenario con almeno 10 caratteri.", "error");
            descriptionInput.focus();
            return null;
        }

        const location = NP.geocoding.getSelectedLocation();

        if (!location) {
            showStatus("Seleziona prima una località sulla mappa.", "error");
            return null;
        }

        return {
            description,
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
    // INVIO AL BACKEND
    // -----------------------------------------------------

    async function sendScenarioToBackend(scenarioData) {

        if (activeController) activeController.abort();

        activeController = new AbortController();
        const controller = activeController;

        startButton.disabled = true;
        startButton.textContent = "Analisi in corso...";

        showStatus("Janara sta analizzando lo scenario...", "");

        const panel = createResultPanel();
        addText(panel, "div", "result-heading", "Analisi in corso...");

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
                throw new Error(
                    responseData.detail || "Errore durante l'elaborazione dello scenario."
                );
            }

            if (activeController !== controller) return;

            currentRequest = {
                ...scenarioData,
                response: responseData
            };

            showStatus("Analisi completata.", "success");

            renderResult(responseData);

        } catch (error) {

            if (error.name === "AbortError") return;

            console.error("CitySync - Errore:", error);

            showStatus("Errore durante l'analisi: " + error.message, "error");

            const errorPanel = createResultPanel();

            addText(errorPanel, "div", "result-heading", "Analisi non disponibile");
            addText(errorPanel, "p", "result-summary", error.message);

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
    // AVVIO E RESET
    // -----------------------------------------------------

    async function avviaScenario() {
        const scenarioData = collectScenarioData();
        if (!scenarioData) return;

        await sendScenarioToBackend(scenarioData);
    }

    function resetScenario() {

        if (activeController) {
            activeController.abort();
            activeController = null;
        }

        currentRequest = null;
        descriptionInput.value = "";

        showStatus("", "");

        const panel = document.getElementById("citysync-result");
        if (panel) panel.remove();

        logElement.replaceChildren();
        startButton.disabled = false;
        startButton.innerHTML =
            '<i class="ph-fill ph-play"></i> Avvia scenario';
    }

    startButton.addEventListener("click", avviaScenario);
    resetButton.addEventListener("click", resetScenario);

    NP.scenario = {
        getCurrentRequest: () => currentRequest,
        reset: resetScenario
    };

})(globalThis.NP = globalThis.NP || {});
