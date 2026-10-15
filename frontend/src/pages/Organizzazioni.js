import React, { useEffect, useState } from "react";
import api from "../api";
import ExportButton from "../components/ExportButton";

export default function Organizzazioni() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ ragione_sociale: "", tipo: "", partita_iva: "", accreditamento: "", referente: "", email: "", telefono: "", note: "" });

  function load() { api.get("/organizzazioni").then((r) => setList(r.data)); }
  useEffect(load, []);

  async function submit(e) {
    e.preventDefault();
    await api.post("/organizzazioni", form);
    setForm({ ragione_sociale: "", tipo: "", partita_iva: "", accreditamento: "", referente: "", email: "", telefono: "", note: "" });
    load();
  }

  return (
    <div>
      <div className="page-header"><div><h2>Società di formazione</h2><p>Enti accreditati e società a cui appartengono i docenti esterni.</p></div><ExportButton path="/organizzazioni-export/elenco" filename="societa_formazione" /></div>
      <div className="card">
        <h3>Nuova società</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Ragione sociale</label><input required value={form.ragione_sociale} onChange={(e) => setForm({ ...form, ragione_sociale: e.target.value })} /></div>
            <div className="field"><label>Tipo</label><input placeholder="es. ente accreditato" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>P.IVA</label><input value={form.partita_iva} onChange={(e) => setForm({ ...form, partita_iva: e.target.value })} /></div>
            <div className="field"><label>Accreditamento</label><input value={form.accreditamento} onChange={(e) => setForm({ ...form, accreditamento: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Referente</label><input value={form.referente} onChange={(e) => setForm({ ...form, referente: e.target.value })} /></div>
            <div className="field"><label>Email</label><input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          </div>
          <button type="submit">Crea</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Ragione sociale</th><th>Tipo</th><th>Referente</th><th>Email</th></tr></thead>
          <tbody>
            {list.map((o) => (
              <tr key={o.id}><td>{o.ragione_sociale}</td><td>{o.tipo}</td><td>{o.referente}</td><td>{o.email}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
