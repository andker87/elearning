import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";

export default function RichiesteResetPassword() {
  const [dati, setDati] = useState({ richieste: [], smtp_attivo: false });
  const [generata, setGenerata] = useState(null);
  const [errore, setErrore] = useState(null);

  function carica() { api.get("/auth/password-reset-richieste").then((r) => setDati(r.data)); }
  useEffect(carica, []);

  async function genera(r) {
    if (!window.confirm(`Assegnare una password temporanea a ${r.utente?.nome}? Le sessioni aperte verranno chiuse.`)) return;
    setErrore(null);
    try { const res = await api.post(`/auth/password-reset-richieste/${r.id}/genera`); setGenerata(res.data); carica(); }
    catch (err) { setErrore(erroreDi(err, "Errore")); }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Reset password</h2>
        <p>Richieste di chi ha dimenticato la password. {dati.smtp_attivo ? "L'invio email è attivo: chi chiede il reset riceve un link e non compare qui." : "L'invio email non è attivo: le richieste arrivano qui e la password temporanea va comunicata a parte."}</p></div></div>
      {errore && <div className="error-msg">{errore}</div>}
      {generata && (
        <div className="card">
          <h3>Password temporanea per {generata.utente.nome}</h3>
          <p><code style={{ fontSize: 18 }}>{generata.password_temporanea}</code></p>
          <p className="text-muted" style={{ fontSize: 13 }}>Comunicala alla persona con un canale diverso da questa pagina: non verrà mostrata di nuovo. Al primo accesso dovrà scegliere una password propria.</p>
          <button type="button" className="secondary" onClick={() => setGenerata(null)}>Chiudi</button>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Data</th><th>Utente</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {dati.richieste.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString("it-IT")}</td>
                <td>{r.utente ? <>{r.utente.nome}<br /><span className="text-muted" style={{ fontSize: 12 }}>{r.utente.email}</span></> : "-"}</td>
                <td><span className={`badge ${r.stato === "in_attesa" ? "yellow" : "green"}`}>{r.stato === "in_attesa" ? "in attesa" : "completata"}</span></td>
                <td>{r.stato === "in_attesa" && <button type="button" className="btn-sm" onClick={() => genera(r)}>Genera password temporanea</button>}</td>
              </tr>
            ))}
            {dati.richieste.length === 0 && <tr><td colSpan={4} className="empty-state">Nessuna richiesta.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
