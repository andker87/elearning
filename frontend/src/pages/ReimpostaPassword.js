import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../api";
import { REQUISITI_PASSWORD, passwordValida } from "../passwordPolicy";

export default function ReimpostaPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [form, setForm] = useState({ nuova: "", conferma: "" });
  const [fatto, setFatto] = useState(false);
  const [errore, setErrore] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    if (form.nuova !== form.conferma) { setErrore("Le password non coincidono"); return; }
    if (!passwordValida(form.nuova)) { setErrore(`Password non valida: richiesti ${REQUISITI_PASSWORD}`); return; }
    try { await api.post("/auth/reimposta-password", { token, password_nuova: form.nuova }); setFatto(true); }
    catch (err) { setErrore(err.response?.data?.detail || "Errore nella reimpostazione"); }
  }

  return (
    <div className="login-screen">
      <div className="login-box">
        <h2>Nuova password</h2>
        {fatto ? (
          <p style={{ fontSize: 14 }}>Password aggiornata. <Link to="/login">Accedi</Link></p>
        ) : !token ? (
          <p className="error-msg">Link non valido. <Link to="/password-dimenticata">Richiedine uno nuovo</Link></p>
        ) : (
          <form onSubmit={submit}>
            <p className="text-muted" style={{ marginTop: 0, fontSize: 13 }}>Scegli una nuova password: {REQUISITI_PASSWORD}.</p>
            <div className="field"><label>Nuova password</label><input required type="password" autoComplete="new-password" value={form.nuova} onChange={(e) => setForm({ ...form, nuova: e.target.value })} /></div>
            <div className="field"><label>Conferma</label><input required type="password" autoComplete="new-password" value={form.conferma} onChange={(e) => setForm({ ...form, conferma: e.target.value })} /></div>
            <button type="submit">Salva la password</button>
            {errore && <div className="error-msg">{errore} {errore.startsWith("Link") && <Link to="/password-dimenticata">Richiedine uno nuovo</Link>}</div>}
          </form>
        )}
      </div>
    </div>
  );
}
