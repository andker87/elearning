import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { downloadFile } from "../api";

export default function StoricoCorsi() {
  const [iscrizioni, setIscrizioni] = useState([]);
  const [certificati, setCertificati] = useState([]);

  useEffect(() => {
    api.get("/edizioni/mie/iscrizioni").then((r) => setIscrizioni(r.data));
    api.get("/certificati/mie").then((r) => setCertificati(r.data));
  }, []);

  const storico = iscrizioni.filter((i) => i.stato === "completato" || i.stato === "non_completato");

  return (
    <div>
      <div className="page-header"><div><h2>Storico corsi</h2><p>Tutti i corsi seguiti finora, con i relativi attestati.</p></div></div>

      <div className="table-wrap" style={{ marginBottom: "1.1rem" }}>
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {storico.length === 0 && <tr><td colSpan={4} className="empty-state">Ancora nessun corso concluso.</td></tr>}
            {storico.map((i) => (
              <tr key={i.id}>
                <td>{i.corso_titolo}</td>
                <td>{i.edizione_modalita}</td>
                <td>
                  <span className={`badge ${i.stato === "completato" ? "green" : "red"}`}>{i.stato}</span>{" "}
                  {i.aggiornamento_contenuto === "richiesto" && <span className="badge red">da aggiornare</span>}
                  {i.aggiornamento_contenuto === "disponibile" && <span className="badge gray">aggiornamento disponibile</span>}
                </td>
                <td><Link to={`/sessioni/${i.edizione_id}`}>Apri</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Attestati</h3>
        {certificati.length === 0 && <p className="empty-state">Nessun attestato ancora emesso.</p>}
        <table>
          <thead><tr><th>Codice verifica</th><th>Emesso il</th><th></th></tr></thead>
          <tbody>
            {certificati.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.codice_verifica}</td>
                <td>{new Date(c.emesso_at).toLocaleDateString("it-IT")}</td>
                <td><button className="secondary btn-sm" onClick={() => downloadFile(`/certificati/${c.id}/pdf`, "attestato.pdf")}>Scarica PDF</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
