import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";

// Gli uffici sono la struttura organizzativa: albero di uffici e sottouffici, ciascuno con un responsabile.
// Le categorie trasversali (preposto, addetto antincendio...) sono le Mansioni.
export default function Gruppi() {
  const [list, setList] = useState([]);
  const [utenti, setUtenti] = useState([]);
  const [form, setForm] = useState({ name: "", description: "", color: "#5a6b8a", parent_id: "", responsabile_id: "" });
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ name: "", description: "", responsabile_id: "" });
  const [errore, setErrore] = useState(null);

  function load() { api.get("/groups").then((r) => setList(r.data)); }
  useEffect(load, []);
  useEffect(() => { api.get("/auth/users/simple").then((r) => setUtenti(r.data.filter((u) => !u.is_external))); }, []);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try {
      await api.post("/groups", { ...form, parent_id: form.parent_id || null, responsabile_id: form.responsabile_id || null });
    } catch (err) { setErrore(erroreDi(err, "Impossibile creare l'ufficio")); return; }
    setForm({ name: "", description: "", color: "#5a6b8a", parent_id: "", responsabile_id: "" });
    load();
  }

  async function remove(id) {
    if (!window.confirm("Eliminare questo ufficio? I sottouffici diventeranno di primo livello.")) return;
    setErrore(null);
    try { await api.delete(`/groups/${id}`); } catch (err) { setErrore(erroreDi(err, "Impossibile eliminare l'ufficio")); return; }
    load();
  }

  function startEdit(g) {
    setEditId(g.id);
    setEditForm({ name: g.name, description: g.description || "", responsabile_id: g.responsabile_id || "" });
  }

  async function saveEdit(id) {
    setErrore(null);
    try {
      await api.put(`/groups/${id}`, { name: editForm.name, description: editForm.description, responsabile_id: editForm.responsabile_id });
    } catch (err) { setErrore(erroreDi(err, "Impossibile salvare l'ufficio")); return; }
    setEditId(null);
    load();
  }

  // Costruisce l'albero per la visualizzazione a indentazione
  function renderAlbero(parentId, depth) {
    return list.filter((g) => (g.parent_id || null) === parentId).map((g) => (
      <React.Fragment key={g.id}>
        <tr>
          <td style={{ paddingLeft: 16 + depth * 24 }}>
            {editId === g.id
              ? <input aria-label="Nome" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
              : <span className="badge" style={{ background: g.color, color: "#fff" }}>{g.name}</span>}
          </td>
          <td>
            {editId === g.id
              ? <input aria-label="Descrizione" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
              : g.description}
          </td>
          <td>
            {editId === g.id ? (
              <select aria-label="Responsabile" value={editForm.responsabile_id} onChange={(e) => setEditForm({ ...editForm, responsabile_id: e.target.value })}>
                <option value="">-- nessuno --</option>
                {utenti.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
              </select>
            ) : (
              g.responsabile_nome || "—"
            )}
          </td>
          <td>
            {editId === g.id ? (
              <>
                <button className="btn-sm" onClick={() => saveEdit(g.id)}>Salva</button>{" "}
                <button className="btn-sm" onClick={() => setEditId(null)}>Annulla</button>
              </>
            ) : (
              <>
                <button className="btn-sm" onClick={() => startEdit(g)}>Modifica</button>{" "}
                <button className="danger btn-sm" onClick={() => remove(g.id)}>Elimina</button>
              </>
            )}
          </td>
        </tr>
        {renderAlbero(g.id, depth + 1)}
      </React.Fragment>
    ));
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Uffici</h2>
          <p>La struttura dell'organizzazione: uffici e sottouffici, ciascuno con il suo responsabile. Ogni persona interna sta in un solo ufficio (si sceglie dalla sua scheda in Utenti). Un percorso può essere assegnato a un ufficio e ai suoi sottouffici. Per le categorie trasversali (preposto, addetto antincendio...) usa le Mansioni.</p>
        </div>
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="card">
        <h3>Nuovo ufficio</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label>Colore</label><input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Descrizione</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div className="field">
              <label>Sottoufficio di</label>
              <select value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value })}>
                <option value="">-- nessuno (primo livello) --</option>
                {list.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Responsabile</label>
            <select value={form.responsabile_id} onChange={(e) => setForm({ ...form, responsabile_id: e.target.value })}>
              <option value="">-- nessuno --</option>
              {utenti.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </select>
          </div>
          <button type="submit">Crea</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Descrizione</th><th>Responsabile</th><th></th></tr></thead>
          <tbody>
            {renderAlbero(null, 0)}
            {list.length === 0 && <tr><td colSpan={4} className="empty-state">Nessun ufficio ancora creato.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
