import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import { conferma } from "../components/conferma";

const TIPI = { stelle: "Stelle (da 1 a 5)", si_no: "Sì / No", scelta: "Scelta tra opzioni", testo: "Testo libero" };
const NUOVA = () => ({ testo: "", tipo: "stelle", opzioni: "", obbligatoria: false });

const daModulo = (q) => ({ id: q?.id || null, nome: q?.nome || "", is_default: !!q?.is_default,
  domande: (q?.domande || []).map((d) => ({ testo: d.testo, tipo: d.tipo, opzioni: (d.opzioni || []).join("\n"), obbligatoria: d.obbligatoria })) });
const perServer = (m) => ({ nome: m.nome.trim(), is_default: m.is_default,
  domande: m.domande.map((d) => ({ testo: d.testo.trim(), tipo: d.tipo, obbligatoria: d.obbligatoria, opzioni: d.tipo === "scelta" ? d.opzioni.split("\n").map((o) => o.trim()).filter(Boolean) : [] })) });

export default function Questionari() {
  const [elenco, setElenco] = useState(null);
  const [modulo, setModulo] = useState(null);       // il questionario in modifica
  const [errore, setErrore] = useState(null);
  const [errModulo, setErrModulo] = useState(null);
  const [invio, setInvio] = useState(false);

  function carica() { api.get("/questionari").then((r) => setElenco(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i questionari"))); }
  useEffect(carica, []);

  async function salva(e) {
    e.preventDefault(); setErrModulo(null); setInvio(true);
    try {
      if (modulo.id) await api.put(`/questionari/${modulo.id}`, perServer(modulo)); else await api.post("/questionari", perServer(modulo));
      setModulo(null); carica();
    } catch (err) { setErrModulo(erroreDi(err, "Salvataggio non riuscito")); }
    setInvio(false);
  }
  async function elimina(q) {
    if (!(await conferma("Le risposte già date restano nei report.", { titolo: `Eliminare il questionario «${q.nome}»?`, etichetta: "Elimina il questionario", pericolo: true }))) return;
    setErrore(null);
    try { await api.delete(`/questionari/${q.id}`); carica(); } catch (err) { setErrore(erroreDi(err, "Impossibile eliminare il questionario")); }
  }
  const cambia = (i, campo, valore) => setModulo({ ...modulo, domande: modulo.domande.map((d, n) => (n === i ? { ...d, [campo]: valore } : d)) });
  const sposta = (i, verso) => {
    const j = i + verso; if (j < 0 || j >= modulo.domande.length) return;
    const d = [...modulo.domande]; [d[i], d[j]] = [d[j], d[i]]; setModulo({ ...modulo, domande: d });
  };

  return (
    <div>
      <div className="page-header">
        <div><h2>Questionari di gradimento</h2>
          <p>Cosa chiedere a chi ha seguito un corso. Voto complessivo, commento e voto ai docenti ci sono sempre; qui aggiungi le altre domande. Il questionario predefinito vale per tutti i corsi, e ogni corso può sceglierne un altro.</p></div>
        {!modulo && <button type="button" onClick={() => { setErrModulo(null); setModulo(daModulo(null)); }}>Nuovo questionario</button>}
      </div>
      {errore && <div className="error-msg" role="alert">{errore}</div>}

      {modulo && (
        <form className="card" onSubmit={salva}>
          <h3 style={{ marginTop: 0 }}>{modulo.id ? "Modifica questionario" : "Nuovo questionario"}</h3>
          <div className="row">
            <div className="field"><label htmlFor="q-nome">Nome</label><input id="q-nome" required maxLength={100} value={modulo.nome} onChange={(e) => setModulo({ ...modulo, nome: e.target.value })} /></div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" style={{ width: "auto" }} checked={modulo.is_default} onChange={(e) => setModulo({ ...modulo, is_default: e.target.checked })} />
                Predefinito (vale per i corsi che non ne scelgono un altro)
              </label>
            </div>
          </div>
          <p className="text-muted" style={{ fontSize: 13 }}>Sempre presenti, in ogni questionario: voto complessivo del corso (stelle), commento libero e voto a ogni docente della sessione.</p>

          <h4>Domande aggiuntive</h4>
          {modulo.domande.length === 0 && <p className="empty-state">Nessuna domanda aggiuntiva: il modulo avrà solo le domande fisse.</p>}
          {modulo.domande.map((d, i) => (
            <div key={i} className="card card-muted" style={{ marginBottom: 10 }}>
              <div className="row">
                <div className="field" style={{ flex: 3 }}><label htmlFor={`d-testo-${i}`}>Domanda {i + 1}</label>
                  <input id={`d-testo-${i}`} required maxLength={300} value={d.testo} onChange={(e) => cambia(i, "testo", e.target.value)} /></div>
                <div className="field"><label htmlFor={`d-tipo-${i}`}>Tipo di risposta</label>
                  <select id={`d-tipo-${i}`} value={d.tipo} onChange={(e) => cambia(i, "tipo", e.target.value)}>
                    {Object.entries(TIPI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
              </div>
              {d.tipo === "scelta" && (
                <div className="field"><label htmlFor={`d-opz-${i}`}>Opzioni (una per riga, da 2 a 10)</label>
                  <textarea id={`d-opz-${i}`} rows={3} value={d.opzioni} onChange={(e) => cambia(i, "opzioni", e.target.value)} /></div>
              )}
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
                  <input type="checkbox" style={{ width: "auto" }} checked={d.obbligatoria} onChange={(e) => cambia(i, "obbligatoria", e.target.checked)} /> Obbligatoria
                </label>
                <button type="button" className="secondary btn-sm" disabled={i === 0} onClick={() => sposta(i, -1)} aria-label={`Sposta in su la domanda ${i + 1}`}>↑</button>
                <button type="button" className="secondary btn-sm" disabled={i === modulo.domande.length - 1} onClick={() => sposta(i, 1)} aria-label={`Sposta in giù la domanda ${i + 1}`}>↓</button>
                <button type="button" className="danger btn-sm" onClick={() => setModulo({ ...modulo, domande: modulo.domande.filter((_, n) => n !== i) })}>Togli</button>
              </div>
            </div>
          ))}
          {modulo.domande.length < 20 && <p><button type="button" className="secondary" onClick={() => setModulo({ ...modulo, domande: [...modulo.domande, NUOVA()] })}>+ Aggiungi una domanda</button></p>}
          {errModulo && <div className="error-msg" role="alert">{errModulo}</div>}
          <button type="submit" disabled={invio}>{invio ? "Salvo..." : "Salva"}</button>{" "}
          <button type="button" className="secondary" onClick={() => setModulo(null)}>Annulla</button>
        </form>
      )}

      {!elenco && !errore && <p className="text-muted">Caricamento...</p>}
      {elenco && elenco.length === 0 && !modulo && <p className="empty-state">Nessun questionario: tutti i corsi usano solo le domande fisse. Creane uno per aggiungere altre domande.</p>}
      {elenco && elenco.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Questionario</th><th>Domande aggiuntive</th><th>Corsi che lo scelgono</th><th></th></tr></thead>
            <tbody>
              {elenco.map((q) => (
                <tr key={q.id}>
                  <td><strong>{q.nome}</strong> {q.is_default && <span className="badge green">predefinito</span>}</td>
                  <td>{q.domande.length === 0 ? <span className="text-muted">nessuna</span> : <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>{q.domande.map((d) => <li key={d.id}>{d.testo} <span className="text-muted">({TIPI[d.tipo]}{d.obbligatoria ? ", obbligatoria" : ""})</span></li>)}</ul>}</td>
                  <td>{q.n_corsi || <span className="text-muted">—</span>}</td>
                  <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                    <button type="button" className="btn-sm" onClick={() => { setErrModulo(null); setModulo(daModulo(q)); }}>Modifica</button>{" "}
                    <button type="button" className="danger btn-sm" onClick={() => elimina(q)}>Elimina</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
