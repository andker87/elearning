import React, { useEffect, useState, useRef } from "react";
import api, { erroreDi } from "../api";

export default function Azienda() {
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [testMsg, setTestMsg] = useState(null);
  const [logoMsg, setLogoMsg] = useState(null);
  const [errore, setErrore] = useState(null);
  const fileRef = useRef(null);

  function ricarica() { api.get("/azienda").then((r) => setForm(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i dati dell'azienda"))); }
  useEffect(ricarica, []);

  async function submit(e) {
    e.preventDefault();
    const { ragione_sociale, partita_iva, codice_fiscale, indirizzo, cap, citta, provincia, nazione, email, pec } = form;
    setErrore(null);
    try {
      await api.put("/azienda", { ragione_sociale, partita_iva, codice_fiscale, indirizzo, cap, citta, provincia, nazione, email, pec });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) { setErrore(erroreDi(err, "Errore nel salvataggio")); }
  }

  async function provaSmtp() {
    setTestMsg(null);
    try {
      await api.post("/azienda/smtp/test", { destinatario: testEmail });
      setTestMsg("Email inviata correttamente.");
    } catch (e) {
      setTestMsg(erroreDi(e, "Errore nell'invio"));
    }
  }

  async function caricaLogo(e) {
    const file = e.target.files[0];
    if (!file) return;
    setLogoMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/azienda/logo", fd, { headers: { "Content-Type": "multipart/form-data" } });
      ricarica();
    } catch (err) {
      setLogoMsg(erroreDi(err, "Errore nel caricamento"));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function rimuoviLogo() {
    setLogoMsg(null);
    try {
      await api.delete("/azienda/logo");
      ricarica();
    } catch (err) { setLogoMsg(erroreDi(err, "Impossibile rimuovere il logo")); }
  }

  if (!form) return errore ? <div className="error-msg">{errore}</div> : <div>Caricamento...</div>;

  return (
    <div>
      <h2>Azienda</h2>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="card">
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Ragione sociale</label><input value={form.ragione_sociale || ""} onChange={(e) => setForm({ ...form, ragione_sociale: e.target.value })} /></div>
            <div className="field"><label>P.IVA</label><input value={form.partita_iva || ""} onChange={(e) => setForm({ ...form, partita_iva: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Indirizzo</label><input value={form.indirizzo || ""} onChange={(e) => setForm({ ...form, indirizzo: e.target.value })} /></div>
            <div className="field"><label>Città</label><input value={form.citta || ""} onChange={(e) => setForm({ ...form, citta: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Email</label><input value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div className="field"><label>PEC</label><input value={form.pec || ""} onChange={(e) => setForm({ ...form, pec: e.target.value })} /></div>
          </div>
          <button type="submit">Salva</button>
          {saved && <span style={{ marginLeft: 10, color: "#1a7a3e" }}>Salvato</span>}
        </form>
      </div>

      <div className="card">
        <h3>Logo azienda</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Usato sugli attestati e sulle esportazioni PDF. Formati accettati: PNG, JPG, WEBP.
        </p>
        <div className="row" style={{ alignItems: "center" }}>
          {form.logo_url && (
            <div className="field" style={{ flex: "none" }}>
              <img src={form.logo_url} alt="Logo azienda" style={{ maxHeight: 80, maxWidth: 220, objectFit: "contain", border: "1px solid var(--border)", borderRadius: 6, padding: 4 }} />
            </div>
          )}
          <div className="field" style={{ flex: "none" }}>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={caricaLogo} />
          </div>
          {form.logo_url && (
            <div className="field" style={{ flex: "none", alignSelf: "flex-end" }}>
              <button type="button" className="secondary" onClick={rimuoviLogo}>Rimuovi logo</button>
            </div>
          )}
        </div>
        {logoMsg && <p style={{ color: "#b00" }}>{logoMsg}</p>}
      </div>

      <div className="card">
        <h3>Invio email (SMTP)</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Lo SMTP si configura a livello di ambiente/container da chi amministra il server (variabili <code>SMTP_*</code>), non da questa pagina —
          qui puoi solo verificarne lo stato. Lo stesso vale per una futura autenticazione aziendale (SSO).
        </p>
        <div className="row">
          <div className="field">
            <label>Stato</label>
            <div>
              <span className={`badge ${form.smtp.configurato ? "green" : "gray"}`}>
                {form.smtp.configurato ? "Configurato" : "Non configurato"}
              </span>
            </div>
          </div>
          {form.smtp.configurato && (
            <>
              <div className="field"><label>Host</label><div>{form.smtp.host}{form.smtp.porta ? `:${form.smtp.porta}` : ""}</div></div>
              <div className="field"><label>Mittente</label><div>{form.smtp.mittente}</div></div>
              <div className="field"><label>Sicurezza</label><div>{form.smtp.tls ? "STARTTLS" : "SSL diretto"}</div></div>
            </>
          )}
        </div>
        {form.smtp.configurato && (
          <div className="row" style={{ marginTop: 12 }}>
            <div className="field"><label>Invia email di prova a</label><input value={testEmail} onChange={(e) => setTestEmail(e.target.value)} /></div>
            <div className="field" style={{ alignSelf: "flex-end" }}><button type="button" className="secondary" onClick={provaSmtp}>Invia prova</button></div>
          </div>
        )}
        {testMsg && <p>{testMsg}</p>}
      </div>
    </div>
  );
}
