import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";

const STATO_LABEL = { in_attesa: "In attesa", approvata: "Approvata", rifiutata: "Rifiutata" };
const STATO_BADGE = { in_attesa: "gray", approvata: "green", rifiutata: "red" };

export default function RichiesteCorsoAdmin() {
  const [list, setList] = useState([]);
  const [note, setNote] = useState({});
  const [errore, setErrore] = useState(null);

  function load() { api.get("/richieste-corso").then((r) => setList(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le richieste"))); }
  useEffect(load, []);

  async function valuta(id, stato) {
    setErrore(null);
    try { await api.put(`/richieste-corso/${id}/valuta`, { stato, nota_valutazione: note[id] || "" }); }
    catch (e) { setErrore(erroreDi(e, "Valutazione non riuscita")); }
    load();
  }

  return (
    <div>
      <div className="page-header"><div><h2>Richieste di sessione formativa</h2><p>Richieste dai responsabili, con le persone potenzialmente interessate segnalate.</p></div></div>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Richiedente</th><th>Corso/Argomento</th><th>Note</th><th>Persone</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id}>
                <td>{r.richiedente_nome}</td>
                <td>{r.corso_titolo || r.argomento}</td>
                <td>{r.note}</td>
                <td>{r.persone.map((p) => p.full_name).join(", ") || "—"} ({r.n_persone})</td>
                <td><span className={`badge ${STATO_BADGE[r.stato]}`}>{STATO_LABEL[r.stato]}</span></td>
                <td>
                  {r.stato === "in_attesa" && (
                    <>
                      <input placeholder="nota (opzionale)" value={note[r.id] || ""} onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} style={{ width: 140, marginRight: 4 }} />
                      <button className="btn-sm" onClick={() => valuta(r.id, "approvata")}>Approva</button>{" "}
                      <button className="danger btn-sm" onClick={() => valuta(r.id, "rifiutata")}>Rifiuta</button>
                    </>
                  )}
                  {r.stato !== "in_attesa" && (r.nota_valutazione || "—")}
                </td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan={6} className="empty-state">Nessuna richiesta.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
