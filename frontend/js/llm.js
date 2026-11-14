/* NEURAPOLIS - spiegazioni in linguaggio naturale.
   L'LLM NON decide e NON calcola: riformula soltanto ciò che gli agenti e
   l'orchestratore hanno già prodotto. Senza chiave (o senza rete) si usa un
   testo-modello, quindi la demo funziona sempre. */
(function (NP) {
  const MODEL = "gemini-2.5-flash"; // verifica in Google AI Studio il nome del modello gratuito attuale

  function key() {
    try { return localStorage.getItem("np_gemini_key") || ""; } catch (e) { return ""; }
  }

  function template(rec) {
    return `${rec.title}. Motivi: ` + rec.rationale.join(" ");
  }

  NP.llm = {
    setKey(k) {
      try { localStorage.setItem("np_gemini_key", k.trim()); } catch (e) { /* ignorato */ }
    },
    getKey: key,
    async explain(rec) {
      const k = key();
      if (!k) return { text: template(rec), source: "modello di testo" };
      const prompt =
        "Sei l'assistente di una sala di controllo della città di Napoli. Spiega in 3 frasi, in italiano semplice, " +
        "perché viene raccomandata questa azione. Usa SOLO le informazioni fornite, non aggiungere dati.\n\n" +
        `Azione: ${rec.title}\nMotivazioni:\n- ` + rec.rationale.join("\n- ");
      try {
        const r = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${encodeURIComponent(k)}`,
          { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }) }
        );
        if (!r.ok) throw new Error("HTTP " + r.status);
        const j = await r.json();
        const txt = j.candidates && j.candidates[0] && j.candidates[0].content.parts[0].text;
        if (!txt) throw new Error("risposta vuota");
        return { text: txt, source: "Gemini" };
      } catch (e) {
        return { text: template(rec), source: "modello di testo (Gemini non raggiungibile)" };
      }
    }
  };
})((globalThis.NP = globalThis.NP || {}));
