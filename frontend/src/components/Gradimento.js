import React, { useState } from "react";
import api from "../api";

export default function Gradimento({ iscrizioneId }) {
  const [voto, setVoto] = useState(0);
  const [commento, setCommento] = useState("");
  const [inviato, setInviato] = useState(false);

  async function submit(e) {
    e.preventDefault();
    await api.post(`/iscrizioni/${iscrizioneId}/gradimento`, { voto, commento });
    setInviato(true);
  }

  if (inviato) return <div className="card"><p>Grazie per il tuo feedback!</p></div>;

  return (
    <div className="card">
      <h3>Com'è andata?</h3>
      <form onSubmit={submit}>
        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <span key={n} onClick={() => setVoto(n)} style={{ cursor: "pointer", fontSize: 24, opacity: n <= voto ? 1 : 0.3 }}>★</span>
          ))}
        </div>
        <div className="field"><textarea placeholder="Commento (opzionale)" value={commento} onChange={(e) => setCommento(e.target.value)} /></div>
        <button type="submit" disabled={voto === 0}>Invia</button>
      </form>
    </div>
  );
}
