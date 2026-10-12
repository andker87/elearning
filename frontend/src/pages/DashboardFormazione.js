import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import api from "../api";
import { FiltroEtichette } from "../components/Etichette";
import ExportButton from "../components/ExportButton";

const TIPO_LABEL = {
  scaduto: "Scaduto", da_aggiornare: "Da aggiornare", non_completato: "Non completato",
  in_scadenza: "In scadenza", scoperto: "Mai iniziato",
};
const TIPO_BADGE = {
  scaduto: "red", da_aggiornare: "red", non_completato: "red", in_scadenza: "yellow", scoperto: "gray",
};

function kpiTone(valore, sogliaWarn, sogliaBad) {
  if (valore === null || valore === undefined) return "";
  if (valore >= sogliaBad) return "bad";
  if (valore >= sogliaWarn) return "warn";
  return "";
}

export default function DashboardFormazione() {
  const [kpi, setKpi] = useState(null);
  const [persone, setPersone] = useState([]);
  const [sessioni, setSessioni] = useState([]);
  const [uffici, setUffici] = useState([]);
  const [corsi, setCorsi] = useState([]);
  const [edizioni, setEdizioni] = useState([]);
  const [filtri, setFiltri] = useState({ ufficio_id: "", corso_id: "", etichette: [] });
  const [tipoAttivo, setTipoAttivo] = useState(null);
  const [iscrizioneAperta, setIscrizioneAperta] = useState(null); // { userId, corsoId }
  const [edizioneScelta, setEdizioneScelta] = useState("");
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    api.get("/groups").then((r) => setUffici(r.data.filter((g) => g.is_ufficio)));
    api.get("/corsi").then((r) => setCorsi(r.data));
    api.get("/edizioni").then((r) => setEdizioni(r.data));
  }, []);

  function carica() {
    const params = {};
    if (filtri.ufficio_id) params.ufficio_id = filtri.ufficio_id;
    if (filtri.corso_id) params.corso_id = filtri.corso_id;
    if (filtri.etichette.length) params.etichette = filtri.etichette;
    api.get("/dashboard/formazione/kpi", { params }).then((r) => setKpi(r.data));
    api.get("/dashboard/formazione/persone", { params: { ...params, tipo: tipoAttivo || undefined } }).then((r) => setPersone(r.data));
    api.get("/dashboard/formazione/sessioni-imminenti", { params: filtri.etichette.length ? { etichette: filtri.etichette } : {} }).then((r) => setSessioni(r.data));
  }
  useEffect(carica, [filtri.ufficio_id, filtri.corso_id, filtri.etichette, tipoAttivo]); // eslint-disable-line

  const datiGrafico = useMemo(() => {
    if (!kpi) return [];
    return [
      { nome: "Scaduti", valore: kpi.n_scaduti },
      { nome: "Da aggiornare", valore: kpi.n_da_aggiornare },
      { nome: "Non completato", valore: kpi.n_non_completato },
      { nome: "In scadenza", valore: kpi.n_in_scadenza_30gg },
      { nome: "Mai iniziato", valore: kpi.n_corsi_scoperti },
    ];
  }, [kpi]);

  function toggleTipo(t) { setTipoAttivo(tipoAttivo === t ? null : t); }

  function apriIscrizione(userId, corsoId) {
    setIscrizioneAperta({ userId, corsoId });
    setEdizioneScelta("");
  }

  async function confermaIscrizione() {
    if (!edizioneScelta) return;
    try {
      const r = await api.post(`/edizioni/${edizioneScelta}/iscrizioni`, [iscrizioneAperta.userId]);
      setMsg(r.data.non_iscritti?.length ? `Iscrizione non effettuata: ${r.data.non_iscritti[0].motivo}` : "Iscrizione effettuata.");
    } catch (err) { setMsg(err.response?.data?.detail || "Iscrizione non riuscita"); }
    setIscrizioneAperta(null);
    carica();
  }

  async function invioSollecito(userId, corsoId) {
    await api.post("/dashboard/formazione/sollecito", { user_id: userId, corso_id: corsoId });
    setMsg("Sollecito inviato.");
  }

  function exportPath() {
    const params = {};
    if (filtri.ufficio_id) params.ufficio_id = filtri.ufficio_id;
    if (filtri.corso_id) params.corso_id = filtri.corso_id;
    const p = new URLSearchParams(params);
    filtri.etichette.forEach((id) => p.append("etichette", id));
    const qs = p.toString();
    return `/registro/export${qs ? `?${qs}` : ""}`;
  }

  const edizioniPerCorso = (corsoId) => edizioni.filter((e) => e.corso_id === corsoId && e.stato !== "chiusa");

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Dashboard Ufficio Formazione</h2>
          <p>Chi è scoperto, cosa scade a breve, e azioni rapide — iscrizioni e solleciti senza uscire da qui.</p>
        </div>
        <ExportButton path={exportPath()} filename="registro_formazione" label="Esporta registro" />
      </div>

      <div className="card">
        <div className="row">
          <div className="field">
            <label>Reparto/ufficio</label>
            <select value={filtri.ufficio_id} onChange={(e) => setFiltri({ ...filtri, ufficio_id: e.target.value })}>
              <option value="">Tutti</option>
              {uffici.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Corso</label>
            <select value={filtri.corso_id} onChange={(e) => setFiltri({ ...filtri, corso_id: e.target.value })}>
              <option value="">Tutti</option>
              {corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 240 }}><FiltroEtichette valore={filtri.etichette} onChange={(v) => setFiltri({ ...filtri, etichette: v })} /></div>
        </div>
      </div>

      {kpi && (
        <div className="kpi-grid">
          <div className="kpi-card" onClick={() => { setTipoAttivo(null); }}>
            <div className={`kpi-value ${kpi.compliance_pct === null ? "" : kpi.compliance_pct >= 90 ? "ok" : kpi.compliance_pct >= 75 ? "warn" : "bad"}`}>
              {kpi.compliance_pct === null ? "-" : `${kpi.compliance_pct}%`}
            </div>
            <div className="kpi-label">Compliance (su {kpi.n_persone_in_scope} persone)</div>
          </div>
          <div className={`kpi-card ${tipoAttivo === "scaduto" ? "active" : ""}`} onClick={() => toggleTipo("scaduto")}>
            <div className={`kpi-value ${kpiTone(kpi.n_scaduti, 1, 5)}`}>{kpi.n_scaduti}</div>
            <div className="kpi-label">Corsi scaduti</div>
          </div>
          <div className={`kpi-card ${tipoAttivo === "da_aggiornare" ? "active" : ""}`} onClick={() => toggleTipo("da_aggiornare")}>
            <div className={`kpi-value ${kpiTone(kpi.n_da_aggiornare, 1, 5)}`}>{kpi.n_da_aggiornare}</div>
            <div className="kpi-label">Da aggiornare (nuova versione)</div>
          </div>
          <div className={`kpi-card ${tipoAttivo === "non_completato" ? "active" : ""}`} onClick={() => toggleTipo("non_completato")}>
            <div className={`kpi-value ${kpiTone(kpi.n_non_completato, 1, 5)}`}>{kpi.n_non_completato}</div>
            <div className="kpi-label">Non completato</div>
          </div>
          <div className={`kpi-card ${tipoAttivo === "in_scadenza" ? "active" : ""}`} onClick={() => toggleTipo("in_scadenza")}>
            <div className={`kpi-value ${kpiTone(kpi.n_in_scadenza_30gg, 1, 5)}`}>{kpi.n_in_scadenza_30gg}</div>
            <div className="kpi-label">In scadenza (30gg)</div>
          </div>
          <div className={`kpi-card ${tipoAttivo === "scoperto" ? "active" : ""}`} onClick={() => toggleTipo("scoperto")}>
            <div className={`kpi-value ${kpiTone(kpi.n_persone_scoperte, 1, 5)}`}>{kpi.n_persone_scoperte}</div>
            <div className="kpi-label">Persone mai partite ({kpi.n_corsi_scoperti} corsi)</div>
          </div>
          <div className="kpi-card" onClick={() => document.getElementById("sessioni-imminenti")?.scrollIntoView({ behavior: "smooth" })}>
            <div className="kpi-value">{kpi.n_sessioni_imminenti}</div>
            <div className="kpi-label">Sessioni nei prossimi 14gg</div>
          </div>
        </div>
      )}

      {kpi && datiGrafico.some((d) => d.valore > 0) && (
        <div className="card">
          <h3>Problemi aperti per categoria</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={datiGrafico}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="nome" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="valore" fill="#0E7C66" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {msg && <div className="card card-muted">{msg}</div>}

      <div className="chip-row">
        <span className="chip-row-label" style={{ fontSize: 13, color: "var(--text3)", alignSelf: "center" }}>Filtra per tipo:</span>
        {Object.keys(TIPO_LABEL).map((t) => (
          <span key={t} className={`chip ${tipoAttivo === t ? "active" : ""}`} onClick={() => toggleTipo(t)}>{TIPO_LABEL[t]}</span>
        ))}
        {tipoAttivo && <span className="chip" onClick={() => setTipoAttivo(null)}>Azzera filtro</span>}
      </div>

      <div className="table-wrap" style={{ marginBottom: "1.1rem" }}>
        <table>
          <thead><tr><th>Persona</th><th>Problemi</th><th></th></tr></thead>
          <tbody>
            {persone.map((p) => (
              <tr key={p.user_id}>
                <td>{p.full_name}<br /><span className="text-muted" style={{ fontSize: 12 }}>{p.email}</span></td>
                <td>
                  {p.problemi.map((pr, idx) => (
                    <div key={idx} style={{ marginBottom: 6 }}>
                      <span className={`badge ${TIPO_BADGE[pr.tipo]}`}>{TIPO_LABEL[pr.tipo]}</span>{" "}
                      {pr.corso_titolo}{" "}
                      <button className="secondary btn-sm" onClick={() => apriIscrizione(p.user_id, pr.corso_id)}>Iscrivi</button>{" "}
                      <button className="secondary btn-sm" onClick={() => invioSollecito(p.user_id, pr.corso_id)}>Sollecita</button>
                    </div>
                  ))}
                </td>
                <td></td>
              </tr>
            ))}
            {persone.length === 0 && <tr><td colSpan={3} className="empty-state">Nessun problema aperto per i filtri selezionati.</td></tr>}
          </tbody>
        </table>
      </div>

      {iscrizioneAperta && (
        <div className="card">
          <h3>Iscrivi a una sessione</h3>
          <div className="row">
            <div className="field">
              <label>Sessione disponibile</label>
              <select value={edizioneScelta} onChange={(e) => setEdizioneScelta(e.target.value)}>
                <option value="">-- seleziona --</option>
                {edizioniPerCorso(iscrizioneAperta.corsoId).map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.modalita} — {e.data_inizio ? new Date(e.data_inizio).toLocaleDateString("it-IT") : "senza data"}
                  </option>
                ))}
              </select>
              {edizioniPerCorso(iscrizioneAperta.corsoId).length === 0 && <p className="text-muted" style={{ fontSize: 13 }}>Nessuna sessione aperta per questo corso — creane una dalla pagina Sessioni.</p>}
            </div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button type="button" onClick={confermaIscrizione} disabled={!edizioneScelta}>Conferma iscrizione</button>{" "}
              <button type="button" className="secondary" onClick={() => setIscrizioneAperta(null)}>Annulla</button>
            </div>
          </div>
        </div>
      )}

      <h3 id="sessioni-imminenti">Sessioni nei prossimi 14 giorni</h3>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Data</th><th>Posti</th><th></th></tr></thead>
          <tbody>
            {sessioni.map((s) => (
              <tr key={s.id}>
                <td>{s.corso_titolo}</td>
                <td>{s.modalita}</td>
                <td>{s.data_inizio ? new Date(s.data_inizio).toLocaleString("it-IT") : "-"}</td>
                <td>{s.posti_max ? `${s.n_iscritti}/${s.posti_max}${s.posti_liberi === 0 ? " (pieno)" : ""}` : `${s.n_iscritti} (illimitati)`}</td>
                <td><Link to={`/sessioni/${s.id}`}>Apri</Link></td>
              </tr>
            ))}
            {sessioni.length === 0 && <tr><td colSpan={5} className="empty-state">Nessuna sessione nei prossimi 14 giorni.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
