// Variabili globali per tracciare i marker
let activeAlertMarker = null;
let simulatedCrowdMarker = null; 

document.getElementById('btn-avvia').addEventListener('click', avviaSimulazioneDemo);
document.getElementById('btn-reset').addEventListener('click', resetSimulazioneDemo);

function avviaSimulazioneDemo() {
    const coordinateEvento = [40.8396, 14.2490]; // Toledo

    // 1. Mostra Orologio Fisso (senza secondi)
    const clockEl = document.getElementById('sim-clock');
    if (clockEl) {
        clockEl.style.display = 'block';
        clockEl.innerText = "15:30";
    }

    // 2. Vola sul punto dell'incidente
    NP.map.flyTo(coordinateEvento, 16, { animate: true, duration: 2.5 });

    // 3. Esegue le azioni visive una volta terminato il "volo"
    setTimeout(() => {
        // Pulisce eventuali layer vecchi per una mappa pulita
        NP.layers.events.clearLayers(); 

        // Disegna il marker del Guasto Critico
        activeAlertMarker = L.circleMarker(coordinateEvento, {
            radius: 30, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.5
        }).addTo(NP.map);
        activeAlertMarker.bindPopup("<strong>ALLARME:</strong> Guasto critico Metro Linea 1.").openPopup();

        // Disegna l'area di Folla causata dall'evacuazione
        simulatedCrowdMarker = L.circle(coordinateEvento, {
            color: '#7f1d1d', fillColor: '#ef4444', fillOpacity: 0.6, radius: 350
        }).addTo(NP.map); 
        simulatedCrowdMarker.bindPopup("<strong>Folla Critica (Toledo)</strong><br>Picco di densità causato dall'evacuazione della stazione.");

        // Popola il Registro Decisioni
        const registroDiv = document.querySelector('.log');
        if(registroDiv) {
            if(registroDiv.innerHTML.includes("In attesa")) {
                registroDiv.innerHTML = "";
            }
            registroDiv.innerHTML = `
                <div class="log-line event">
                    <span>15:30:02</span>
                    <i class="ph-fill ph-warning-circle" style="color: #ef4444;"></i>
                    <span><strong>Sensori:</strong> Blocco Linea 1 a Toledo. Evacuazione in corso.</span>
                </div>
                <div class="log-line">
                    <span>15:30:05</span>
                    <i class="ph-fill ph-cpu" style="color: #3b82f6;"></i>
                    <span><strong>Orchestratore:</strong> Allarme folla. Interrogo Agente Mobilità.</span>
                </div>
                <div class="log-line revision">
                    <span>15:30:12</span>
                    <i class="ph-fill ph-check-circle" style="color: #22c55e;"></i>
                    <span><strong>PIANO:</strong> 3 Navette in arrivo. Pedoni deviati su Via Diaz.</span>
                </div>
            ` + registroDiv.innerHTML;
        }

    }, 2500); 
}

function resetSimulazioneDemo() {
    // 1. Nasconde l'orologio
    const clockEl = document.getElementById('sim-clock');
    if (clockEl) {
        clockEl.style.display = 'none';
    }

    // 2. Rimuove permanentemente i marker dell'emergenza usando .remove()
    if (activeAlertMarker) { 
        activeAlertMarker.remove(); 
        activeAlertMarker = null; 
    }
    if (simulatedCrowdMarker) { 
        simulatedCrowdMarker.remove(); 
        simulatedCrowdMarker = null; 
    }

    // 3. Chiude i popup e riporta la mappa alla visuale larga di Napoli
    NP.map.closePopup();
    NP.map.flyTo(NP.data.center, NP.data.zoom, { animate: true, duration: 1.5 });

    // 4. Svuota il registro decisioni
    const registroDiv = document.querySelector('.log');
    if (registroDiv) {
        registroDiv.innerHTML = '<div class="empty-message">In attesa di eventi...</div>';
    }
}
