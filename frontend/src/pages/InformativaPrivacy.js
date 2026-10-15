import React, { useEffect, useRef, useState } from "react";
import api, { apriFile } from "../api";

export default function InformativaPrivacy() {
  const [info, setInfo] = useState(null);
  const [testo, setTesto] = useState("");
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);
  const fileRef = useRef(null);

  function applica(r) { setInfo(r.data); setTesto(r.data.testo || ""); }
  useEffect(() => { api.get("/privacy/informativa").then(applica); }, []);

  async function esegui(chiamata, ok) {
    setMsg(null); setErrore(null);
    try { applica(await chiamata()); setMsg(ok); }
    catch (err) { setErrore(err.response?.data?.detail || "Errore nel salvataggio"); }
  }

  const salvaTesto = (e) => { e.preventDefault(); esegui(() => api.put("/privacy/informativa", { testo }), "Testo salvato"); };
  const caricaPdf = (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    esegui(() => api.post("/privacy/informativa/pdf", fd), "PDF caricato");
  };
  const rimuoviPdf = () => {
    if (!window.confirm("Rimuovere il PDF dell'informativa?")) return;
    esegui(() => api.delete("/privacy/informativa/pdf"), "PDF rimosso");
  };

  if (!info) return <p className="text-muted">Caricamento...</p>;
  return (
    <div>
      <div className="page-header"><div><h2>Informativa privacy</h2><p>Gli utenti la consultano dal proprio profilo (Impostazioni, scheda Privacy). Non richiede accettazione.</p></div></div>
      {msg && <p style={{ color: "var(--green-text)" }}>{msg}</p>}
      {errore && <div className="error-msg">{errore}</div>}
      <div className="row" style={{ alignItems: "flex-start" }}>
        <form className="card" onSubmit={salvaTesto} style={{ flex: "2 1 420px" }}>
          <h3>Testo</h3>
          <div className="field">
            <label htmlFor="testo-informativa">Testo dell'informativa</label>
            <textarea id="testo-informativa" rows={16} value={testo} onChange={(e) => setTesto(e.target.value)}
              placeholder="Titolare, finalità e base giuridica del trattamento, categorie di dati, tempi di conservazione, diritti dell'interessato, contatti del DPO..." />
          </div>
          <button type="submit">Salva testo</button>
        </form>
        <div className="card" style={{ flex: "1 1 260px" }}>
          <h3>Documento PDF</h3>
          <p className="text-muted" style={{ fontSize: 13 }}>In alternativa o in aggiunta al testo. Gli utenti lo aprono da un link.</p>
          {info.pdf_url
            ? <p><button type="button" className="secondary btn-sm" onClick={() => apriFile(info.pdf_url).catch(() => setErrore("Impossibile aprire il PDF"))}>Apri il PDF attuale</button></p>
            : <p className="text-muted">Nessun PDF caricato.</p>}
          <input ref={fileRef} type="file" accept="application/pdf" onChange={caricaPdf} style={{ display: "none" }} />
          <button type="button" className="secondary" onClick={() => fileRef.current.click()}>{info.pdf_url ? "Sostituisci PDF" : "Carica PDF"}</button>{" "}
          {info.pdf_url && <button type="button" className="secondary" onClick={rimuoviPdf}>Rimuovi</button>}
          {info.aggiornata_at && <p className="text-muted" style={{ fontSize: 12, marginTop: 14 }}>Ultimo aggiornamento: {new Date(info.aggiornata_at).toLocaleString("it-IT")}</p>}
        </div>
      </div>
    </div>
  );
}
