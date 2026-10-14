import React, { useEffect, useState } from "react";
import api from "../api";

const STATO_LABEL = { in_attesa: "In attesa", approvata: "Approvata", rifiutata: "Rifiutata" };
const STATO_BADGE = { in_attesa: "gray", approvata: "green", rifiutata: "red" };

export default function RichiestaCorso() {
  const [corsi, setCorsi] = useState([]);
  const [sottoposti, setSottoposti] = useState([]);
  const [mie, setMie] = useState([]);
  const [form, setForm] = useState({ corso_id: "", argomento: "", note: "", persone_ids: [] });
  const user = JSON.parse(localStorage.getItem("user") || "null");

  function load() { api.get("/richieste-corso").then((r) => setMie(r.data)); }
  useEffect(() => {
    load();
    api.get("/corsi").then((r) => setCorsi(r.data));
    if (user?.id) api.get(`/auth/users/${user.id}/sottoposti`).then((r) => setSottoposti(r.data));
  }, []);

  async function submit(e) {
    e.preventDefault();
    if (!form.corso_id && !form.argomento) return;
    await api.post("/richieste-corso", { ...form, corso_id: form.corso_id || null });
    setForm({ corso_id: "", argomento: "", note: "", persone_ids: [] });
    load();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Richiedi una sessione formativa</h2>
          <p>Chiedi all'Ufficio Formazione di organizzare una sessione su un corso a catalogo o un nuovo argomento. Puoi segnalare le persone potenzialmente interessate per aiutare la valutazione della richiesta.</p>
        </div>
      </div>
      <div className="card">
        <h3>Nuova richiesta</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field">
              <label>Corso a catalogo</label>
              <select value={form.corso_id} onChange={(e) => setForm({ ...form, corso_id: e.target.value, argomento: "" })}>
                <option value="">-- nessuno, è un nuovo argomento --</option>
                {corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
              </select>
            </div>
            {!form.corso_id && (
              <div className="field"><label>Argomento</label><input value={form.argomento} onChange={(e) => setForm({ ...form, argomento: e.target.value })} /></div>
            )}
          </div>
          <div className="field"><label>Note</label><input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></div>
          {sottoposti.length > 0 && (
            <div className="field">
              <label>Persone potenzialmente interessate</label>
              <select multiple value={form.persone_ids} onChange={(e) => setForm({ ...form, persone_ids: Array.from(e.target.selectedOptions, (o) => o.value) })} style={{ height: 80 }}>
                {sottoposti.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
              </select>
            </div>
          )}
          <button type="submit">Invia richiesta</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso/Argomento</th><th>Persone</th><th>Stato</th><th>Nota valutazione</th></tr></thead>
          <tbody>
            {mie.map((r) => (
              <tr key={r.id}>
                <td>{r.corso_titolo || r.argomento}</td>
                <td>{r.n_persone}</td>
                <td><span className={`badge ${STATO_BADGE[r.stato]}`}>{STATO_LABEL[r.stato]}</span></td>
                <td>{r.nota_valutazione || "—"}</td>
              </tr>
            ))}
            {mie.length === 0 && <tr><td colSpan={4} className="empty-state">Nessuna richiesta ancora inviata.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
