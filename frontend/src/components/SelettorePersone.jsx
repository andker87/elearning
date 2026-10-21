import React, { useEffect, useMemo, useState } from "react";
import api from "../api";
import { elencoUffici } from "../uffici";

// Scelta di persone: ricerca per nome o email, filtri per ufficio (sottouffici compresi) e mansione, scelta delle singole
// persone o di tutti i risultati. `scelti` (un Set di id) e `setScelti` stanno in chi lo usa, che sa cosa farne.
export default function SelettorePersone({ utenti, esclusi = new Set(), scelti, setScelti, etichettaTrovate = "non ancora scelte", vuoto = "Nessuna persona con questi criteri." }) {
  const [testo, setTesto] = useState("");
  const [ufficio, setUfficio] = useState("");
  const [mansione, setMansione] = useState("");
  const [gruppi, setGruppi] = useState([]);
  const [mansioni, setMansioni] = useState([]);
  useEffect(() => { api.get("/groups").then((r) => setGruppi(r.data)).catch(() => {}); api.get("/mansioni").then((r) => setMansioni(r.data)).catch(() => {}); }, []);

  const uffici = useMemo(() => elencoUffici(gruppi), [gruppi]);
  const nomeUfficio = useMemo(() => Object.fromEntries(uffici.map((g) => [g.id, g.etichetta])), [uffici]);
  const nomeMansione = useMemo(() => Object.fromEntries(mansioni.map((m) => [m.id, m.name])), [mansioni]);
  // un ufficio comprende anche i suoi sottouffici
  const ufficiInclusi = useMemo(() => {
    if (!ufficio) return null;
    const figli = {};
    gruppi.forEach((g) => { if (g.parent_id) (figli[g.parent_id] = figli[g.parent_id] || []).push(g.id); });
    const insieme = new Set(); const coda = [ufficio];
    while (coda.length) { const x = coda.pop(); if (insieme.has(x)) continue; insieme.add(x); (figli[x] || []).forEach((f) => coda.push(f)); }
    return insieme;
  }, [ufficio, gruppi]);

  const cerca = testo.trim().toLowerCase();
  const risultati = utenti.filter((u) => !u.is_external && !esclusi.has(u.id)
    && (!cerca || `${u.full_name} ${u.email}`.toLowerCase().includes(cerca))
    && (!ufficiInclusi || (u.ufficio_id && ufficiInclusi.has(u.ufficio_id)))
    && (!mansione || (u.mansione_ids || []).includes(mansione)));
  const MOSTRATI = 100;
  const tutteSelezionate = risultati.length > 0 && risultati.every((u) => scelti.has(u.id));
  function alterna(id) { const n = new Set(scelti); n.has(id) ? n.delete(id) : n.add(id); setScelti(n); }
  function tutti() { const n = new Set(scelti); risultati.forEach((u) => (tutteSelezionate ? n.delete(u.id) : n.add(u.id))); setScelti(n); }

  return (
    <>
      <div className="row">
        <div className="field"><label htmlFor="sel-cerca">Cerca per nome o email</label><input id="sel-cerca" value={testo} onChange={(e) => setTesto(e.target.value)} placeholder="es. Rossi" /></div>
        <div className="field">
          <label htmlFor="sel-uff">Ufficio (con i sottouffici)</label>
          <select id="sel-uff" value={ufficio} onChange={(e) => setUfficio(e.target.value)}><option value="">Tutti</option>{uffici.map((g) => <option key={g.id} value={g.id}>{g.etichetta}</option>)}</select>
        </div>
        <div className="field">
          <label htmlFor="sel-man">Mansione</label>
          <select id="sel-man" value={mansione} onChange={(e) => setMansione(e.target.value)}><option value="">Tutte</option>{mansioni.filter((m) => m.is_active).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
        </div>
      </div>
      <div className="flex-between" style={{ margin: "4px 0 8px" }}>
        <span className="text-muted" aria-live="polite" style={{ fontSize: 13 }}>
          {risultati.length} {risultati.length === 1 ? "persona" : "persone"} {cerca || ufficio || mansione ? "trovate" : etichettaTrovate}
          {risultati.length > MOSTRATI && ` (ne mostro ${MOSTRATI}: restringi con la ricerca o i filtri; «Seleziona tutti» le prende tutte)`}
        </span>
        <button type="button" className="secondary btn-sm" disabled={risultati.length === 0} onClick={tutti}>{tutteSelezionate ? "Deseleziona i risultati" : "Seleziona tutti i risultati"}</button>
      </div>
      <div className="table-wrap" style={{ maxHeight: 280, overflowY: "auto" }}>
        <table>
          <tbody>
            {risultati.slice(0, MOSTRATI).map((u) => (
              <tr key={u.id}>
                <td style={{ width: 34 }}><input type="checkbox" style={{ width: "auto" }} aria-label={`Scegli ${u.full_name}`} checked={scelti.has(u.id)} onChange={() => alterna(u.id)} /></td>
                <td>{u.full_name}<div className="text-muted" style={{ fontSize: 12 }}>{u.email}</div></td>
                <td className="text-muted" style={{ fontSize: 13 }}>{nomeUfficio[u.ufficio_id] || "—"}</td>
                <td>{(u.mansione_ids || []).map((m) => nomeMansione[m] && <span key={m} className="badge gray" style={{ marginRight: 4 }}>{nomeMansione[m]}</span>)}</td>
              </tr>
            ))}
            {risultati.length === 0 && <tr><td className="text-muted">{vuoto}</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
