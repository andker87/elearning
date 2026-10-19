import React, { useEffect, useState } from "react";

const PREDEFINITI = ["#5a6b8a", "#e84a4a", "#e8903a", "#d4b106", "#22a587", "#2f9e44", "#4a7eff", "#7048e8", "#c2255c", "#495057"];
const ESADECIMALE = /^#[0-9a-fA-F]{6}$/;

// Colore con un quadrato ben visibile (apre il selettore del browser: tavolozza, RGB, HSL, esadecimale),
// il codice esadecimale scritto a mano e una fila di colori pronti. `anteprima` e' il testo mostrato nell'etichetta di prova.
export default function SelettoreColore({ valore, onChange, anteprima = "Esempio", id }) {
  const [testo, setTesto] = useState(valore || "#5a6b8a");
  useEffect(() => { setTesto(valore || "#5a6b8a"); }, [valore]);
  const valido = ESADECIMALE.test(testo);

  function digita(e) {
    let t = e.target.value.trim();
    if (t && t[0] !== "#") t = "#" + t;
    setTesto(t);
    if (ESADECIMALE.test(t)) onChange(t.toLowerCase());
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <input type="color" id={id} aria-label="Scegli il colore" value={valido ? testo.toLowerCase() : "#5a6b8a"}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: 48, height: 48, padding: 2, flex: "none", cursor: "pointer", borderRadius: 8 }} />
      <input type="text" aria-label="Codice colore esadecimale" aria-invalid={!valido} placeholder="#RRGGBB" maxLength={7} value={testo} onChange={digita}
        style={{ width: 110, flex: "none", fontFamily: "monospace", borderColor: valido ? undefined : "#b02a2a" }} />
      <span className="badge" style={{ background: valido ? testo : "#5a6b8a", color: "#fff" }}>{anteprima || "Esempio"}</span>
      <span role="group" aria-label="Colori pronti" style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
        {PREDEFINITI.map((c) => (
          <button key={c} type="button" title={c} aria-label={`Colore ${c}`} onClick={() => onChange(c)}
            style={{ width: 22, height: 22, minWidth: 22, padding: 0, borderRadius: "50%", background: c, cursor: "pointer",
              border: c.toLowerCase() === (valore || "").toLowerCase() ? "2px solid var(--text)" : "1px solid var(--border)" }} />
        ))}
      </span>
      {!valido && <span style={{ fontSize: 12, color: "#b02a2a" }}>Scrivi il colore come #RRGGBB (per esempio #22a587).</span>}
    </div>
  );
}
