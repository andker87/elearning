import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import api, { erroreDi } from "../api";
import { useBranding } from "../branding";

const ERRORI_SSO = {
  non_configurato: "L'accesso aziendale non è configurato.",
  sessione_scaduta: "La sessione di accesso è scaduta: riprova.",
  state_non_valido: "Richiesta di accesso non valida: riprova.",
  rifiutato_da_idp: "L'accesso è stato rifiutato dal provider aziendale.",
  idp_non_raggiungibile: "Il provider aziendale non risponde: riprova fra poco.",
  scambio_codice: "Il provider aziendale ha rifiutato la richiesta: riprova.",
  token_non_valido: "La risposta del provider aziendale non è valida.",
  email_assente: "Il provider aziendale non ha fornito un indirizzo email.",
  email_non_verificata: "L'indirizzo email dell'account aziendale non è verificato.",
  utente_non_abilitato: "Il tuo account aziendale non è abilitato a questa piattaforma: contatta l'Ufficio Formazione.",
  utente_disabilitato: "Il tuo utente è disabilitato.",
  esterno_non_ammesso: "Gli utenti esterni accedono con email e password.",
  admin_non_collegabile: "L'account di Admin tecnico entra con email e password: non si collega all'accesso aziendale.",
  identita_diversa: "Questa email è collegata a un'altra identità aziendale: contatta l'amministratore.",
};

export default function Login() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [sso, setSso] = useState({ enabled: false, label: "" });
  const navigate = useNavigate();
  const branding = useBranding();

  useEffect(() => {
    api.get("/auth/sso/config").then((r) => setSso(r.data)).catch(() => {});

    const params = new URLSearchParams(window.location.search);
    const codiceErrore = params.get("sso_errore");
    if (codiceErrore) {
      setError(ERRORI_SSO[codiceErrore] || "Accesso aziendale non riuscito.");
      window.history.replaceState(null, "", window.location.pathname);
    }

    // Ritorno dall'IdP: il token arriva nel fragment (mai inviato al server né nei log).
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = hash.get("sso_token");
    if (token) {
      window.history.replaceState(null, "", window.location.pathname);
      localStorage.setItem("token", token);
      api.get("/auth/me")
        .then((r) => {
          localStorage.setItem("user", JSON.stringify(r.data));
          navigate("/miei-corsi");
        })
        .catch(() => {
          localStorage.removeItem("token");
          setError("Accesso aziendale non riuscito.");
        });
    }
  }, [navigate]);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    try {
      const r = await api.post("/auth/login", form);
      localStorage.setItem("token", r.data.access_token);
      localStorage.setItem("user", JSON.stringify(r.data.user));
      navigate("/miei-corsi");
    } catch (err) {
      setError(erroreDi(err, "Credenziali non valide"));
    }
  }

  return (
    <div className="login-screen">
      <div className="login-box">
        <h2>{branding.nome_piattaforma}</h2>
        <p className="text-muted" style={{ marginTop: 0 }}>Accedi</p>
        {sso.enabled && (
          <>
            <button type="button" style={{ width: "100%" }} onClick={() => { window.location.href = "/api/auth/sso/login"; }}>
              {sso.label}
            </button>
            <div className="text-muted" style={{ textAlign: "center", fontSize: 12, margin: "12px 0" }}>oppure con email e password</div>
          </>
        )}
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
          <p style={{ fontSize: 13, marginBottom: 0 }}><Link to="/password-dimenticata">Password dimenticata?</Link></p>
          {error && <div className="error-msg">{error}</div>}
        </form>
      </div>
    </div>
  );
}
