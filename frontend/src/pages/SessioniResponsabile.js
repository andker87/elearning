import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { FiltroEtichette, ChipEtichette } from "../components/Etichette";

export default function SessioniResponsabile() {
  const [list, setList] = useState([]);
  const [corsi, setCorsi] = useState([]);
  const [daApprovare, setDaApprovare] = useState([]);

  function loadApprovazioni() { api.get("/autoiscrizioni/da-approvare").then((r) => setDaApprovare(r.data)); }

  const [filtroEtichette, setFiltroEtichette] = useState([]);
  useEffect(() => { api.get("/edizioni", { params: filtroEtichette.length ? { etichette: filtroEtichette } : {} }).then((r) => setList(r.data)); }, [filtroEtichette]);
  useEffect(() => {
    api.get("/corsi").then((r) => setCorsi(r.data));
    loadApprovazioni();
  }, []);

  const corsoTitolo = (id) => corsi.find((c) => c.id === id)?.titolo || id;

  async function approva(id) { await api.put(`/autoiscrizioni/${id}/approva`); loadApprovazioni(); }
  async function rifiuta(id) { await api.put(`/autoiscrizioni/${id}/rifiuta`); loadApprovazioni(); }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Sessioni</h2>
          <p>Apri una sessione per iscrivere una delle tue risorse (le persone sotto la tua responsabilità).</p>
        </div>
      </div>

      {daApprovare.length > 0 && (
        <div className="card">
          <h3>Auto-iscrizioni da approvare</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Persona</th><th>Corso</th><th></th></tr></thead>
              <tbody>
                {daApprovare.map((r) => (
                  <tr key={r.id}>
                    <td>{r.user_nome}</td>
                    <td>{r.corso_titolo}</td>
                    <td>
                      <button className="btn-sm" onClick={() => approva(r.id)}>Approva</button>{" "}
                      <button className="danger btn-sm" onClick={() => rifiuta(r.id)}>Rifiuta</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ maxWidth: 420 }}><FiltroEtichette valore={filtroEtichette} onChange={setFiltroEtichette} /></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Data</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((e) => (
              <tr key={e.id}>
                <td>{corsoTitolo(e.corso_id)}{e.corso_etichette?.length > 0 && <div style={{ marginTop: 4 }}><ChipEtichette etichette={e.corso_etichette} /></div>}</td>
                <td>{e.modalita}</td>
                <td>{e.data_inizio ? new Date(e.data_inizio).toLocaleString("it-IT") : "-"}</td>
                <td><span className="badge gray">{e.stato}</span></td>
                <td><Link to={`/sessioni/${e.id}`}>Apri</Link></td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan={5} className="empty-state">Nessuna sessione disponibile.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
