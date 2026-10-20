import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { apriFile, downloadFile, erroreDi } from "../api";
import { MODALITA } from "../sessioni";
import { formattaDurata } from "../durata";

const giorno = (d) => (d ? new Date(d).toLocaleDateString("it-IT") : "—");

export default function StoricoCorsi() {
  const [iscrizioni, setIscrizioni] = useState(null);
  const [certificati, setCertificati] = useState([]);
  const [errore, setErrore] = useState(null);

  useEffect(() => {
    api.get("/edizioni/mie/iscrizioni").then((r) => setIscrizioni(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare lo storico")));
    api.get("/certificati/mie").then((r) => setCertificati(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare gli attestati")));
  }, []);

  async function azione(fn) { setErrore(null); try { await fn(); } catch (e) { setErrore(erroreDi(e, "Impossibile aprire l'attestato")); } }

  // Una riga per ogni corso concluso, con l'attestato se c'e' (il piu' recente, se fossero piu' d'uno).
  const perIscrizione = {};
  certificati.forEach((c) => { if (!perIscrizione[c.iscrizione_id]) perIscrizione[c.iscrizione_id] = c; });
  const righe = (iscrizioni || []).filter((i) => i.stato === "completato" || i.stato === "non_completato")
    .map((i) => ({ i, c: perIscrizione[i.id] }))
    .sort((a, b) => new Date(b.c?.emesso_at || b.i.completato_at || b.i.edizione_data_inizio || 0) - new Date(a.c?.emesso_at || a.i.completato_at || a.i.edizione_data_inizio || 0));

  return (
    <div>
      <div className="page-header"><div><h2>Storico corsi</h2><p>Tutti i corsi seguiti finora, con i relativi attestati.</p></div></div>
      {errore && <div className="error-msg" role="alert">{errore}</div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Data</th><th>Durata</th><th>Esito</th><th>Emesso il</th><th>Codice verifica</th><th></th></tr></thead>
          <tbody>
            {!iscrizioni && <tr><td colSpan={8} className="text-muted">Caricamento...</td></tr>}
            {iscrizioni && righe.length === 0 && <tr><td colSpan={8} className="empty-state">Ancora nessun corso concluso.</td></tr>}
            {righe.map(({ i, c }) => (
              <tr key={i.id}>
                <td><Link to={`/sessioni/${i.edizione_id}?segui=1`}>{i.corso_titolo}</Link></td>
                <td>{MODALITA[i.edizione_modalita] || i.edizione_modalita}</td>
                <td style={{ whiteSpace: "nowrap" }}>{giorno(c?.data_corso || i.edizione_data_inizio || i.completato_at)}</td>
                <td style={{ whiteSpace: "nowrap" }}>{(c?.durata_minuti || i.durata_effettiva_minuti) ? formattaDurata(c?.durata_minuti || i.durata_effettiva_minuti) : "—"}</td>
                <td>
                  <span className={`badge ${i.stato === "completato" ? "green" : "red"}`}>{i.stato === "completato" ? "completato" : "non completato"}</span>{" "}
                  {i.aggiornamento_contenuto === "richiesto" && <span className="badge red">da aggiornare</span>}
                  {i.aggiornamento_contenuto === "disponibile" && <span className="badge gray">aggiornamento disponibile</span>}
                </td>
                <td style={{ whiteSpace: "nowrap" }}>{giorno(c?.emesso_at)}</td>
                <td className="mono">{c?.codice_verifica || <span className="text-muted">—</span>}</td>
                <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                  {c ? <>
                    <button type="button" className="secondary btn-sm" onClick={() => azione(() => apriFile(`/certificati/${c.id}/pdf?inline=true`))}>Visualizza</button>{" "}
                    <button type="button" className="secondary btn-sm" onClick={() => azione(() => downloadFile(`/certificati/${c.id}/pdf`, c.nome_file))}>Scarica PDF</button>
                  </> : <span className="text-muted">nessun attestato</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
