import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

export default function MieEdizioni() {
  const [list, setList] = useState([]);

  useEffect(() => { api.get("/edizioni?mie_come_docente=true").then((r) => setList(r.data)); }, []);

  const daTenere = list.filter((e) => e.stato !== "chiusa");
  const storico = list.filter((e) => e.stato === "chiusa");

  return (
    <div>
      <div className="page-header"><div><h2>Le mie sessioni</h2><p>Le formazioni che tieni come docente.</p></div></div>

      <div className="card">
        <h3>Da tenere</h3>
        {daTenere.length === 0 && <p className="empty-state">Nessuna sessione in programma.</p>}
        {daTenere.map((e) => (
          <div key={e.id} className="flex-between" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
            <div>
              <strong>{e.corso_titolo}</strong>
              <div className="text-muted" style={{ fontSize: 13 }}>
                {e.data_inizio ? new Date(e.data_inizio).toLocaleString("it-IT") : "data da definire"} · {e.modalita} · {e.n_iscritti} iscritti
              </div>
            </div>
            <Link to={`/sessioni/${e.id}`}>Apri</Link>
          </div>
        ))}
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Data</th><th>Iscritti</th><th></th></tr></thead>
          <tbody>
            {storico.length === 0 && <tr><td colSpan={5} className="empty-state">Nessuna sessione tenuta finora.</td></tr>}
            {storico.map((e) => (
              <tr key={e.id}>
                <td>{e.corso_titolo}</td><td>{e.modalita}</td>
                <td>{e.data_inizio ? new Date(e.data_inizio).toLocaleDateString("it-IT") : "-"}</td>
                <td>{e.n_iscritti}</td>
                <td><Link to={`/sessioni/${e.id}`}>Apri</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
