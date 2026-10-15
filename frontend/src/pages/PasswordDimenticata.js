import React, { useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useBranding } from "../branding";

export default function PasswordDimenticata() {
  const branding = useBranding();
  const [email, setEmail] = useState("");
  const [inviata, setInviata] = useState(false);
  const [errore, setErrore] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try { await api.post("/auth/password-dimenticata", { email }); setInviata(true); }
    catch (err) { setErrore(err.response?.data?.detail || "Errore nell'invio della richiesta"); }
  }

  return (
    <div className="login-screen">
      <div className="login-box">
        <h2>{branding.nome_piattaforma}</h2>
        <p className="text-muted" style={{ marginTop: 0 }}>Password dimenticata</p>
        {inviata ? (
          <p style={{ fontSize: 14 }}>
            Se l'indirizzo è registrato, riceverai le istruzioni: un link via email oppure, se l'invio email non è attivo,
            una password temporanea che ti comunicherà un amministratore.
          </p>
        ) : (
          <form onSubmit={submit}>
            <div className="field"><label>Email</label><input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <button type="submit">Richiedi la reimpostazione</button>
            {errore && <div className="error-msg">{errore}</div>}
          </form>
        )}
        <p style={{ fontSize: 13, marginTop: 16 }}><Link to="/login">Torna all'accesso</Link></p>
      </div>
    </div>
  );
}
