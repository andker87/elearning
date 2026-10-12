import React, { useState } from "react";
import api from "../api";

function Stelle({ value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 6 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} onClick={() => onChange(n)} style={{ cursor: "pointer", fontSize: 22, opacity: n <= value ? 1 : 0.3 }}>★</span>
      ))}
    </div>
  );
}

export default function Gradimento({ iscrizioneId, docenti = [] }) {
  const [votoCorso, setVotoCorso] = useState(0);
  const [commentoCorso, setCommentoCorso] = useState("");
  const [votiDocenti, setVotiDocenti] = useState({});
  const [inviato, setInviato] = useState(false);

  async function submit(e) {
    e.preventDefault();
    await api.post(`/iscrizioni/${iscrizioneId}/gradimento`, {
      voto_corso: votoCorso, commento_corso: commentoCorso, voti_docenti: votiDocenti,
    });
    setInviato(true);
  }

  if (inviato) return <div className="card"><p>Grazie per il tuo feedback! La valutazione è anonima.</p></div>;

  const mancaVotoDocente = docenti.some((d) => !votiDocenti[d.id]);

  return (
    <div className="card">
      <h3>Com'è andata?</h3>
      <p className="text-muted" style={{ fontSize: 12 }}>La tua valutazione è anonima: l'Ufficio Formazione vede solo medie e commenti, non chi li ha scritti.</p>
      <form onSubmit={submit}>
        <div className="field">
          <label>Il corso nel complesso</label>
          <Stelle value={votoCorso} onChange={setVotoCorso} />
        </div>
        <div className="field"><textarea placeholder="Commento sul corso (opzionale)" value={commentoCorso} onChange={(e) => setCommentoCorso(e.target.value)} /></div>
        {docenti.map((d) => (
          <div className="field" key={d.id}>
            <label>Docente: {d.nome}</label>
            <Stelle value={votiDocenti[d.id] || 0} onChange={(n) => setVotiDocenti({ ...votiDocenti, [d.id]: n })} />
          </div>
        ))}
        <button type="submit" disabled={votoCorso === 0 || mancaVotoDocente}>Invia</button>
      </form>
    </div>
  );
}
