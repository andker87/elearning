import React, { useState } from "react";
import api from "../api";

export default function ImpostazioniUtente() {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErrore(null); setMsg(null);
    if (form.new_password !== form.confirm) { setErrore("Le password non coincidono"); return; }
    try {
      await api.put("/auth/me/password", { current_password: form.current_password, new_password: form.new_password });
      setMsg("Password aggiornata");
      setForm({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setErrore(err.response?.data?.detail || "Errore durante l'aggiornamento");
    }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Impostazioni utente</h2><p>Preferenze e sicurezza del tuo account.</p></div></div>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div className="card">
          <h3>Il tuo account</h3>
          <div style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>Nome</div>
            <div style={{ fontWeight: 600 }}>{user?.full_name}</div>
          </div>
          <div style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>Email</div>
            <div>{user?.email}</div>
          </div>
          <div style={{ padding: "10px 0" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>Gruppi</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
              {(user?.groups || []).length === 0
                ? <span className="text-muted" style={{ fontSize: 13 }}>Nessun gruppo</span>
                : user.groups.map((g) => <span key={g.id} className="badge" style={{ background: g.color + "22", color: g.color }}>{g.name}</span>)}
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Modifica password</h3>
          {user?.origine_credenziali && user.origine_credenziali !== "locale" ? (
            <p className="text-muted">Le tue credenziali sono gestite centralmente (dominio aziendale) — la password non si cambia da qui.</p>
          ) : (
            <form onSubmit={submit}>
              <div className="field"><label>Password attuale</label><input required type="password" value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })} /></div>
              <div className="field"><label>Nuova password</label><input required type="password" minLength={6} value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} /></div>
              <div className="field"><label>Conferma nuova password</label><input required type="password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} /></div>
              <button type="submit">Aggiorna password</button>
              {msg && <span style={{ marginLeft: 10, color: "var(--green-text)" }}>{msg}</span>}
              {errore && <div className="error-msg">{errore}</div>}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
