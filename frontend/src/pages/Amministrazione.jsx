import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { erroreDi } from "../api";
import Icona from "../components/Icona";

const LAVORI = { sync_entra: "Sincronizzazione utenti", notifiche_giornaliere: "Notifiche e promemoria", percorsi_iscrizioni: "Iscrizioni dei percorsi", rinnovi_automatici: "Rinnovi automatici" };
const quandoFu = (d) => (d ? new Date(d).toLocaleString("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");
const gb = (b) => (b == null ? "—" : `${(b / 1e9).toFixed(1).replace(".", ",")} GB`);

// Il punto di partenza dello spazio Amministrazione: persone, accessi e salute della piattaforma in una pagina.
export default function Amministrazione() {
  const [d, setD] = useState(null);
  const [errore, setErrore] = useState(null);
  useEffect(() => { api.get("/amministrazione/riepilogo").then((r) => setD(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare il riepilogo"))); }, []);
  if (errore) return <div className="error-msg" role="alert">{errore}</div>;
  if (!d) return <p className="text-muted">Caricamento...</p>;
  const st = d.storage || {};
  return (
    <div>
      <div className="page-header"><div><h2>Amministrazione</h2><p>Persone, accessi e salute della piattaforma.</p></div></div>
      <div className="kpi-grid" style={{ marginBottom: "1rem" }}>
        <div className="kpi-card statico"><div className="kpi-value">{d.persone.attive}</div><div className="kpi-label">persone attive ({d.persone.interne} interne, {d.persone.esterne} esterne)</div></div>
        <div className="kpi-card statico"><div className="kpi-value">{d.persone.senza_ufficio}</div><div className="kpi-label">interne senza ufficio · <Link to="/utenti">vedi</Link></div></div>
        <div className="kpi-card statico"><div className="kpi-value">{d.richieste_password}</div><div className="kpi-label">richieste di nuova password · <Link to="/reset-password-richieste">apri</Link></div></div>
        <div className="kpi-card statico"><div className="kpi-value">{d.accessi.utenti_distinti_7g}</div><div className="kpi-label">persone entrate negli ultimi 7 giorni{d.accessi.login_falliti_24h ? ` · ${d.accessi.login_falliti_24h} accessi falliti in 24 ore` : ""}</div></div>
      </div>
      <div className="card lista-azioni">
        <h3>Lavori automatici</h3>
        {Object.entries(LAVORI).map(([k, nome]) => {
          const l = d.lavori[k];
          return (
            <div className="riga-azione" key={k}>
              <Icona nome={!l ? "info" : l.esito === "ok" ? "award" : "pulse"} />
              <div><strong>{nome}</strong><div className="text-muted piccolo">{l ? `ultimo giro ${quandoFu(l.started_at)}` : "non ancora eseguito"}{l?.errore ? ` · ${l.errore}` : ""}</div></div>
              <div className="azioni">{l ? <span className={`badge ${l.esito === "ok" ? "green" : "red"}`}>{l.esito === "ok" ? "riuscito" : "errore"}</span> : <span className="badge gray">—</span>}</div>
            </div>
          );
        })}
      </div>
      <div className="card lista-azioni">
        <h3>Servizi</h3>
        <div className="riga-azione"><Icona nome="bell" /><div><strong>Posta in uscita</strong><div className="text-muted piccolo">{d.smtp.configurato ? "configurata: le email partono" : "non configurata: niente email (le notifiche restano nella piattaforma)"}</div></div><div className="azioni"><span className={`badge ${d.smtp.configurato ? "green" : "gray"}`}>{d.smtp.configurato ? "attiva" : "spenta"}</span></div></div>
        <div className="riga-azione"><Icona nome="key" /><div><strong>Accesso con le credenziali aziendali</strong><div className="text-muted piccolo">{d.sso.configurato ? `attivo · ${d.sso.utenti_collegati} persone collegate` : "non configurato"}</div></div><div className="azioni"><span className={`badge ${d.sso.configurato ? "green" : "gray"}`}>{d.sso.configurato ? "attivo" : "spento"}</span></div></div>
        <div className="riga-azione"><Icona nome="play" /><div><strong>Spazio per video e allegati</strong><div className="text-muted piccolo">video {gb(st.video_bytes)} · allegati {gb(st.upload_bytes)} · liberi {gb(st.disco_libero)}{st.video_in_errore ? ` · ${st.video_in_errore} video in errore` : ""}</div></div><div className="azioni"><span className={`badge ${st.video_in_errore ? "yellow" : "green"}`}>{st.video_in_errore ? "da guardare" : "ok"}</span></div></div>
      </div>
      <p className="text-muted" style={{ fontSize: ".85rem" }}>Il dettaglio è in <Link to="/stato-piattaforma">Stato della piattaforma</Link>; chi ha fatto cosa in <Link to="/audit-log">Registro attività</Link>.</p>
    </div>
  );
}
