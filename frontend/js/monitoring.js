
/* =========================================================
   CITYSYNC - MONITORAGGIO EVENTI REALI E NOTIFICHE
   ========================================================= */

(function () {

    const API_URL = "http://127.0.0.1:8000/api/monitoring/events";
    const POLLING_INTERVAL = 15000;

    const seenEvents = new Set();
    let firstCheck = true;

    // -----------------------------------------------------
    // STILI POPUP
    // -----------------------------------------------------

    const style = document.createElement("style");

    style.textContent = `
        #citysync-monitor-popup {
            position: fixed;
            top: 22px;
            right: 22px;
            width: min(420px, calc(100vw - 32px));
            z-index: 99999;
            background: #ffffff;
            color: #172b4d;
            border: 1px solid #dce5ef;
            border-radius: 14px;
            box-shadow: 0 12px 40px rgba(15,23,42,.22);
            padding: 20px;
            font-family: Arial, sans-serif;
            animation: citysyncPopupIn .3s ease;
        }

        @keyframes citysyncPopupIn {
            from {
                opacity: 0;
                transform: translateY(-12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        #citysync-monitor-popup .monitor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 14px;
        }

        #citysync-monitor-popup .monitor-label {
            font-size: 11px;
            font-weight: 800;
            letter-spacing: .7px;
            color: #1674c8;
        }

        #citysync-monitor-popup .monitor-close {
            border: 0;
            background: #edf2f7;
            color: #475569;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            cursor: pointer;
            font-size: 18px;
        }

        #citysync-monitor-popup .monitor-title {
            font-size: 18px;
            font-weight: 800;
            margin-bottom: 8px;
        }

        #citysync-monitor-popup .monitor-location {
            font-size: 14px;
            color: #475569;
            margin-bottom: 12px;
        }

        #citysync-monitor-popup .monitor-status {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 20px;
            background: #fff3d6;
            color: #946200;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 12px;
        }

        #citysync-monitor-popup .monitor-status.confirmed {
            background: #dcfce7;
            color: #166534;
        }

        #citysync-monitor-popup .monitor-status.conflicting,
        #citysync-monitor-popup .monitor-status.contradicted,
        #citysync-monitor-popup .monitor-status.contested {
            background: #fee2e2;
            color: #991b1b;
        }

        #citysync-monitor-popup .monitor-description {
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 12px;
        }

        #citysync-monitor-popup .monitor-guidance-title {
            font-size: 14px;
            font-weight: 800;
            margin-bottom: 7px;
        }

        #citysync-monitor-popup .monitor-guidance {
            padding-left: 19px;
            margin: 0 0 14px;
        }

        #citysync-monitor-popup .monitor-guidance li {
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 6px;
        }

        #citysync-monitor-popup .monitor-source {
            border-top: 1px solid #edf1f5;
            padding-top: 10px;
            font-size: 11px;
            color: #64748b;
            line-height: 1.6;
        }

        #citysync-monitor-popup .monitor-dismiss {
            width: 100%;
            border: 0;
            border-radius: 8px;
            padding: 11px;
            margin-top: 14px;
            background: #1674c8;
            color: #fff;
            font-weight: 700;
            cursor: pointer;
        }

        #citysync-monitor-popup .monitor-dismiss:hover {
            background: #105fa5;
        }
    `;

    document.head.appendChild(style);

    // -----------------------------------------------------
    // CREAZIONE POPUP
    // -----------------------------------------------------

    function showNotification(event) {

        const oldPopup = document.getElementById(
            "citysync-monitor-popup"
        );

        if (oldPopup) {
            oldPopup.remove();
        }

        const popup = document.createElement("section");
        popup.id = "citysync-monitor-popup";

        const header = document.createElement("div");
        header.className = "monitor-header";

        const label = document.createElement("span");
        label.className = "monitor-label";
        label.textContent = "CITYSYNC · MONITORAGGIO REALE";

        const close = document.createElement("button");
        close.className = "monitor-close";
        close.type = "button";
        close.textContent = "×";
        close.setAttribute("aria-label", "Chiudi avviso");

        close.addEventListener("click", () => popup.remove());

        header.append(label, close);
        popup.appendChild(header);

        const title = document.createElement("div");
        title.className = "monitor-title";
        title.textContent = "Nuova segnalazione rilevata";

        popup.appendChild(title);

        const status = document.createElement("div");
        status.className = "monitor-status";
        status.textContent = event.verification_label;

        if (event.verification_status === "confirmed") {
            status.classList.add("confirmed");
        }

        if ([
            "conflicting",
            "contradicted",
            "contested"
        ].includes(event.verification_status)) {
            status.classList.add(event.verification_status);
        }

        popup.appendChild(status);

        const location = document.createElement("div");
        location.className = "monitor-location";
        location.textContent =
            "Località: " + (event.location || "Non specificata");

        popup.appendChild(location);

        const description = document.createElement("div");
        description.className = "monitor-description";
        description.textContent =
            event.description || "Descrizione non disponibile.";

        popup.appendChild(description);

        const guidanceTitle = document.createElement("div");
        guidanceTitle.className = "monitor-guidance-title";
        guidanceTitle.textContent = "Come comportarsi";

        popup.appendChild(guidanceTitle);

        const guidanceList = document.createElement("ul");
        guidanceList.className = "monitor-guidance";

        (event.guidance || []).forEach(item => {
            const li = document.createElement("li");
            li.textContent = item;
            guidanceList.appendChild(li);
        });

        popup.appendChild(guidanceList);

        const source = document.createElement("div");
        source.className = "monitor-source";

        const date = event.last_report_at
            ? new Date(event.last_report_at).toLocaleString("it-IT")
            : "Non disponibile";

        source.textContent =
            "Fonte: " + event.source +
            "\nSegnalazioni associate: " + event.report_count +
            "\nUltimo aggiornamento: " + date;

        popup.appendChild(source);

        const dismiss = document.createElement("button");
        dismiss.className = "monitor-dismiss";
        dismiss.type = "button";
        dismiss.textContent = "Ho letto";

        dismiss.addEventListener("click", () => popup.remove());

        popup.appendChild(dismiss);

        document.body.appendChild(popup);
    }

    // -----------------------------------------------------
    // CONTROLLO EVENTI
    // -----------------------------------------------------

    async function checkEvents() {

        try {

            const response = await fetch(API_URL, {
                method: "GET",
                headers: {
                    "Accept": "application/json"
                },
                cache: "no-store"
            });

            if (!response.ok) {
                throw new Error("Errore recupero eventi.");
            }

            const data = await response.json();
            const events = data.events || [];

            if (firstCheck) {

                firstCheck = false;

                if (events.length > 0) {

                    events.forEach(event => {
                        seenEvents.add(
                            String(event.id) + ":" +
                            String(event.last_report_at)
                        );
                    });

                    showNotification(events[0]);
                }

                return;
            }

            const newEvents = events.filter(event => {

                const signature =
                    String(event.id) + ":" +
                    String(event.last_report_at);

                return !seenEvents.has(signature);
            });

            events.forEach(event => {
                seenEvents.add(
                    String(event.id) + ":" +
                    String(event.last_report_at)
                );
            });

            if (newEvents.length > 0) {
                showNotification(newEvents[0]);
            }

        } catch (error) {

            console.warn(
                "CitySync: monitoraggio temporaneamente non disponibile.",
                error.message
            );
        }
    }

    // -----------------------------------------------------
    // AVVIO AUTOMATICO
    // -----------------------------------------------------

    checkEvents();

    setInterval(
        checkEvents,
        POLLING_INTERVAL
    );

    console.info("CitySync: monitoraggio eventi attivo.");

})();
