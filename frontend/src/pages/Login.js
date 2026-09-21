import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function Login() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError(null);
    try {
      const r = await api.post("/auth/login", form);
      localStorage.setItem("token", r.data.access_token);
      localStorage.setItem("user", JSON.stringify(r.data.user));
      navigate("/miei-corsi");
    } catch (err) {
      setError(err.response?.data?.detail || "Credenziali non valide");
    }
  }

  return (
    <div className="login-screen">
      <div className="login-box">
        <h2>Accedi</h2>
        <form onSubmit={submit}>
          <div className="field">
            <label>Email</label>
            <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field">
            <label>Password</label>
            <input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <button type="submit">Accedi</button>
          {error && <div className="error-msg">{error}</div>}
        </form>
      </div>
    </div>
  );
}
