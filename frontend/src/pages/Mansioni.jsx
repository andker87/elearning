import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import SelettoreColore from "../components/SelettoreColore";
import { conferma } from "../components/conferma";

// Le mansioni sono etichette trasversali (preposto, addetto antincendio...): una persona può averne più d'una,
// servono ad assegnare percorsi in blocco e a filtrare gli elenchi. Non danno permessi.
export default function Mansioni() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: "", description: "", color: "#5a6b8a" });
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ name: "", description: "", color: "#5a6b8a", is_active: true });
  const [errore, setErrore] = useState(null);

  function load() { api.get("/mansioni").then((r) => setList(r.data)); }
  useEffect(load, []);
  useEffect(() => { if (editId) document.getElementById("m-form-modifica")?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [editId]);

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try { await api.post("/mansioni", form); } catch (err) { setErrore(erroreDi(err, "Impossibile creare la mansione")); return; }
    setForm({ name: "", description: "", color: "#5a6b8a" });
    load();
  }

  async function salva(id) {
    setErrore(null);
    try { await api.put(`/mansioni/${id}`, editForm); } catch (err) { setErrore(erroreDi(err, "Impossibile salvare la mansione")); return; }
    setEditId(null);
    load();
  }

  async function elimina(m) {
    if (!(await conferma(`Viene tolta alle ${m.persone} persone che la hanno.`, { titolo: `Eliminare la mansione «${m.name}»?`, etichetta: "Elimina la mansione", pericolo: true }))) return;
    setErrore(null);
    try { await api.delete(`/mansioni/${m.id}`); } catch (err) { setErrore(erroreDi(err, "Impossibile eliminare la mansione")); return; }
    load();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Mansioni</h2>
          <p>Etichette trasversali agli uffici, per esempio preposto o addetto antincendio. Una persona può averne più d'una. Servono ad assegnare un percorso a tutti quelli che hanno la mansione e a filtrare l'elenco utenti; non danno permessi. Si assegnano dalla scheda di ciascun utente.</p>
        </div>
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="card">
        <h3>Nuova mansione</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label>Colore</label><SelettoreColore valore={form.color} anteprima={form.name} onChange={(c) => setForm({ ...form, color: c })} /></div>
          </div>
          <div className="field"><label>Descrizione</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <button type="submit">Crea</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Descrizione</th><th>Persone</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((m) => (
              <React.Fragment key={m.id}>
                <tr>
                  <td><span className="badge" style={{ background: m.color, color: "#fff" }}>{m.name}</span></td>
                  <td>{m.description}</td>
                  <td>{m.persone}</td>
                  <td>{m.is_active ? <span className="badge green">attiva</span> : <span className="badge gray">non attiva</span>}</td>
                  <td>
                    <button className="btn-sm" onClick={() => { setErrore(null); setEditId(m.id); setEditForm({ name: m.name, description: m.description || "", color: m.color || "#5a6b8a", is_active: m.is_active }); }}>Modifica</button>{" "}
                    <button className="danger btn-sm" onClick={() => elimina(m)}>Elimina</button>
                  </td>
                </tr>
                {editId === m.id && (
                  <tr>
                    <td colSpan={5} style={{ background: "var(--bg3)" }}>
                      <form id="m-form-modifica" onSubmit={(e) => { e.preventDefault(); salva(m.id); }}>
                        <h4 style={{ margin: "8px 0" }}>Modifica «{m.name}»</h4>
                        <div className="row">
                          <div className="field"><label htmlFor="m-nome">Nome</label><input id="m-nome" required autoFocus value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /></div>
                          <div className="field"><label htmlFor="m-colore">Colore</label><SelettoreColore id="m-colore" valore={editForm.color} anteprima={editForm.name} onChange={(c) => setEditForm((f) => ({ ...f, color: c }))} /></div>
                        </div>
                        <div className="field"><label htmlFor="m-descr">Descrizione</label><input id="m-descr" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} /></div>
                        <div className="field"><label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })} />Attiva</label></div>
                        <button type="submit">Salva</button>{" "}
                        <button type="button" className="secondary" onClick={() => setEditId(null)}>Annulla</button>
                      </form>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {list.length === 0 && <tr><td colSpan={5} className="empty-state">Nessuna mansione ancora creata.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
