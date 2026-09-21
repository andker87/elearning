import React, { useEffect, useState } from "react";
import api from "../api";

export default function Utenti() {
  const [list, setList] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "user", is_external: false, organizzazione_id: "", group_ids: [], origine_credenziali: "locale" });

  function load() { api.get("/auth/users").then((r) => setList(r.data)); }
  useEffect(() => {
    load();
    api.get("/organizzazioni").then((r) => setOrgs(r.data));
    api.get("/groups").then((r) => setGroups(r.data));
  }, []);

  async function submit(e) {
    e.preventDefault();
    const payload = { ...form, organizzazione_id: form.is_external ? form.organizzazione_id : null };
    await api.post("/auth/users", payload);
    setForm({ full_name: "", email: "", password: "", role: "user", is_external: false, organizzazione_id: "", group_ids: [], origine_credenziali: "locale" });
    load();
  }

  async function toggleActive(u) {
    await api.put(`/auth/users/${u.id}`, { is_active: !u.is_active });
    load();
  }

  return (
    <div>
      <div className="page-header"><div><h2>Utenti</h2></div></div>
      <div className="card">
        <h3>Nuovo utente</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome e cognome</label><input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
            <div className="field"><label>Email</label><input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Password iniziale</label><input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
            <div className="field">
              <label>Ruolo funzionale</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="user">Utente (discente / eventuale docente)</option>
                <option value="training_admin">Ufficio Formazione</option>
                <option value="admin_tecnico">Admin tecnico</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={form.is_external} onChange={(e) => setForm({ ...form, is_external: e.target.checked })} /> Utente esterno (docente/collaboratore di un ente terzo)</label>
          </div>
          {form.is_external && (
            <div className="field">
              <label>Organizzazione di riferimento</label>
              <select required value={form.organizzazione_id} onChange={(e) => setForm({ ...form, organizzazione_id: e.target.value })}>
                <option value="">-- seleziona --</option>
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.ragione_sociale}</option>)}
              </select>
            </div>
          )}
          <div className="field">
            <label>Credenziali</label>
            <select value={form.origine_credenziali} onChange={(e) => setForm({ ...form, origine_credenziali: e.target.value })}>
              <option value="locale">Gestite qui (l'utente può cambiare la password)</option>
              <option value="dominio">Gestite dal dominio aziendale (nessun cambio password qui)</option>
            </select>
          </div>
          <div className="field">
            <label>Gruppi</label>
            <select multiple value={form.group_ids} onChange={(e) => setForm({ ...form, group_ids: Array.from(e.target.selectedOptions, (o) => o.value) })} style={{ height: 80 }}>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>
          <button type="submit">Crea utente</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Email</th><th>Ruolo</th><th>Tipo</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((u) => (
              <tr key={u.id}>
                <td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td>
                <td>{u.is_external ? "esterno" : "interno"}</td>
                <td>{u.is_active ? <span className="badge green">attivo</span> : <span className="badge red">disabilitato</span>}</td>
                <td><button className="secondary" onClick={() => toggleActive(u)}>{u.is_active ? "Disabilita" : "Riattiva"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
