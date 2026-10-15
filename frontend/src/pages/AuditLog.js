import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import ExportButton from "../components/ExportButton";

const VUOTI = { q: "", action: "", entity_type: "", utente: "", ip: "", da: "", a: "" };
const PER_PAGINA = 50;

function badgeAzione(a) {
  if (a === "LOGIN_FAILED" || a.startsWith("DELETE") || a.startsWith("UNASSIGN") || a === "CANCEL_ENROLLMENT" || a === "SELF_ENROLL_REJECT") return "red";
  if (a === "LOGIN") return "gray";
  if (a.startsWith("CREATE") || a.includes("APPROVE") || a === "ENROLL" || a === "SELF_ENROLL") return "green";
  return "accent";
}

function parametri(filtri) {
  const p = {};
  Object.entries(filtri).forEach(([k, v]) => { if (v) p[k] = v; });
  return p;
}

export default function AuditLog() {
  const [filtri, setFiltri] = useState(VUOTI);
  const [applicati, setApplicati] = useState(VUOTI);
  const [pagina, setPagina] = useState(1);
  const [dati, setDati] = useState({ totale: 0, items: [] });
  const [opzioni, setOpzioni] = useState({ azioni: [], entita: [] });
  const [aperta, setAperta] = useState(null);
  const [errore, setErrore] = useState(null);

  useEffect(() => { api.get("/admin/audit/filtri").then((r) => setOpzioni(r.data)).catch((err) => setErrore(erroreDi(err, "Impossibile caricare i filtri"))); }, []);

  // Se i filtri cambiano mentre una richiesta e' ancora in corso, la risposta vecchia viene scartata.
  useEffect(() => {
    let attiva = true;
    api.get("/admin/audit", { params: { ...parametri(applicati), pagina, per_pagina: PER_PAGINA } })
      .then((r) => { if (attiva) { setDati(r.data); setErrore(null); } })
      .catch((err) => { if (attiva) setErrore(erroreDi(err, "Errore nel caricamento")); });
    return () => { attiva = false; };
  }, [applicati, pagina]);

  function applica(e) {
    e.preventDefault();
    setPagina(1);
    setApplicati(filtri);
  }
  function azzera() {
    setFiltri(VUOTI);
    setPagina(1);
    setApplicati(VUOTI);
  }
  const percorsoExport = () => {
    const qs = new URLSearchParams(parametri(applicati)).toString();
    return `/admin/audit/export${qs ? `?${qs}` : ""}`;
  };
  const set = (k) => (e) => setFiltri({ ...filtri, [k]: e.target.value });
  const pagineTotali = Math.max(1, Math.ceil(dati.totale / PER_PAGINA));

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Audit log</h2>
          <p>Chi ha fatto cosa, quando e da dove. Registro in sola lettura delle azioni sulla piattaforma.</p>
        </div>
        <ExportButton path={percorsoExport()} filename="audit_log" />
      </div>

      <form className="card" onSubmit={applica}>
        <div className="row">
          <div className="field"><label>Cerca (nome, dettaglio, id, utente)</label><input value={filtri.q} onChange={set("q")} placeholder="Testo libero" /></div>
          <div className="field"><label>Azione</label>
            <select value={filtri.action} onChange={set("action")}>
              <option value="">Tutte</option>
              {opzioni.azioni.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="field"><label>Tipo entità</label>
            <select value={filtri.entity_type} onChange={set("entity_type")}>
              <option value="">Tutte</option>
              {opzioni.entita.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>
        <div className="row">
          <div className="field"><label>Utente (email)</label><input value={filtri.utente} onChange={set("utente")} /></div>
          <div className="field"><label>Indirizzo IP</label><input value={filtri.ip} onChange={set("ip")} /></div>
          <div className="field"><label>Dal</label><input type="date" value={filtri.da} onChange={set("da")} /></div>
          <div className="field"><label>Al</label><input type="date" value={filtri.a} onChange={set("a")} /></div>
          <div className="field" style={{ alignSelf: "flex-end", flex: "0 0 auto" }}>
            <button type="submit">Filtra</button>{" "}
            <button type="button" className="secondary" onClick={azzera}>Azzera</button>
          </div>
        </div>
      </form>

      {errore && <div className="error-msg">{errore}</div>}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Data e ora</th><th>Utente</th><th>Azione</th><th>Entità</th><th>Dettaglio</th><th>IP</th></tr></thead>
          <tbody>
            {dati.items.map((r) => (
              <React.Fragment key={r.id}>
                <tr onClick={() => setAperta(aperta === r.id ? null : r.id)} style={{ cursor: "pointer" }}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {/* il pulsante rende apribile il dettaglio anche da tastiera; il clic sulla riga resta per il mouse */}
                    <button type="button" className="secondary btn-sm" aria-expanded={aperta === r.id} aria-label="Mostra o nascondi il dettaglio"
                            onClick={(e) => { e.stopPropagation(); setAperta(aperta === r.id ? null : r.id); }}>{aperta === r.id ? "▾" : "▸"}</button>{" "}
                    {new Date(r.created_at).toLocaleString("it-IT")}
                  </td>
                  <td>{r.user_email || <span className="text-muted">anonimo</span>}</td>
                  <td><span className={`badge ${badgeAzione(r.action)}`}>{r.action}</span></td>
                  <td>
                    {r.entity_name || "-"}
                    {r.entity_type && <><br /><span className="text-muted" style={{ fontSize: 12 }}>{r.entity_type}</span></>}
                  </td>
                  <td style={{ maxWidth: 320 }}>{r.detail || "-"}</td>
                  <td>{r.ip_address || "-"}</td>
                </tr>
                {aperta === r.id && (
                  <tr>
                    <td colSpan={6} style={{ background: "var(--bg3)", fontSize: 12 }}>
                      <div><strong>ID evento:</strong> {r.id}</div>
                      <div><strong>ID utente:</strong> {r.user_id || "-"}</div>
                      <div><strong>ID entità:</strong> {r.entity_id || "-"}</div>
                      <div><strong>Dettaglio completo:</strong> {r.detail || "-"}</div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {dati.items.length === 0 && <tr><td colSpan={6} className="empty-state">Nessun evento per i filtri selezionati.</td></tr>}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 12 }}>
        <button type="button" className="secondary btn-sm" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>← Precedente</button>
        <span className="text-muted" style={{ fontSize: 13 }}>Pagina {pagina} di {pagineTotali} — {dati.totale} eventi</span>
        <button type="button" className="secondary btn-sm" disabled={pagina >= pagineTotali} onClick={() => setPagina(pagina + 1)}>Successiva →</button>
      </div>
    </div>
  );
}
