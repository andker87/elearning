import React, { useEffect, useState } from "react";
import api from "../api";

export default function Ruoli() {
  const [list, setList] = useState([]);
  const [editing, setEditing] = useState(null);

  function load() { api.get("/groups").then((r) => setList(r.data.filter((g) => g.is_system))); }
  useEffect(load, []);

  async function salva(g) {
    await api.put(`/groups/${g.id}`, { name: g.name, description: g.description, color: g.color });
    setEditing(null);
    load();
  }

  return (
    <div>
      <div className="page-header">
        <div><h2>Ruoli</h2><p>Le categorie fisse della piattaforma (non eliminabili, ma rinominabili a piacere).</p></div>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Descrizione</th><th></th></tr></thead>
          <tbody>
            {list.map((g) => (
              <tr key={g.id}>
                {editing?.id === g.id ? (
                  <>
                    <td><input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></td>
                    <td><input value={editing.description || ""} onChange={(e) => setEditing({ ...editing, description: e.target.value })} /></td>
                    <td>
                      <button className="btn-sm" onClick={() => salva(editing)}>Salva</button>{" "}
                      <button className="secondary btn-sm" onClick={() => setEditing(null)}>Annulla</button>
                    </td>
                  </>
                ) : (
                  <>
                    <td><span className="badge" style={{ background: g.color, color: "#fff" }}>{g.name}</span></td>
                    <td>{g.description}</td>
                    <td><button className="secondary btn-sm" onClick={() => setEditing(g)}>Rinomina</button></td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
