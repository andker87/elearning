import React, { useRef, useState } from "react";
import api, { erroreDi } from "../api";
import Copertina from "./Copertina";
import { conferma } from "./conferma";

// Nella scheda di un corso: carica, sostituisce o toglie la copertina. Agisce subito (non aspetta «Salva» del modulo del corso).
export default function CampoCopertina({ corso, onCambia }) {
  const campo = useRef(null);
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);

  async function carica(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setErrore(null); setInvio(true);
    const fd = new FormData(); fd.append("file", file);
    try { await api.post(`/corsi/${corso.id}/copertina`, fd); onCambia && (await onCambia()); }
    catch (err) { setErrore(erroreDi(err, "Caricamento non riuscito")); }
    setInvio(false);
    if (campo.current) campo.current.value = "";
  }
  async function togli() {
    if (!(await conferma("Il corso torna a mostrare il riquadro colorato generato.", { titolo: "Togliere la copertina?", etichetta: "Togli la copertina", pericolo: true }))) return;
    setErrore(null);
    try { await api.delete(`/corsi/${corso.id}/copertina`); onCambia && (await onCambia()); }
    catch (err) { setErrore(erroreDi(err, "Impossibile togliere la copertina")); }
  }

  return (
    <div className="campo-copertina">
      <Copertina url={corso.copertina_url} titolo={corso.titolo} className="copertina-anteprima" />
      <div style={{ display: "grid", gap: ".45rem", alignContent: "start" }}>
        <strong>Copertina del corso</strong>
        <span className="text-muted piccolo">
          {corso.copertina_url ? "È quella che si vede nel Catalogo, nella Home e nella pagina del corso." : "Senza immagine, il corso mostra un riquadro colorato con l'icona del suo tipo."}
          {" "}Formato 16:9 (meglio 1280×720), PNG, JPG o WEBP, al massimo 5 MB. Se l'immagine ha un'altra proporzione viene ritagliata al centro.
        </span>
        <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", alignItems: "center" }}>
          <label className="btn-file">
            <input ref={campo} type="file" accept="image/png,image/jpeg,image/webp" onChange={carica} disabled={invio} style={{ display: "none" }} />
            {invio ? "Carico..." : corso.copertina_url ? "Sostituisci l'immagine" : "Carica un'immagine"}
          </label>
          {corso.copertina_url && <button type="button" className="danger btn-sm" onClick={togli}>Togli</button>}
        </div>
        {errore && <div className="error-msg" role="alert" style={{ margin: 0 }}>{errore}</div>}
      </div>
    </div>
  );
}
