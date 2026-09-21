import React, { useEffect, useState } from "react";
import api from "../api";

export default function Gruppi() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: "", description: "", color: "#5a6b8a", parent_id: "" });

  function load() { api.get("/groups").then((r) => setList(r.data.filter((g) => !g.is_system))); }
  useEffect(load, []);

  async function submit(e) {
    e.preventDefault();
    await api.post("/groups", { ...form, parent_id: form.parent_id || null, permissions: {} });
    setForm({ name: "", description: "", color: "#5a6b8a", parent_id: "" });
    load();
  }

  async function remove(id) {
    if (!window.confirm("Eliminare questo gruppo? I sottogruppi diventeranno di primo livello.")) return;
    await api.delete(`/groups/${id}`);
    load();
  }

  // Costruisce l'albero per la visualizzazione a indentazione
  function renderAlbero(parentId, depth) {
    return list.filter((g) => g.parent_id === parentId).map((g) => (
      <React.Fragment key={g.id}>
        <tr>
          <td style={{ paddingLeft: 16 + depth * 24 }}>
            <span className="badge" style={{ background: g.color, color: "#fff" }}>{g.name}</span>
          </td>
          <td>{g.description}</td>
          <td><button className="danger btn-sm" onClick={() => remove(g.id)}>Elimina</button></td>
        </tr>
        {renderAlbero(g.id, depth + 1)}
      </React.Fragment>
    ));
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Gruppi</h2>
          <p>Struttura libera con sottogruppi, per modellare reparti/team reali e assegnare corsi in blocco (es. un percorso con trigger "gruppo").</p>
        </div>
      </div>
      <div className="card">
        <h3>Nuovo gruppo</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label>Colore</label><input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Descrizione</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div className="field">
              <label>Sottogruppo di</label>
              <select value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value })}>
                <option value="">-- nessuno (primo livello) --</option>
                {list.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </div>
          </div>
          <button type="submit">Crea</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Descrizione</th><th></th></tr></thead>
          <tbody>
            {renderAlbero(null, 0)}
            {list.length === 0 && <tr><td colSpan={3} className="empty-state">Nessun gruppo ancora creato.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
