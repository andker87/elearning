import React, { useState } from "react";
import api from "../api";
import { REQUISITI_PASSWORD, passwordValida } from "../passwordPolicy";

// Mostrata al posto dell'app finche' la persona non sceglie una password propria
// (password assegnata da un amministratore o temporanea).
export default function CambioPasswordObbligatorio() {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [errore, setErrore] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    if (form.new_password !== form.confirm) { setErrore("Le password non coincidono"); return; }
    if (!passwordValida(form.new_password)) { setErrore(`Password non valida: richiesti ${REQUISITI_PASSWORD}`); return; }
    try {
      const r = await api.put("/auth/me/password", { current_password: form.current_password, new_password: form.new_password });
      localStorage.setItem("token", r.data.access_token);
      const user = JSON.parse(localStorage.getItem("user") || "{}");
      localStorage.setItem("user", JSON.stringify({ ...user, password_da_cambiare: false }));
      window.location.reload();
    } catch (err) {
      setErrore(err.response?.data?.detail || "Errore durante l'aggiornamento");
    }
  }
  function esci() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
  }

  return (
    <div className="login-screen">
      <div className="login-box">
        <h2>Scegli la tua password</h2>
        <p className="text-muted" style={{ marginTop: 0, fontSize: 13 }}>
          La password attuale è stata assegnata da un amministratore. Prima di continuare scegline una tua: {REQUISITI_PASSWORD}.
        </p>
        <form onSubmit={submit}>
          <div className="field"><label>Password attuale</label><input required type="password" autoComplete="current-password" value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })} /></div>
          <div className="field"><label>Nuova password</label><input required type="password" autoComplete="new-password" value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} /></div>
          <div className="field"><label>Conferma nuova password</label><input required type="password" autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} /></div>
          <button type="submit">Salva e continua</button>{" "}
          <button type="button" className="secondary" onClick={esci}>Esci</button>
          {errore && <div className="error-msg">{errore}</div>}
        </form>
      </div>
    </div>
  );
}
