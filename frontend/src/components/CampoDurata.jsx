import React from "react";

// Durata scritta in ore e minuti; il valore e' un numero di minuti (o null se vuota).
export default function CampoDurata({ valore, onChange, etichetta = "Durata", id = "durata", suggerimento }) {
  const tot = valore ? Number(valore) : 0;
  const ore = tot ? Math.floor(tot / 60) : "";
  const minuti = tot ? tot % 60 : "";
  const aggiorna = (h, m) => { const t = h * 60 + m; onChange(t > 0 ? t : null); };
  const num = (v, max) => Math.max(0, Math.min(max, parseInt(v, 10) || 0));
  return (
    <div className="field">
      <label htmlFor={`${id}-ore`}>{etichetta}</label>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input id={`${id}-ore`} type="number" min="0" max="1666" style={{ width: 80 }} placeholder="0" value={ore} onChange={(e) => aggiorna(num(e.target.value, 1666), tot % 60)} /> <span>ore</span>
        <input id={`${id}-min`} aria-label={`${etichetta}: minuti`} type="number" min="0" max="59" style={{ width: 80 }} placeholder="0" value={minuti} onChange={(e) => aggiorna(Math.floor(tot / 60), num(e.target.value, 59))} /> <span>minuti</span>
      </div>
      {suggerimento && <span className="text-muted" style={{ fontSize: 12 }}>{suggerimento}</span>}
    </div>
  );
}
