import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { REQUISITI_PASSWORD } from "../passwordPolicy";

export default function Setup() {
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/setup/init", form);
      navigate("/login");
    } catch (err) {
      setError(err.response?.data?.detail || "Errore durante il setup");
    }
  }

  return (
    <div className="login-screen">
      <div className="login-box">
        <h2>Primo avvio</h2>
        <p style={{ fontSize: 13, color: "#666" }}>
          Crea l'utente amministratore tecnico. Da qui potrai poi impostare gruppi,
          utenti, organizzazioni e tutto il resto della piattaforma.
        </p>
        <form onSubmit={submit}>
          <div className="field">
            <label>Nome e cognome</label>
            <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div className="field">
            <label>Email</label>
            <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field">
            <label>Password</label>
            <input required type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <p className="text-muted" style={{ fontSize: 12 }}>La password deve avere {REQUISITI_PASSWORD}.</p>
          <button type="submit">Configura piattaforma</button>
          {error && <div className="error-msg">{error}</div>}
        </form>
      </div>
    </div>
  );
}
