import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api, { apriFile, downloadFile, erroreDi } from "../api";
import { MODALITA } from "../sessioni";
import { formattaDurata } from "../durata";
import { dataIt } from "../date";


export default function StoricoCorsi() {
  // null = in caricamento, "errore" = richiesta fallita, altrimenti l'elenco: i due caricamenti sono indipendenti
  const [iscrizioni, setIscrizioni] = useState(null);
  const [certificati, setCertificati] = useState(null);
  const [errore, setErrore] = useState(null);

  const generazione = useRef(0);        // una risposta di un tentativo precedente (dopo «Riprova») non sovrascrive quella nuova
  function carica() {
    const mia = ++generazione.current;
    const attuale = () => mia === generazione.current;
    setErrore(null); setIscrizioni(null); setCertificati(null);
    api.get("/edizioni/mie/iscrizioni").then((r) => { if (attuale()) setIscrizioni(r.data); })
      .catch((e) => { if (attuale()) { setIscrizioni("errore"); setErrore(erroreDi(e, "Impossibile caricare lo storico")); } });
    api.get("/certificati/mie").then((r) => { if (attuale()) setCertificati(r.data); })
      .catch((e) => { if (attuale()) { setCertificati("errore"); setErrore(erroreDi(e, "Impossibile caricare gli attestati")); } });
  }
  useEffect(carica, []);

  async function azione(fn) { setErrore(null); try { await fn(); } catch (e) { setErrore(erroreDi(e, "Impossibile aprire l'attestato")); } }

  const certErrore = certificati === "errore";
  // Tutti gli attestati di ogni corso concluso (di solito uno): una riga per attestato, o una sola riga senza attestato.
  const perIscrizione = {};
  (Array.isArray(certificati) ? certificati : []).forEach((c) => { (perIscrizione[c.iscrizione_id] = perIscrizione[c.iscrizione_id] || []).push(c); });
  const righe = [];
  (Array.isArray(iscrizioni) ? iscrizioni : []).filter((i) => i.stato === "completato" || i.stato === "non_completato").forEach((i) => {
    const lista = perIscrizione[i.id] || [];
    (lista.length ? lista : [null]).forEach((c, n) => righe.push({ i, c, chiave: `${i.id}-${c?.id || n}` }));
  });
  const quando = ({ i, c }) => new Date(c?.emesso_at || i.completato_at || i.edizione_data_inizio || 0);
  righe.sort((a, b) => quando(b) - quando(a));
  const inCaricamento = iscrizioni === null;

  return (
    <div>
      <div className="page-header"><div><h2>Storico e attestati</h2><p>Tutti i corsi seguiti finora, con i relativi attestati.</p></div></div>
      {errore && <div className="error-msg" role="alert">{errore} <button type="button" className="secondary btn-sm" onClick={carica}>Riprova</button></div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Data</th><th>Durata</th><th>Esito</th><th>Emesso il</th><th>Codice verifica</th><th></th></tr></thead>
          <tbody>
            {inCaricamento && <tr><td colSpan={8} className="text-muted">Caricamento...</td></tr>}
            {iscrizioni === "errore" && <tr><td colSpan={8} className="text-muted">Lo storico non è disponibile in questo momento.</td></tr>}
            {Array.isArray(iscrizioni) && righe.length === 0 && <tr><td colSpan={8} className="empty-state">Ancora nessun corso concluso.</td></tr>}
            {righe.map(({ i, c, chiave }) => (
              <tr key={chiave}>
                <td><Link to={`/sessioni/${i.edizione_id}?segui=1`}>{i.corso_titolo}</Link></td>
                <td>{MODALITA[i.edizione_modalita] || i.edizione_modalita}</td>
                <td style={{ whiteSpace: "nowrap" }}>{dataIt(c?.data_corso || i.edizione_data_inizio || i.completato_at)}</td>
                <td style={{ whiteSpace: "nowrap" }}>{(c?.durata_minuti || i.durata_effettiva_minuti) ? formattaDurata(c?.durata_minuti || i.durata_effettiva_minuti) : "—"}</td>
                <td>
                  <span className={`badge ${i.stato === "completato" ? "green" : "red"}`}>{i.stato === "completato" ? "completato" : "non completato"}</span>{" "}
                  {i.aggiornamento_contenuto === "richiesto" && <span className="badge red">da aggiornare</span>}
                  {i.aggiornamento_contenuto === "disponibile" && <span className="badge gray">aggiornamento disponibile</span>}
                </td>
                <td style={{ whiteSpace: "nowrap" }}>{dataIt(c?.emesso_at)}</td>
                <td className="mono">{c?.codice_verifica || <span className="text-muted">—</span>}</td>
                <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                  {c ? <>
                    <button type="button" className="secondary btn-sm" onClick={() => azione(() => apriFile(`/certificati/${c.id}/pdf?inline=true`))}>Visualizza</button>{" "}
                    <button type="button" className="secondary btn-sm" onClick={() => azione(() => downloadFile(`/certificati/${c.id}/pdf`, c.nome_file))}>Scarica PDF</button>
                  </> : certificati === null ? <span className="text-muted">...</span>
                    : certErrore ? <span className="text-muted">attestati non disponibili</span>
                    : <span className="text-muted">nessun attestato</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
