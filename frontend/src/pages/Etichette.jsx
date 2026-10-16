import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import { aggiornaCacheFamiglie } from "../components/Etichette";

function Famiglia({ f, onCambiato, setErrore }) {
  const [nuova, setNuova] = useState("");
  const [modifica, setModifica] = useState(null);   // etichetta in modifica
  const [unisci, setUnisci] = useState(null);       // etichetta da unire
  const chiama = async (fn) => { setErrore(null); try { await fn(); aggiornaCacheFamiglie(); onCambiato(); return true; } catch (e) { setErrore(erroreDi(e, "Operazione non riuscita")); return false; } };  // true = riuscita: i moduli si chiudono solo allora
  const salvaFamiglia = (campi) => chiama(() => api.put(`/etichette/famiglie/${f.id}`, { nome: f.nome, descrizione: f.descrizione, scelta_multipla: f.scelta_multipla, obbligatoria: f.obbligatoria, archiviata: f.archiviata, ...campi }));
  const attive = f.etichette.filter((e) => !e.archiviata);

  return (
    <div className="card" style={f.archiviata ? { opacity: .6 } : undefined}>
      <div className="flex-between" style={{ alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ marginBottom: 2 }}>{f.nome}{f.archiviata && <span className="badge gray" style={{ marginLeft: 8 }}>archiviata</span>}</h3>
          {f.descrizione && <p className="text-muted" style={{ margin: 0, fontSize: 13 }}>{f.descrizione}</p>}
        </div>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 13 }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" style={{ width: "auto" }} checked={f.scelta_multipla} onChange={(e) => salvaFamiglia({ scelta_multipla: e.target.checked })} /> più di una per corso</label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" style={{ width: "auto" }} checked={f.obbligatoria} onChange={(e) => salvaFamiglia({ obbligatoria: e.target.checked })} /> obbligatoria</label>
          <button type="button" className="secondary btn-sm" onClick={() => salvaFamiglia({ archiviata: !f.archiviata })}>{f.archiviata ? "Ripristina" : "Archivia"}</button>
        </div>
      </div>

      <div className="table-wrap" style={{ marginTop: ".9rem" }}>
        <table>
          <thead><tr><th>Etichetta</th><th>Corsi</th><th>Esclusiva</th><th></th></tr></thead>
          <tbody>
            {f.etichette.map((e) => (
              <tr key={e.id} style={e.archiviata ? { opacity: .55 } : undefined}>
                <td>
                  {modifica?.id === e.id ? (
                    <form style={{ display: "flex", gap: 6 }} onSubmit={(ev) => { ev.preventDefault(); chiama(() => api.put(`/etichette/${e.id}`, { ...modifica })).then((ok) => ok && setModifica(null)); }}>
                      <input autoFocus value={modifica.nome} onChange={(ev) => setModifica({ ...modifica, nome: ev.target.value })} />
                      <button type="submit" className="btn-sm">Salva</button>
                      <button type="button" className="secondary btn-sm" onClick={() => setModifica(null)}>Annulla</button>
                    </form>
                  ) : <>{e.nome}{e.archiviata && <span className="badge gray" style={{ marginLeft: 6 }}>archiviata</span>}</>}
                  {unisci?.id === e.id && (
                    <div style={{ display: "flex", gap: 6, marginTop: 6, alignItems: "center", fontSize: 13 }}>
                      Unisci in
                      <select value={unisci.in || ""} onChange={(ev) => setUnisci({ ...unisci, in: ev.target.value })}>
                        <option value="">scegli...</option>
                        {attive.filter((x) => x.id !== e.id).map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}
                      </select>
                      <button type="button" className="btn-sm" disabled={!unisci.in} onClick={() => chiama(() => api.post(`/etichette/${e.id}/unisci`, { in_etichetta_id: unisci.in })).then((ok) => ok && setUnisci(null))}>Unisci</button>
                      <button type="button" className="secondary btn-sm" onClick={() => setUnisci(null)}>Annulla</button>
                    </div>
                  )}
                </td>
                <td>{e.corsi}</td>
                <td><input type="checkbox" style={{ width: "auto" }} title="Se scelta insieme ad altre della stessa famiglia compare un avviso (es. Trasversale)" checked={e.esclusiva}
                           onChange={(ev) => chiama(() => api.put(`/etichette/${e.id}`, { nome: e.nome, archiviata: e.archiviata, esclusiva: ev.target.checked }))} /></td>
                <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                  <button type="button" className="secondary btn-sm" onClick={() => setModifica({ id: e.id, nome: e.nome, esclusiva: e.esclusiva, archiviata: e.archiviata })}>Rinomina</button>{" "}
                  {!e.archiviata && attive.length > 1 && <><button type="button" className="secondary btn-sm" onClick={() => setUnisci({ id: e.id })}>Unisci...</button>{" "}</>}
                  {e.corsi > 0 || e.archiviata
                    ? <button type="button" className="secondary btn-sm" onClick={() => chiama(() => api.put(`/etichette/${e.id}`, { nome: e.nome, esclusiva: e.esclusiva, archiviata: !e.archiviata }))}>{e.archiviata ? "Ripristina" : "Archivia"}</button>
                    : <button type="button" className="danger btn-sm" onClick={() => window.confirm(`Eliminare «${e.nome}»?`) && chiama(() => api.delete(`/etichette/${e.id}`))}>Elimina</button>}
                </td>
              </tr>
            ))}
            {f.etichette.length === 0 && <tr><td colSpan={4} className="empty-state">Nessuna etichetta in questa famiglia.</td></tr>}
          </tbody>
        </table>
      </div>
      <form style={{ display: "flex", gap: 8, marginTop: ".8rem" }} onSubmit={(ev) => { ev.preventDefault(); if (nuova.trim()) chiama(() => api.post(`/etichette/famiglie/${f.id}/etichette`, { nome: nuova })).then((ok) => ok && setNuova("")); }}>
        <input placeholder={`Nuova etichetta in ${f.nome}`} value={nuova} onChange={(ev) => setNuova(ev.target.value)} style={{ maxWidth: 320 }} />
        <button type="submit" className="secondary">Aggiungi</button>
      </form>
    </div>
  );
}

export default function Etichette() {
  const [famiglie, setFamiglie] = useState([]);
  const [errore, setErrore] = useState(null);
  const [nuova, setNuova] = useState({ nome: "", descrizione: "", scelta_multipla: true, obbligatoria: false });
  const carica = () => api.get("/etichette", { params: { con_archiviate: true } }).then((r) => setFamiglie(r.data));
  useEffect(() => { carica(); }, []);

  async function creaFamiglia(e) {
    e.preventDefault(); setErrore(null);
    try { await api.post("/etichette/famiglie", nuova); setNuova({ nome: "", descrizione: "", scelta_multipla: true, obbligatoria: false }); aggiornaCacheFamiglie(); carica(); }
    catch (err) { setErrore(erroreDi(err, "Operazione non riuscita")); }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Etichette dei corsi</h2>
        <p>Classificano i corsi per famiglia (di che cosa parlano, quale norma soddisfano, per chi valgono, perché sono obbligatori). Servono a filtrare registro, matrice e pacchetto per l'ispezione: ad esempio tutto ciò che riguarda il D.Lgs 81/08 per un audit ISO 45001.</p></div></div>
      {errore && <div className="error-msg">{errore}</div>}
      {famiglie.map((f) => <Famiglia key={f.id} f={f} onCambiato={carica} setErrore={setErrore} />)}
      <form className="card" onSubmit={creaFamiglia}>
        <h3>Nuova famiglia</h3>
        <div className="row">
          <div className="field"><label>Nome</label><input required value={nuova.nome} onChange={(e) => setNuova({ ...nuova, nome: e.target.value })} placeholder="es. Destinatari" /></div>
          <div className="field" style={{ flex: 2 }}><label>A cosa serve (facoltativo)</label><input value={nuova.descrizione} onChange={(e) => setNuova({ ...nuova, descrizione: e.target.value })} /></div>
        </div>
        <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 13 }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" style={{ width: "auto" }} checked={nuova.scelta_multipla} onChange={(e) => setNuova({ ...nuova, scelta_multipla: e.target.checked })} /> più di una per corso</label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" style={{ width: "auto" }} checked={nuova.obbligatoria} onChange={(e) => setNuova({ ...nuova, obbligatoria: e.target.checked })} /> obbligatoria</label>
        </div>
        <button type="submit">Crea famiglia</button>
      </form>
    </div>
  );
}
