import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import { aggiornaBranding } from "../branding";

export default function Piattaforma() {
  const [form, setForm] = useState({ nome_piattaforma: "", url_pubblico: "" });
  const [iconaUrl, setIconaUrl] = useState(null);
  const [integrazioni, setIntegrazioni] = useState(null);
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);

  function carica() {
    api.get("/azienda").then((r) => {
      setForm({ nome_piattaforma: r.data.nome_piattaforma || "", url_pubblico: r.data.url_pubblico || "" });
      setIconaUrl(r.data.icona_url);
    }).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le impostazioni")));
    api.get("/about").then((r) => setIntegrazioni(r.data.integrazioni)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare lo stato delle integrazioni")));
  }
  useEffect(carica, []);

  async function salva(e) {
    e.preventDefault();
    setMsg(null); setErrore(null);
    try {
      await api.put("/azienda/piattaforma", form);
      await aggiornaBranding();
      setMsg("Impostazioni salvate");
    } catch (err) {
      setErrore(erroreDi(err, "Errore nel salvataggio"));
    }
  }

  async function caricaIcona(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    setMsg(null); setErrore(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post("/azienda/icona", fd);
      setIconaUrl(r.data.icona_url);
      setMsg("Icona aggiornata. Chi ha già installato l'app la vedrà cambiare al prossimo aggiornamento del dispositivo.");
    } catch (err) {
      setErrore(erroreDi(err, "Errore nel caricamento dell'icona"));
    }
  }

  async function rimuoviIcona() {
    setErrore(null);
    try {
      const r = await api.delete("/azienda/icona");
      setIconaUrl(r.data.icona_url);
      setMsg("Icona rimossa: l'app usa il logo aziendale, se presente.");
    } catch (err) { setErrore(erroreDi(err, "Impossibile rimuovere l'icona")); }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Piattaforma</h2><p>Nome, indirizzo pubblico e icona dell'app.</p></div></div>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <form className="card" onSubmit={salva}>
          <h3>Identità</h3>
          <div className="field">
            <label htmlFor="nome-piattaforma">Nome della piattaforma</label>
            <input id="nome-piattaforma" maxLength={60} placeholder="E-Learning" value={form.nome_piattaforma}
                   onChange={(e) => setForm({ ...form, nome_piattaforma: e.target.value })} />
            <div className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>Appare nella barra laterale, nella pagina di accesso, nel titolo della scheda e come nome dell'app installata.</div>
          </div>
          <div className="field">
            <label htmlFor="url-pubblico">URL pubblico</label>
            <input id="url-pubblico" placeholder="https://formazione.azienda.it" value={form.url_pubblico}
                   onChange={(e) => setForm({ ...form, url_pubblico: e.target.value })} />
            <div className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>Indirizzo con cui gli utenti raggiungono la piattaforma. Serve per i link diretti nelle email.</div>
          </div>
          <button type="submit">Salva</button>
          {msg && <span style={{ marginLeft: 10, color: "var(--green-text)" }}>{msg}</span>}
          {errore && <div className="error-msg">{errore}</div>}
        </form>

        <div className="card">
          <h3>Icona dell'app</h3>
          <p className="text-muted" style={{ fontSize: 13 }}>
            Quadrata, almeno 192×192 (meglio 512×512), PNG/JPG/WEBP. Se non la carichi, l'app usa il logo aziendale; senza logo, il marchio predefinito.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <img src={iconaUrl || "/api/azienda/icona?size=192"} alt="Icona attuale" width={72} height={72} style={{ borderRadius: 14, border: "1px solid var(--border)" }} />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <label className="secondary btn-sm" style={{ cursor: "pointer", display: "inline-block", padding: ".4rem .8rem", border: "1px solid var(--border2)", borderRadius: 8 }}>
                Carica icona
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={caricaIcona} style={{ display: "none" }} />
              </label>
              {iconaUrl && <button type="button" className="secondary btn-sm" onClick={rimuoviIcona}>Rimuovi</button>}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Integrazioni</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>Si configurano solo dall'ambiente del server, non da qui: questa pagina ne mostra lo stato.</p>
        {integrazioni ? (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {Object.entries({ smtp: "Posta (SMTP)", sso: "Accesso aziendale", microsoft_graph: "Microsoft Teams", notifiche_push: "Notifiche push" }).map(([k, label]) => (
              <span key={k} className={`badge ${integrazioni[k] ? "green" : "gray"}`}>{label}: {integrazioni[k] ? "attiva" : "non configurata"}</span>
            ))}
          </div>
        ) : <p className="text-muted">Caricamento...</p>}
      </div>
    </div>
  );
}
