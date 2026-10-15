import React, { useEffect, useState, useMemo } from "react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import api from "../api";
import ExportButton from "../components/ExportButton";
import { FiltroEtichette } from "../components/Etichette";

const METRICHE = [
  { key: "tasso_completamento_pct", label: "Tasso di completamento %" },
  { key: "punteggio_test_medio", label: "Punteggio test medio" },
  { key: "gradimento_corso_medio", label: "Gradimento corso (1-5)" },
  { key: "gradimento_docenti_medio", label: "Gradimento docenti (1-5)" },
  { key: "ore_erogate", label: "Ore erogate" },
];

const TABS = [
  { key: "per-corso", label: "Per corso" },
  { key: "per-docente", label: "Per docente" },
  { key: "andamento", label: "Andamento nel tempo" },
  { key: "confronto-edizioni", label: "Confronto edizioni" },
  { key: "confronto-versioni", label: "Confronto versioni" },
];

function fmt(v) { return v === null || v === undefined ? "-" : v; }

export default function DashboardKpi() {
  const [tab, setTab] = useState("per-corso");
  const [metrica, setMetrica] = useState("tasso_completamento_pct");
  const [filtri, setFiltri] = useState({ corso_id: "", docente_id: "", ufficio_id: "", da: "", a: "", etichette: [] });
  const [corsi, setCorsi] = useState([]);
  const [docenti, setDocenti] = useState([]);
  const [uffici, setUffici] = useState([]);
  const [riepilogo, setRiepilogo] = useState(null);
  const [perCorso, setPerCorso] = useState([]);
  const [perDocente, setPerDocente] = useState([]);
  const [andamento, setAndamento] = useState([]);
  const [confrontoEdizioni, setConfrontoEdizioni] = useState([]);
  const [confrontoVersioni, setConfrontoVersioni] = useState([]);

  useEffect(() => {
    api.get("/corsi").then((r) => setCorsi(r.data));
    api.get("/dashboard/kpi/docenti").then((r) => setDocenti(r.data));
    api.get("/groups").then((r) => setUffici(r.data.filter((g) => g.is_ufficio)));
  }, []);

  const paramsBase = useMemo(() => {
    const p = {};
    if (filtri.corso_id) p.corso_id = filtri.corso_id;
    if (filtri.docente_id) p.docente_id = filtri.docente_id;
    if (filtri.ufficio_id) p.ufficio_id = filtri.ufficio_id;
    if (filtri.da) p.da = filtri.da;
    if (filtri.a) p.a = filtri.a;
    if (filtri.etichette.length) p.etichette = filtri.etichette;
    return p;
  }, [filtri]);

  useEffect(() => {
    api.get("/dashboard/kpi/riepilogo", { params: paramsBase }).then((r) => setRiepilogo(r.data));
    api.get("/dashboard/kpi/per-corso", { params: paramsBase }).then((r) => setPerCorso(r.data));
    api.get("/dashboard/kpi/per-docente", { params: paramsBase }).then((r) => setPerDocente(r.data));
    api.get("/dashboard/kpi/andamento", { params: paramsBase }).then((r) => setAndamento(r.data));
    if (filtri.corso_id) {
      api.get("/dashboard/kpi/confronto-edizioni", { params: paramsBase }).then((r) => setConfrontoEdizioni(r.data));
      api.get("/dashboard/kpi/confronto-versioni", { params: { corso_id: filtri.corso_id, ufficio_id: filtri.ufficio_id || undefined } }).then((r) => setConfrontoVersioni(r.data));
    } else {
      setConfrontoEdizioni([]); setConfrontoVersioni([]);
    }
  }, [paramsBase]); // eslint-disable-line

  function exportPath(vista) {
    const p = new URLSearchParams();
    Object.entries(paramsBase).forEach(([chiave, v]) => (Array.isArray(v) ? v.forEach((x) => p.append(chiave, x)) : p.set(chiave, v)));
    const qs = p.toString();
    return `/dashboard/kpi/export?vista=${vista}${qs ? `&${qs}` : ""}`;
  }

  const metricaLabel = METRICHE.find((m) => m.key === metrica)?.label;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Dashboard KPI</h2>
          <p>Reportistica per corso, docente e periodo — confronti tra edizioni e tra versioni del contenuto.</p>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <div className="field">
            <label>Corso</label>
            <select value={filtri.corso_id} onChange={(e) => setFiltri({ ...filtri, corso_id: e.target.value })}>
              <option value="">Tutti</option>
              {corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Docente</label>
            <select value={filtri.docente_id} onChange={(e) => setFiltri({ ...filtri, docente_id: e.target.value })}>
              <option value="">Tutti</option>
              {docenti.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Reparto/ufficio</label>
            <select value={filtri.ufficio_id} onChange={(e) => setFiltri({ ...filtri, ufficio_id: e.target.value })}>
              <option value="">Tutti</option>
              {uffici.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
        </div>
        <div className="row">
          <div className="field" style={{ minWidth: 240 }}><FiltroEtichette valore={filtri.etichette} onChange={(v) => setFiltri({ ...filtri, etichette: v })} /></div>
          <div className="field"><label>Sessioni dal</label><input type="date" value={filtri.da} onChange={(e) => setFiltri({ ...filtri, da: e.target.value })} /></div>
          <div className="field"><label>Sessioni al</label><input type="date" value={filtri.a} onChange={(e) => setFiltri({ ...filtri, a: e.target.value })} /></div>
          <div className="field">
            <label>Metrica nei grafici</label>
            <select value={metrica} onChange={(e) => setMetrica(e.target.value)}>
              {METRICHE.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      {riepilogo && (
        <div className="kpi-grid">
          <div className="kpi-card"><div className="kpi-value">{riepilogo.n_edizioni}</div><div className="kpi-label">Edizioni</div></div>
          <div className="kpi-card"><div className="kpi-value">{riepilogo.n_iscrizioni}</div><div className="kpi-label">Iscrizioni</div></div>
          <div className="kpi-card"><div className="kpi-value">{fmt(riepilogo.tasso_completamento_pct)}{riepilogo.tasso_completamento_pct !== null ? "%" : ""}</div><div className="kpi-label">Tasso completamento</div></div>
          <div className="kpi-card"><div className="kpi-value">{fmt(riepilogo.punteggio_test_medio)}</div><div className="kpi-label">Punteggio test medio</div></div>
          <div className="kpi-card"><div className="kpi-value">{fmt(riepilogo.gradimento_corso_medio)}</div><div className="kpi-label">Gradimento corso</div></div>
          <div className="kpi-card"><div className="kpi-value">{fmt(riepilogo.gradimento_docenti_medio)}</div><div className="kpi-label">Gradimento docenti</div></div>
          <div className="kpi-card"><div className="kpi-value">{fmt(riepilogo.ore_erogate)}</div><div className="kpi-label">Ore erogate</div></div>
          {riepilogo.delta_pre_post !== null && riepilogo.delta_pre_post !== undefined && (
            <div className="kpi-card"><div className={`kpi-value ${riepilogo.delta_pre_post >= 0 ? "ok" : "bad"}`}>{riepilogo.delta_pre_post > 0 ? "+" : ""}{riepilogo.delta_pre_post}</div><div className="kpi-label">Delta pre/post test</div></div>
          )}
        </div>
      )}

      <div className="tabs">
        {TABS.map((t) => <button type="button" aria-pressed={tab === t.key} key={t.key} className={`tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>{t.label}</button>)}
      </div>

      {tab === "per-corso" && (
        <>
          <div className="card">
            <div className="flex-between"><h3>Per corso — {metricaLabel}</h3><ExportButton path={exportPath("per-corso")} filename="kpi_per_corso" /></div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={perCorso}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="corso_titolo" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey={metrica} fill="#0E7C66" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Corso</th><th>Edizioni</th><th>Iscrizioni</th><th>Completamento</th><th>Punteggio test</th><th>Gradimento corso</th><th>Gradimento docenti</th><th>Ore</th></tr></thead>
              <tbody>
                {perCorso.map((r) => (
                  <tr key={r.corso_id}>
                    <td>{r.corso_titolo}</td><td>{r.n_edizioni}</td><td>{r.n_iscrizioni}</td>
                    <td>{fmt(r.tasso_completamento_pct)}{r.tasso_completamento_pct !== null ? "%" : ""}</td>
                    <td>{fmt(r.punteggio_test_medio)}</td><td>{fmt(r.gradimento_corso_medio)}</td>
                    <td>{fmt(r.gradimento_docenti_medio)}</td><td>{fmt(r.ore_erogate)}</td>
                  </tr>
                ))}
                {perCorso.length === 0 && <tr><td colSpan={8} className="empty-state">Nessun dato per i filtri selezionati.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "per-docente" && (
        <>
          <div className="card">
            <div className="flex-between"><h3>Per docente — {metricaLabel}</h3><ExportButton path={exportPath("per-docente")} filename="kpi_per_docente" /></div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={perDocente}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="docente_nome" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey={metrica} fill="#F5A623" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Docente</th><th>Edizioni</th><th>Iscrizioni</th><th>Completamento</th><th>Punteggio test</th><th>Gradimento corso</th><th>Gradimento docente</th></tr></thead>
              <tbody>
                {perDocente.map((r) => (
                  <tr key={r.docente_id}>
                    <td>{r.docente_nome}</td><td>{r.n_edizioni}</td><td>{r.n_iscrizioni}</td>
                    <td>{fmt(r.tasso_completamento_pct)}{r.tasso_completamento_pct !== null ? "%" : ""}</td>
                    <td>{fmt(r.punteggio_test_medio)}</td><td>{fmt(r.gradimento_corso_medio)}</td>
                    <td>{fmt(r.gradimento_docenti_medio)}</td>
                  </tr>
                ))}
                {perDocente.length === 0 && <tr><td colSpan={7} className="empty-state">Nessun dato per i filtri selezionati.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "andamento" && (
        <>
          <div className="card">
            <div className="flex-between"><h3>Andamento nel tempo — {metricaLabel}</h3><ExportButton path={exportPath("andamento")} filename="kpi_andamento" /></div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={andamento}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="mese" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey={metrica} stroke="#0E7C66" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Mese</th><th>Edizioni</th><th>Completati</th><th>Completamento</th><th>Punteggio test</th><th>Gradimento</th></tr></thead>
              <tbody>
                {andamento.map((r) => (
                  <tr key={r.mese}>
                    <td>{r.mese}</td><td>{r.n_edizioni}</td><td>{r.n_completati}</td>
                    <td>{fmt(r.tasso_completamento_pct)}{r.tasso_completamento_pct !== null ? "%" : ""}</td>
                    <td>{fmt(r.punteggio_test_medio)}</td><td>{fmt(r.gradimento_corso_medio)}</td>
                  </tr>
                ))}
                {andamento.length === 0 && <tr><td colSpan={6} className="empty-state">Nessun dato per i filtri selezionati.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "confronto-edizioni" && (
        !filtri.corso_id ? <div className="card card-muted">Seleziona un corso per confrontare le sue edizioni.</div> : (
          <>
            <div className="card">
              <div className="flex-between"><h3>Confronto edizioni — {metricaLabel}</h3><ExportButton path={exportPath("confronto-edizioni")} filename="kpi_confronto_edizioni" /></div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={confrontoEdizioni.map((r, i) => ({ ...r, etichetta: r.data_inizio ? new Date(r.data_inizio).toLocaleDateString("it-IT") : `#${i + 1}` }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="etichetta" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey={metrica} fill="#0E7C66" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Data</th><th>Modalità</th><th>Versione corso</th><th>Iscrizioni</th><th>Completamento</th><th>Punteggio test</th><th>Gradimento</th></tr></thead>
                <tbody>
                  {confrontoEdizioni.map((r) => (
                    <tr key={r.edizione_id}>
                      <td>{r.data_inizio ? new Date(r.data_inizio).toLocaleDateString("it-IT") : "-"}</td>
                      <td>{r.modalita}</td>
                      <td>{r.versione_corso ? <span className="badge gray">v{r.versione_corso}</span> : "-"}</td>
                      <td>{r.n_iscrizioni}</td>
                      <td>{fmt(r.tasso_completamento_pct)}{r.tasso_completamento_pct !== null ? "%" : ""}</td>
                      <td>{fmt(r.punteggio_test_medio)}</td><td>{fmt(r.gradimento_corso_medio)}</td>
                    </tr>
                  ))}
                  {confrontoEdizioni.length === 0 && <tr><td colSpan={7} className="empty-state">Nessuna edizione per questo corso con i filtri selezionati.</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )
      )}

      {tab === "confronto-versioni" && (
        !filtri.corso_id ? <div className="card card-muted">Seleziona un corso per confrontare le sue versioni.</div> : (
          <div className="table-wrap">
            <div className="flex-between"><h3>Confronto versioni</h3><ExportButton path={exportPath("confronto-versioni")} filename="kpi_confronto_versioni" /></div>
            <table>
              <thead><tr><th>Versione</th><th>Completati</th><th>Punteggio test medio</th><th>Gradimento corso medio</th></tr></thead>
              <tbody>
                {confrontoVersioni.map((r) => (
                  <tr key={r.versione}>
                    <td><span className="badge gray">v{r.versione}</span></td>
                    <td>{r.n_completati}</td><td>{fmt(r.punteggio_test_medio)}</td><td>{fmt(r.gradimento_corso_medio)}</td>
                  </tr>
                ))}
                {confrontoVersioni.length === 0 && <tr><td colSpan={4} className="empty-state">Nessun completamento registrato per questo corso.</td></tr>}
              </tbody>
            </table>
            <p className="text-muted" style={{ fontSize: 13, marginTop: 10 }}>
              Il confronto considera solo chi ha completato il corso in ciascuna versione (la versione è registrata al momento del completamento).
            </p>
          </div>
        )
      )}
    </div>
  );
}
