import React, { useEffect, useState } from "react";
import api from "../api";

let cache = null;
export function useFamiglie() {
  const [famiglie, setFamiglie] = useState(cache || []);
  useEffect(() => { api.get("/etichette").then((r) => { cache = r.data; setFamiglie(r.data); }); }, []);
  return famiglie;
}
export function aggiornaCacheFamiglie() { cache = null; }

// Scelta delle etichette di un corso: una riga per famiglia, chip per quelle a scelta multipla,
// menu per quelle a scelta singola. Si sceglie sempre da un elenco, mai testo libero.
export function SceltaEtichette({ famiglie, valore, onChange }) {
  const sel = new Set(valore);
  const alterna = (f, id) => {
    const n = new Set(sel);
    if (f.scelta_multipla) { n.has(id) ? n.delete(id) : n.add(id); }
    else { f.etichette.forEach((e) => n.delete(e.id)); if (id) n.add(id); }
    onChange([...n]);
  };
  return (
    <div className="scelta-etichette">
      {famiglie.map((f) => (
        <div key={f.id} className="famiglia-riga">
          <span className="famiglia-nome" title={f.descrizione || ""}>{f.nome}{f.obbligatoria && <span style={{ color: "var(--red-text)" }}> *</span>}</span>
          {f.scelta_multipla ? (
            <div className="chips">
              {f.etichette.map((e) => (
                <button type="button" key={e.id} className={`chip ${sel.has(e.id) ? "attiva" : ""}`} onClick={() => alterna(f, e.id)}>{e.nome}</button>
              ))}
              {f.etichette.length === 0 && <span className="text-muted" style={{ fontSize: 12 }}>nessuna etichetta: aggiungile in Etichette</span>}
            </div>
          ) : (
            <select value={f.etichette.find((e) => sel.has(e.id))?.id || ""} onChange={(ev) => alterna(f, ev.target.value)}>
              <option value="">—</option>
              {f.etichette.map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
            </select>
          )}
        </div>
      ))}
    </div>
  );
}

// Filtro per etichette: si aggiungono come chip; tra famiglie diverse valgono tutte, nella stessa famiglia basta una.
export function FiltroEtichette({ valore, onChange }) {
  const famiglie = useFamiglie();
  const tutte = {};
  famiglie.forEach((f) => f.etichette.forEach((e) => { tutte[e.id] = `${f.nome}: ${e.nome}`; }));
  return (
    <div className="field">
      <label>Etichette</label>
      <select value="" onChange={(e) => e.target.value && onChange([...new Set([...valore, e.target.value])])}>
        <option value="">Aggiungi un filtro...</option>
        {famiglie.map((f) => (
          <optgroup key={f.id} label={f.nome}>
            {f.etichette.filter((e) => !valore.includes(e.id)).map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
          </optgroup>
        ))}
      </select>
      {valore.length > 0 && (
        <div className="chips" style={{ marginTop: 6 }}>
          {valore.map((id) => <button type="button" key={id} className="chip attiva" title="Togli il filtro" onClick={() => onChange(valore.filter((x) => x !== id))}>{tutte[id] || "…"} ✕</button>)}
        </div>
      )}
    </div>
  );
}

export function ChipEtichette({ etichette }) {
  if (!etichette?.length) return <span className="text-muted">—</span>;
  return <div className="chips">{etichette.map((e) => <span key={e.id} className="chip piccola" title={e.famiglia}>{e.nome}</span>)}</div>;
}
