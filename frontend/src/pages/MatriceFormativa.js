import React, { useEffect, useState } from "react";
import api from "../api";
import ExportButton from "../components/ExportButton";
import { FiltroEtichette } from "../components/Etichette";

const ORDINE = ["valido", "in_scadenza", "in_corso", "da_aggiornare", "scaduto", "non_completato", "mancante"];
const COLORI = { valido: "var(--green-bg)", in_scadenza: "var(--yellow-bg)", in_corso: "var(--bg3)", da_aggiornare: "var(--red-bg)", scaduto: "var(--red-bg)", non_completato: "var(--red-bg)", mancante: "var(--red-bg)" };
const data = (d) => (d ? new Date(d).toLocaleDateString("it-IT") : null);

export default function MatriceFormativa() {
  const [uffici, setUffici] = useState([]);
  const [filtri, setFiltri] = useState({ ufficio_id: "", solo_obbligatori: true, etichette: [] });
  const [m, setM] = useState(null);

  useEffect(() => { api.get("/groups").then((r) => setUffici(r.data.filter((g) => g.is_ufficio))); }, []);
  useEffect(() => {
    const params = { solo_obbligatori: filtri.solo_obbligatori };
    if (filtri.ufficio_id) params.ufficio_id = filtri.ufficio_id;
    if (filtri.etichette.length) params.etichette = filtri.etichette;
    api.get("/registro/matrice", { params, paramsSerializer: { indexes: null } }).then((r) => setM(r.data));
  }, [filtri]);

  function exportPath() {
    const p = new URLSearchParams({ solo_obbligatori: filtri.solo_obbligatori });
    if (filtri.ufficio_id) p.set("ufficio_id", filtri.ufficio_id);
    filtri.etichette.forEach((id) => p.append("etichette", id));
    return `/registro/matrice/export?${p.toString()}`;
  }

  const r = m?.riepilogo;
  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Matrice formativa</h2>
          <p>Chi ha fatto cosa, in un colpo d'occhio: una riga per persona, una colonna per corso richiesto dai percorsi assegnati.</p>
        </div>
        <ExportButton path={exportPath()} filename="matrice_formativa" />
      </div>

      <div className="card">
        <div className="row">
          <div className="field">
            <label>Reparto/ufficio</label>
            <select value={filtri.ufficio_id} onChange={(e) => setFiltri({ ...filtri, ufficio_id: e.target.value })}>
              <option value="">Tutta l'azienda</option>
              {uffici.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 220 }}><FiltroEtichette valore={filtri.etichette} onChange={(v) => setFiltri({ ...filtri, etichette: v })} /></div>
          <div className="field" style={{ alignSelf: "flex-end" }}>
            <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={filtri.solo_obbligatori} onChange={(e) => setFiltri({ ...filtri, solo_obbligatori: e.target.checked })} />
              Solo corsi richiesti dai percorsi
            </label>
          </div>
          {r && r.percentuale !== null && (
            <div className="field" style={{ alignSelf: "flex-end", flex: "0 0 auto" }}>
              <strong style={{ fontSize: 22 }}>{r.percentuale}%</strong>{" "}
              <span className="text-muted" style={{ fontSize: 12 }}>in regola ({r.conformi} su {r.celle_obbligatorie} corsi richiesti)</span>
            </div>
          )}
        </div>
      </div>

      <div className="matrice-legenda">
        {ORDINE.map((s) => <span key={s} style={{ "--c": COLORI[s] }}>{m?.etichette[s] || s}{s === "in_scadenza" ? " (entro 30 giorni)" : ""}</span>)}
      </div>

      {m && m.persone.length === 0 && <div className="card empty-state">Nessun corso richiesto per il perimetro scelto. Assegna un percorso formativo alle persone, oppure togli la spunta su "Solo corsi richiesti".</div>}
      {m && m.persone.length > 0 && (
        <div className="matrice-wrap">
          <table className="matrice">
            <thead>
              <tr>
                <th className="col-persona">Persona</th>
                {m.corsi.map((c) => <th key={c.id} title={c.titolo}>{c.titolo}</th>)}
              </tr>
            </thead>
            <tbody>
              {m.persone.map((p) => (
                <tr key={p.user_id}>
                  <td className="col-persona">{p.persona}<br /><span className="text-muted" style={{ fontSize: 11 }}>{p.uffici.join(", ")}</span></td>
                  {m.corsi.map((c) => {
                    const cella = p.celle[c.id];
                    if (!cella) return <td key={c.id} className="text-muted">·</td>;
                    const scade = data(cella.scade_il), fatto = data(cella.completato_il);
                    const tip = [m.etichette[cella.stato], fatto && `completato il ${fatto}`, scade && `scade il ${scade}`, !cella.obbligatorio && "non richiesto da un percorso"].filter(Boolean).join(" — ");
                    return (
                      <td key={c.id} className={`cella ${cella.stato} ${cella.obbligatorio ? "" : "facoltativo"}`} title={`${p.persona} · ${c.titolo}: ${tip}`}>
                        {m.etichette[cella.stato]}{scade && cella.stato !== "mancante" ? <><br /><span style={{ fontWeight: 400 }}>{scade}</span></> : null}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
