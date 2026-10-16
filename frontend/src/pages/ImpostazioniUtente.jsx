import React, { useState, useEffect } from "react";
import api, { downloadFile, apriFile, erroreDi } from "../api";
import { REQUISITI_PASSWORD } from "../passwordPolicy";
import { pushSupportato, statoSottoscrizione, attivaPush, disattivaPush } from "../push";

const SCHEDE = [
  { id: "account", label: "Account" },
  { id: "password", label: "Password" },
  { id: "notifiche", label: "Notifiche" },
  { id: "calendario", label: "Calendario" },
  { id: "privacy", label: "Privacy" },
];

function SchedaPrivacy() {
  const [info, setInfo] = useState(undefined);
  const [esportando, setEsportando] = useState(false);
  const [errore, setErrore] = useState(null);

  useEffect(() => {
    api.get("/privacy/informativa").then((r) => setInfo(r.data))
      .catch((e) => { setInfo(null); setErrore(erroreDi(e, "Impossibile caricare l'informativa")); });
  }, []);

  async function scarica() {
    setEsportando(true);
    setErrore(null);
    try { await downloadFile("/privacy/export", "i-miei-dati.json"); }
    catch { setErrore("Impossibile scaricare i tuoi dati: riprova"); }
    finally { setEsportando(false); }
  }

  return (
    <>
      <div className="card">
        <h3>Informativa sul trattamento dei dati</h3>
        {info === undefined && <p className="text-muted">Caricamento...</p>}
        {info && !info.presente && <p className="text-muted">L'azienda non ha ancora pubblicato un'informativa.</p>}
        {info && info.testo && <div style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.55 }}>{info.testo}</div>}
        {info && info.pdf_url && <p><button type="button" className="secondary btn-sm" onClick={() => apriFile(info.pdf_url).catch(() => setErrore("Impossibile aprire il PDF"))}>Apri l'informativa in PDF</button></p>}
        {errore && <div className="error-msg">{errore}</div>}
        {info && info.presente && info.aggiornata_at && (
          <p className="text-muted" style={{ fontSize: 12 }}>Aggiornata il {new Date(info.aggiornata_at).toLocaleDateString("it-IT")}</p>
        )}
        {info && (info.titolare || info.contatto) && (
          <p className="text-muted" style={{ fontSize: 13 }}>
            Questa piattaforma è uno strumento aziendale per la gestione della formazione.
            Per esercitare i tuoi diritti{info.titolare ? <> contatta {info.titolare}</> : ""}{info.contatto ? <> ({info.contatto})</> : ""}.
          </p>
        )}
      </div>

      <div className="card">
        <h3>I tuoi dati</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Scarica una copia dei dati personali che la piattaforma conserva su di te: profilo, iscrizioni e esiti, tentativi di test, attestati, notifiche e attività registrata.
          Il gradimento dei corsi non è incluso perché è anonimo.
        </p>
        <button type="button" onClick={scarica} disabled={esportando}>{esportando ? "..." : "Scarica i miei dati"}</button>
      </div>
    </>
  );
}

export default function ImpostazioniUtente() {
  const [scheda, setScheda] = useState(() => {
    const dallaUrl = window.location.hash.replace("#", "");
    return SCHEDE.some((x) => x.id === dallaUrl) ? dallaUrl : "account";
  });
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);
  const [pushAttivo, setPushAttivo] = useState(null); // null = non ancora verificato
  const [pushErrore, setPushErrore] = useState(null);
  const [pushCaricamento, setPushCaricamento] = useState(false);
  const [calendarioAttivo, setCalendarioAttivo] = useState(null);   // null = non ancora caricato
  const [calendarioUrl, setCalendarioUrl] = useState(null);         // il link si vede solo subito dopo averlo creato
  const [calendarioCopiato, setCalendarioCopiato] = useState(false);
  const [calendarioErrore, setCalendarioErrore] = useState(null);

  useEffect(() => {
    if (!pushSupportato()) { setPushAttivo(false); return; }
    statoSottoscrizione().then((sub) => setPushAttivo(!!sub)).catch(() => setPushAttivo(false));
  }, []);

  const [urlPubblico, setUrlPubblico] = useState(null);
  useEffect(() => {
    api.get("/calendario/url").then((r) => setCalendarioAttivo(r.data.attivo)).catch((e) => setCalendarioErrore(erroreDi(e, "Impossibile caricare il link del calendario")));
    api.get("/about").then((r) => setUrlPubblico(r.data.url_pubblico)).catch(() => {});
  }, []);

  function urlAssoluta() {
    return `${urlPubblico || window.location.origin}${calendarioUrl}`;
  }

  async function copiaLinkCalendario() {
    try {
      await navigator.clipboard.writeText(urlAssoluta());
      setCalendarioCopiato(true);
      setTimeout(() => setCalendarioCopiato(false), 2000);
    } catch { /* clipboard non disponibile, l'utente copia a mano dal campo */ }
  }

  async function rigeneraLinkCalendario() {
    if (calendarioAttivo && !window.confirm("Il link attuale smetterà di funzionare nei calendari dove l'hai già aggiunto. Continuare?")) return;
    setCalendarioErrore(null);
    try {
      const r = await api.post("/calendario/url/rigenera");
      setCalendarioUrl(r.data.url);
      setCalendarioAttivo(true);
    } catch (err) { setCalendarioErrore(erroreDi(err, "Impossibile creare il link")); }
  }

  async function togglePush() {
    setPushErrore(null);
    setPushCaricamento(true);
    try {
      if (pushAttivo) { await disattivaPush(); setPushAttivo(false); }
      else { await attivaPush(); setPushAttivo(true); }
    } catch (err) {
      setPushErrore(err.message || "Errore nell'attivazione delle notifiche push");
    } finally {
      setPushCaricamento(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setErrore(null); setMsg(null);
    if (form.new_password !== form.confirm) { setErrore("Le password non coincidono"); return; }
    try {
      const r = await api.put("/auth/me/password", { current_password: form.current_password, new_password: form.new_password });
      localStorage.setItem("token", r.data.access_token);  // le altre sessioni sono state chiuse
      setMsg("Password aggiornata. Le altre sessioni aperte sono state chiuse.");
      setForm({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setErrore(erroreDi(err, "Errore durante l'aggiornamento"));
    }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Impostazioni utente</h2><p>Preferenze e sicurezza del tuo account.</p></div></div>
      <div className="tabs">
        {SCHEDE.map((x) => (
          <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>
        ))}
      </div>

      {scheda === "account" && (
        <div className="card">
          <h3>Il tuo account</h3>
          <div style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>Nome</div>
            <div style={{ fontWeight: 600 }}>{user?.full_name}</div>
          </div>
          <div style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>Email</div>
            <div>{user?.email}</div>
          </div>
          <div style={{ padding: "10px 0" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>Gruppi</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
              {(user?.groups || []).length === 0
                ? <span className="text-muted" style={{ fontSize: 13 }}>Nessun gruppo</span>
                : user.groups.map((g) => <span key={g.id} className="badge" style={{ background: g.color + "22", color: g.color }}>{g.name}</span>)}
            </div>
          </div>
        </div>
      )}

      {scheda === "password" && (
        <div className="card">
          <h3>Modifica password</h3>
          {user?.origine_credenziali && user.origine_credenziali !== "locale" ? (
            <p className="text-muted">Le tue credenziali sono gestite centralmente (dominio aziendale) — la password non si cambia da qui.</p>
          ) : (
            <form onSubmit={submit}>
              <div className="field"><label>Password attuale</label><input required type="password" value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })} /></div>
              <div className="field"><label>Nuova password</label><input required type="password" autoComplete="new-password" value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} /></div>
              <div className="field"><label>Conferma nuova password</label><input required type="password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} /></div>
              <p className="text-muted" style={{ fontSize: 12 }}>La nuova password deve avere {REQUISITI_PASSWORD}.</p>
              <button type="submit">Aggiorna password</button>
              {msg && <span style={{ marginLeft: 10, color: "var(--green-text)" }}>{msg}</span>}
              {errore && <div className="error-msg">{errore}</div>}
            </form>
          )}
        </div>
      )}

      {scheda === "notifiche" && (
      <div className="card">
        <h3>Notifiche push</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Ricevi sul dispositivo le stesse notifiche che vedi qui nella campanella (scadenze, solleciti, sessioni imminenti),
          anche ad app chiusa. Puoi attivarle su più dispositivi (pc, cellulare, tablet).
        </p>
        {pushAttivo === null && <p className="text-muted">Verifica in corso...</p>}
        {pushAttivo === false && !pushSupportato() && (
          <p className="text-muted">Il tuo browser non supporta le notifiche push.</p>
        )}
        {pushAttivo !== null && pushSupportato() && (
          <>
            <button type="button" onClick={togglePush} disabled={pushCaricamento} className={pushAttivo ? "secondary" : ""}>
              {pushCaricamento ? "..." : pushAttivo ? "Disattiva notifiche push" : "Attiva notifiche push su questo dispositivo"}
            </button>
            {pushAttivo && <span style={{ marginLeft: 10, color: "var(--green-text)" }}>Attive su questo dispositivo</span>}
          </>
        )}
        {pushErrore && <div className="error-msg">{pushErrore}</div>}
      </div>
      )}

      {scheda === "calendario" && (
      <div className="card">
        <h3>Il mio calendario</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Abbonati a questo link da Outlook o Google Calendar per vedere sempre le date dei tuoi corsi (come iscritto o come docente),
          aggiornate automaticamente — niente da riaggiungere ogni volta che cambia una data.
        </p>
        {calendarioAttivo === null ? (calendarioErrore ? null : <p className="text-muted">Caricamento...</p>) : (
          <>
            {calendarioUrl && (
              <>
                <div className="row" style={{ alignItems: "center" }}>
                  <input readOnly value={urlAssoluta()} onFocus={(e) => e.target.select()} />
                  <div style={{ flex: "0 0 auto" }}>
                    <button type="button" className="secondary btn-sm" onClick={copiaLinkCalendario}>{calendarioCopiato ? "Copiato!" : "Copia link"}</button>
                  </div>
                </div>
                <p className="text-muted" style={{ fontSize: 12, marginTop: 6 }}>
                  Per sicurezza questo link si vede <strong>solo adesso</strong>: copialo e aggiungilo al calendario. Se lo perdi, ne crei uno nuovo.
                  Outlook: Calendario → Aggiungi calendario → Da Internet. Google Calendar: Altri calendari → Da URL.
                </p>
              </>
            )}
            {!calendarioUrl && calendarioAttivo && <p className="text-muted" style={{ fontSize: 13 }}>Hai già un link attivo. Per sicurezza non si può rivedere: se ti serve di nuovo, creane uno nuovo (quello attuale smetterà di funzionare).</p>}
            {!calendarioUrl && (
              <button type="button" className="secondary" onClick={rigeneraLinkCalendario}>{calendarioAttivo ? "Crea un nuovo link" : "Crea il link"}</button>
            )}
          </>
        )}
        {calendarioErrore && <div className="error-msg">{calendarioErrore}</div>}
      </div>
      )}

      {scheda === "privacy" && <SchedaPrivacy />}
    </div>
  );
}
