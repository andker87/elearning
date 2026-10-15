import React, { useEffect, useState } from "react";
import api from "../api";

function durata(secondi) {
  const g = Math.floor(secondi / 86400);
  const o = Math.floor((secondi % 86400) / 3600);
  const m = Math.floor((secondi % 3600) / 60);
  return g ? `${g} g ${o} h` : o ? `${o} h ${m} min` : `${m} min`;
}

export default function Informazioni() {
  const [d, setD] = useState(null);
  const [errore, setErrore] = useState(null);

  useEffect(() => {
    api.get("/about").then((r) => setD(r.data)).catch(() => setErrore("Impossibile caricare le informazioni"));
  }, []);

  if (errore) return <div className="error-msg">{errore}</div>;
  if (!d) return <p className="text-muted">Caricamento...</p>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Informazioni</h2>
          <p>{d.nome_piattaforma}{d.nome_azienda ? ` · ${d.nome_azienda}` : ""} · versione <strong>{d.versione}</strong></p>
        </div>
      </div>

      {d.ambiente && (
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="card">
            <h3>Ambiente</h3>
            <table><tbody>
              <tr><td>Python</td><td>{d.ambiente.python}</td></tr>
              <tr><td>Sistema</td><td>{d.ambiente.sistema}</td></tr>
              <tr><td>Database</td><td>{d.ambiente.database}</td></tr>
              <tr><td>Attivo da</td><td>{durata(d.ambiente.attivo_da_secondi)}</td></tr>
              <tr><td>URL pubblico</td><td>{d.url_pubblico || <span className="text-muted">non impostato</span>}</td></tr>
            </tbody></table>
            <h3 style={{ marginTop: 16 }}>Integrazioni</h3>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {Object.entries({ smtp: "Posta (SMTP)", sso: "Accesso aziendale", microsoft_graph: "Microsoft Teams", notifiche_push: "Notifiche push" }).map(([k, label]) => (
                <span key={k} className={`badge ${d.integrazioni[k] ? "green" : "gray"}`}>{label}: {d.integrazioni[k] ? "attiva" : "non configurata"}</span>
              ))}
            </div>
          </div>
          <div className="card">
            <h3>Componenti</h3>
            <table><tbody>
              {Object.entries(d.dipendenze).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}
            </tbody></table>
          </div>
        </div>
      )}

      <div className="card">
        <h3>Novità</h3>
        {d.changelog.map((c) => (
          <div key={c.version} style={{ padding: "12px 0", borderTop: "1px solid var(--border)" }}>
            <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
              <span className="badge accent">{c.version}</span>
              <strong>{c.label}</strong>
              <span className="text-muted" style={{ fontSize: 12 }}>{c.date}</span>
            </div>
            <ul style={{ margin: "8px 0 0", paddingLeft: 20, fontSize: 13, color: "var(--text2)" }}>
              {c.changes.map((t, i) => <li key={i} style={{ marginBottom: 4 }}>{t}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
