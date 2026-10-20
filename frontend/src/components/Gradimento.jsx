import React, { useState } from "react";
import api, { erroreDi } from "../api";

// Cinque pulsanti: si scelgono con il mouse e da tastiera (Tab e Invio/Spazio), e lo schermo li legge come "N stelle su 5".
function Stelle({ value, onChange, etichetta }) {
  return (
    <div role="group" aria-label={etichetta} style={{ display: "flex", gap: 6 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" onClick={() => onChange(n)} aria-pressed={n === value} aria-label={`${n} ${n === 1 ? "stella" : "stelle"} su 5`}
                style={{ cursor: "pointer", fontSize: 22, opacity: n <= value ? 1 : 0.3, background: "none", border: 0, padding: 0, color: "inherit", lineHeight: 1 }}>★</button>
      ))}
    </div>
  );
}

export default function Gradimento({ iscrizioneId, docenti = [] }) {
  const [votoCorso, setVotoCorso] = useState(0);
  const [commentoCorso, setCommentoCorso] = useState("");
  const [votiDocenti, setVotiDocenti] = useState({});
  const [inviato, setInviato] = useState(false);
  const [errore, setErrore] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try {
      await api.post(`/iscrizioni/${iscrizioneId}/gradimento`, {
        voto_corso: votoCorso, commento_corso: commentoCorso, voti_docenti: votiDocenti,
      });
      setInviato(true);
    } catch (err) { setErrore(erroreDi(err, "Invio non riuscito")); }
  }

  if (inviato) return <div className="card"><p>Grazie per il tuo feedback! La valutazione è anonima.</p></div>;

  const mancaVotoDocente = docenti.some((d) => !votiDocenti[d.id]);

  return (
    <div className="card">
      <h3>Il tuo parere sul corso</h3>
      <p className="text-muted" style={{ fontSize: 12 }}>La tua valutazione è anonima: l'Ufficio Formazione vede solo medie e commenti, non chi li ha scritti.</p>
      <form onSubmit={submit}>
        <div className="field">
          <label>Il corso nel complesso</label>
          <Stelle value={votoCorso} onChange={setVotoCorso} etichetta="Voto del corso" />
        </div>
        <div className="field"><textarea placeholder="Commento sul corso (opzionale)" value={commentoCorso} onChange={(e) => setCommentoCorso(e.target.value)} /></div>
        {docenti.map((d) => (
          <div className="field" key={d.id}>
            <label>Docente: {d.nome}</label>
            <Stelle value={votiDocenti[d.id] || 0} onChange={(n) => setVotiDocenti((v) => ({ ...v, [d.id]: n }))} etichetta={`Voto del docente ${d.nome}`} />
          </div>
        ))}
        {errore && <div className="error-msg">{errore}</div>}
        <button type="submit" disabled={votoCorso === 0 || mancaVotoDocente}>Invia</button>
      </form>
    </div>
  );
}
