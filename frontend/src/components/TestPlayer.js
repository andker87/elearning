import React, { useEffect, useState } from "react";
import api from "../api";

export default function TestPlayer({ testId, iscrizioneId }) {
  const [test, setTest] = useState(null);
  const [risposte, setRisposte] = useState({});
  const [esito, setEsito] = useState(null);
  const [errore, setErrore] = useState(null);

  function load() { api.get(`/test/${testId}`).then((r) => setTest(r.data)); }
  useEffect(load, [testId]);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try {
      const r = await api.post(`/test/${testId}/tenta`, { iscrizione_id: iscrizioneId, risposte });
      setEsito(r.data);
    } catch (err) {
      setErrore(err.response?.data?.detail || "Errore durante l'invio");
    }
  }

  if (!test) return null;

  return (
    <div className="card">
      <h3>{test.titolo}</h3>
      {esito ? (
        <div>
          <p><strong>Punteggio:</strong> {esito.punteggio_pct}%</p>
          <span className={`badge ${esito.superato ? "green" : "red"}`}>{esito.superato ? "Superato" : "Non superato"}</span>
          {esito.messaggio && <p style={{ marginTop: 8 }}>{esito.messaggio}</p>}
          <div style={{ marginTop: 10 }}><button className="secondary" onClick={() => { setEsito(null); setRisposte({}); }}>Ritenta</button></div>
        </div>
      ) : (
        <form onSubmit={submit}>
          {test.domande.map((d, i) => (
            <div key={d.id} className="field">
              <label>{i + 1}. {d.testo}</label>
              {d.opzioni.map((o) => (
                <label key={o.id} style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 400, marginBottom: 4 }}>
                  <input type="radio" style={{ width: "auto" }} name={d.id} checked={risposte[d.id] === o.id}
                         onChange={() => setRisposte({ ...risposte, [d.id]: o.id })} />
                  {o.testo}
                </label>
              ))}
            </div>
          ))}
          <button type="submit">Invia risposte</button>
          {errore && <div className="error-msg">{errore}</div>}
        </form>
      )}
    </div>
  );
}
