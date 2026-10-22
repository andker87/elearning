import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";

function formatBytes(n) {
  if (n == null) return "-";
  const unita = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < unita.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${unita[i]}`;
}

function formatData(iso) {
  return iso ? new Date(iso).toLocaleString("it-IT") : "-";
}

function Kpi({ valore, etichetta, classe }) {
  return (
    <div className="kpi-card" style={{ cursor: "default", transform: "none" }}>
      <div className={`kpi-value ${classe || ""}`}>{valore}</div>
      <div className="kpi-label">{etichetta}</div>
    </div>
  );
}

export default function StatoPiattaforma() {
  const [d, setD] = useState(null);
  const [errore, setErrore] = useState(null);
  const [caricamento, setCaricamento] = useState(false);

  function carica() {
    setCaricamento(true);
    setErrore(null);
    api.get("/admin/salute")
      .then((r) => setD(r.data))
      .catch((err) => setErrore(erroreDi(err, "Errore nel caricamento")))
      .finally(() => setCaricamento(false));
  }
  useEffect(carica, []);

  if (errore) return <div><div className="error-msg">{errore}</div><button type="button" className="secondary btn-sm" style={{ marginTop: 8 }} onClick={carica} disabled={caricamento}>Riprova</button></div>;
  if (!d) return <p className="text-muted">Caricamento...</p>;

  const sch = d.scheduler;
  const ultima = sch.ultima_esecuzione;
  const percDisco = d.storage.disco_totale ? Math.round((d.storage.disco_usato / d.storage.disco_totale) * 100) : 0;
  const coloreDisco = percDisco >= 90 ? "bad" : percDisco >= 75 ? "warn" : "ok";

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Stato della piattaforma</h2>
          <p>Salute tecnica: accessi, job pianificati, posta, spazio. Aggiornato alle {formatData(d.generato_at)}.</p>
        </div>
        <button type="button" className="secondary" onClick={carica} disabled={caricamento}>{caricamento ? "..." : "Aggiorna"}</button>
      </div>

      <div className="kpi-grid">
        <Kpi valore={d.accessi.utenti_distinti_24h} etichetta="Utenti con login nelle ultime 24h" />
        <Kpi valore={d.accessi.utenti_distinti_7g} etichetta="Utenti con login negli ultimi 7 giorni" />
        <Kpi valore={d.accessi.login_falliti_24h} etichetta="Login falliti nelle ultime 24h" classe={d.accessi.login_falliti_24h >= 10 ? "bad" : ""} />
        <Kpi valore={d.smtp.configurato ? "Configurato" : "Non configurato"} etichetta="Posta (SMTP)" classe={d.smtp.configurato ? "ok" : "warn"} />
        <Kpi valore={d.sso.configurato ? "Attivo" : "Non configurato"}
             etichetta={d.sso.configurato ? `Accesso aziendale (SSO) · ${d.sso.utenti_collegati} utenti collegati${d.sso.provisioning ? " · creazione automatica" : ""}` : "Accesso aziendale (SSO)"}
             classe={d.sso.configurato ? "ok" : ""} />
        <Kpi valore={d.entra.configurato ? (d.entra.automatico ? "Automatica" : "Manuale") : "Non configurata"}
             etichetta={d.entra.ultima_esecuzione ? `Sincronizzazione utenti Entra · ultimo giro ${formatData(d.entra.ultima_esecuzione.started_at)}: ${d.entra.ultima_esecuzione.esito === "ok" ? d.entra.ultima_esecuzione.dettaglio : "errore"}` : "Sincronizzazione utenti Entra"}
             classe={d.entra.ultima_esecuzione?.esito === "errore" ? "bad" : d.entra.configurato ? "ok" : ""} />
        <Kpi valore={`${percDisco}%`} etichetta={`Disco occupato (${formatBytes(d.storage.disco_libero)} liberi)`} classe={coloreDisco} />
        <Kpi valore={d.storage.video_in_errore} etichetta="Video in errore di elaborazione" classe={d.storage.video_in_errore ? "bad" : ""} />
      </div>

      <div className="card">
        <h3>Job pianificati</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Generazione notifiche giornaliere (scadenze, solleciti, sessioni imminenti, promemoria).
          Scheduler {sch.attivo ? <span className="badge green">attivo</span> : <span className="badge red">fermo</span>}
          {" "}— prossima esecuzione: <strong>{formatData(sch.prossima_esecuzione)}</strong>
        </p>
        {!ultima && (
          <p className="text-muted">Nessuna esecuzione registrata ancora: il primo giro parte 24 ore dopo l'avvio del backend (lo storico si riempie da qui in avanti).</p>
        )}
        {ultima && ultima.esito === "errore" && (
          <div className="error-msg">Ultima esecuzione fallita ({formatData(ultima.started_at)}).</div>
        )}
        {sch.storico.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Avvio</th><th>Esito</th><th>Durata</th><th>Errore</th></tr></thead>
              <tbody>
                {sch.storico.map((r, i) => (
                  <tr key={i}>
                    <td>{formatData(r.started_at)}</td>
                    <td><span className={`badge ${r.esito === "ok" ? "green" : "red"}`}>{r.esito}</span></td>
                    <td>{r.durata_ms != null ? `${r.durata_ms} ms` : "-"}</td>
                    <td style={{ maxWidth: 420 }}>{r.errore ? <pre style={{ margin: 0, fontSize: 11, whiteSpace: "pre-wrap" }}>{r.errore}</pre> : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {d.cifratura && (
        <div className="card">
          <h3>Cifratura dei dati</h3>
          {d.cifratura.dati_personali && (d.cifratura.dati_personali.cifrato > 0 || d.cifratura.dati_personali.chiaro > 0) && (
            <p style={{ margin: "0 0 8px", fontSize: 13 }}>
              Dati personali nel database (nomi, email, IP, telefoni; del registro attività le ultime 10000 righe): {d.cifratura.dati_personali.cifrato} valori cifrati
              {d.cifratura.dati_personali.chiaro > 0 && <>, <strong>{d.cifratura.dati_personali.chiaro} ancora in chiaro</strong>{d.cifratura.chiave_presente ? " (esegui «cifra» dallo strumento da riga di comando)" : ""}</>}.
            </p>
          )}
          {d.cifratura.chiave_presente ? (
            <p style={{ margin: 0, fontSize: 13 }}>
              <span className="badge green">attiva</span>{" "}
              {d.cifratura.file.cifrato} file cifrati
              {d.cifratura.file.chiaro > 0 && <>, <strong>{d.cifratura.file.chiaro} ancora in chiaro</strong> (esegui «cifra» dallo strumento da riga di comando)</>}
              {d.cifratura.file.altra_chiave > 0 && <>, {d.cifratura.file.altra_chiave} con una chiave precedente (esegui «ruota»)</>}.
            </p>
          ) : (
            <p style={{ margin: 0, fontSize: 13 }}>
              <span className="badge red">non attiva</span>{" "}
              I file caricati e i segreti non sono cifrati sul disco. Imposta <code>CHIAVE_CIFRATURA</code> (vedi docs/sicurezza.md).
              {d.cifratura.file.chiaro > 0 && <> File in chiaro: {d.cifratura.file.chiaro}.</>}
            </p>
          )}
        </div>
      )}

      <div className="card">
        <h3>Spazio e dati</h3>
        <div style={{ background: "var(--bg3)", borderRadius: 6, height: 10, overflow: "hidden", margin: "6px 0 12px" }}>
          <div style={{ width: `${percDisco}%`, height: "100%", background: coloreDisco === "bad" ? "var(--red-text)" : coloreDisco === "warn" ? "var(--accent-dark)" : "var(--primary)" }} />
        </div>
        <div className="row">
          <div><div className="text-muted" style={{ fontSize: 12 }}>Disco (usato / totale)</div>{formatBytes(d.storage.disco_usato)} / {formatBytes(d.storage.disco_totale)}</div>
          <div><div className="text-muted" style={{ fontSize: 12 }}>Video della piattaforma</div>{formatBytes(d.storage.video_bytes)}</div>
          <div><div className="text-muted" style={{ fontSize: 12 }}>Upload (certificati, attestati, template)</div>{formatBytes(d.storage.upload_bytes)}</div>
          <div><div className="text-muted" style={{ fontSize: 12 }}>Database</div>{formatBytes(d.database.dimensione_bytes)}</div>
          <div><div className="text-muted" style={{ fontSize: 12 }}>Righe audit log</div>{d.database.righe_audit}</div>
        </div>
        {Object.keys(d.storage.video_per_stato).length > 0 && (
          <p style={{ marginTop: 12, fontSize: 13 }}>
            Video per stato:{" "}
            {Object.entries(d.storage.video_per_stato).map(([k, v]) => (
              <span key={k} className={`badge ${k === "errore" ? "red" : k === "pronto" ? "green" : "gray"}`} style={{ marginRight: 6 }}>{k}: {v}</span>
            ))}
          </p>
        )}
        <p className="text-muted" style={{ fontSize: 12 }}>
          Il disco indicato è quello del volume che ospita i video: se si riempie, gli upload e la transcodifica falliscono.
        </p>
      </div>
    </div>
  );
}
