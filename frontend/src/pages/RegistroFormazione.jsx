import React, { useEffect, useState } from "react";
import api, { downloadFile } from "../api";
import ExportButton from "../components/ExportButton";
import { FiltroEtichette } from "../components/Etichette";
import { elencoUffici } from "../uffici";

const BADGE = { valido: "green", scaduto: "red", non_completato: "red", in_corso: "gray", non_applicabile: "green", da_aggiornare: "red" };
const LABEL = { valido: "valido", scaduto: "scaduto", non_completato: "non completato", in_corso: "in corso", non_applicabile: "completato", da_aggiornare: "da aggiornare (nuova versione)" };

export default function RegistroFormazione() {
  const [righe, setRighe] = useState([]);
  const [uffici, setUffici] = useState([]);
  const [filtri, setFiltri] = useState({ ufficio_id: "", da: "", a: "", user_id: "", etichette: [] });
  const [persone, setPersone] = useState([]);
  const [scarico, setScarico] = useState(false);
  const [errore, setErrore] = useState(null);

  useEffect(() => { api.get("/groups").then((r) => setUffici(elencoUffici(r.data))); }, []);
  useEffect(() => { api.get("/auth/users/simple").then((r) => setPersone(r.data)); }, []);

  function carica() {
    const params = {};
    if (filtri.ufficio_id) params.ufficio_id = filtri.ufficio_id;
    if (filtri.user_id) params.user_id = filtri.user_id;
    if (filtri.da) params.da = filtri.da;
    if (filtri.a) params.a = filtri.a;
    if (filtri.etichette.length) params.etichette = filtri.etichette;
    api.get("/registro", { params, paramsSerializer: { indexes: null } }).then((r) => setRighe(r.data));
  }
  useEffect(() => { carica(); }, []); // eslint-disable-line

  function exportPath() {
    const params = {};
    if (filtri.ufficio_id) params.ufficio_id = filtri.ufficio_id;
    if (filtri.user_id) params.user_id = filtri.user_id;
    if (filtri.da) params.da = filtri.da;
    if (filtri.a) params.a = filtri.a;
    const p = new URLSearchParams(params);
    filtri.etichette.forEach((id) => p.append("etichette", id));
    const qs = p.toString();
    return `/registro/export${qs ? `?${qs}` : ""}`;
  }

  async function scaricaPacchetto() {
    const params = new URLSearchParams();
    ["ufficio_id", "user_id", "da", "a"].forEach((k) => { if (filtri[k]) params.set(k, filtri[k]); });
    filtri.etichette.forEach((id) => params.append("etichette", id));
    setScarico(true); setErrore(null);
    try { await downloadFile(`/registro/pacchetto-ispezione?${params.toString()}`, "pacchetto-ispezione.zip"); }
    catch (err) {
      // la risposta e' un blob: il messaggio del server va letto da li'
      let msg = "Errore nella creazione del pacchetto";
      try { msg = JSON.parse(await err.response.data.text()).detail || msg; } catch { /* ignore */ }
      setErrore(msg);
    } finally { setScarico(false); }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Registro formazione</h2>
          <p>Stato di compliance per persona e corso — pensato per un controllo ispettivo.</p>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <div className="field">
            <label>Reparto/ufficio</label>
            <select value={filtri.ufficio_id} onChange={(e) => setFiltri({ ...filtri, ufficio_id: e.target.value })}>
              <option value="">Tutti</option>
              {uffici.map((u) => <option key={u.id} value={u.id}>{u.etichetta}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Persona</label>
            <select value={filtri.user_id} onChange={(e) => setFiltri({ ...filtri, user_id: e.target.value })}>
              <option value="">Tutte</option>
              {persone.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 220 }}><FiltroEtichette valore={filtri.etichette} onChange={(v) => setFiltri({ ...filtri, etichette: v })} /></div>
          <div className="field"><label>Completati dal</label><input type="date" value={filtri.da} onChange={(e) => setFiltri({ ...filtri, da: e.target.value })} /></div>
          <div className="field"><label>Completati al</label><input type="date" value={filtri.a} onChange={(e) => setFiltri({ ...filtri, a: e.target.value })} /></div>
          <div className="field" style={{ alignSelf: "flex-end" }}>
            <button type="button" onClick={carica}>Filtra</button>{" "}
            <ExportButton path={exportPath()} filename="registro_formazione" />{" "}
            <button type="button" className="secondary" onClick={scaricaPacchetto} disabled={scarico}
              title="ZIP con registro, matrice, attestati e indice per il perimetro scelto">{scarico ? "Preparo..." : "Pacchetto ispezione"}</button>
          </div>
        </div>
      </div>

      {errore && <div className="error-msg">{errore}</div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Persona</th><th>Uffici</th><th>Corso</th><th>Edizione</th><th>Completato il</th><th>Scade il</th><th>Stato</th></tr></thead>
          <tbody>
            {righe.map((r, i) => (
              <tr key={i}>
                <td>{r.persona}<br /><span className="text-muted" style={{ fontSize: 12 }}>{r.email}</span></td>
                <td>{r.uffici.join(", ")}</td>
                <td>{r.corso}</td>
                <td>{r.data_edizione ? new Date(r.data_edizione).toLocaleDateString("it-IT") : "-"}</td>
                <td>{r.data_completamento ? new Date(r.data_completamento).toLocaleDateString("it-IT") : "-"}</td>
                <td>{r.scade_il ? new Date(r.scade_il).toLocaleDateString("it-IT") : "-"}</td>
                <td>
                  <span className={`badge ${BADGE[r.stato_compliance]}`}>{LABEL[r.stato_compliance]}</span>{" "}
                  {r.aggiornamento_disponibile && <span className="badge gray">aggiornamento disponibile</span>}
                </td>
              </tr>
            ))}
            {righe.length === 0 && <tr><td colSpan={7} className="empty-state">Nessun dato per i filtri selezionati.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
