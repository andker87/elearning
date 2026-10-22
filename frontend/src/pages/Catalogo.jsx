import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { erroreDi } from "../api";
import { ChipEtichette } from "../components/Etichette";
import { formattaDurata } from "../durata";
import { MODALITA, quando, dove } from "../sessioni";

const STATO_MIO = {
  iscritto: ["green", "stai seguendo"], completato: ["green", "completato"], in_lista_attesa: ["yellow", "in lista d'attesa"],
  richiesta_in_attesa: ["yellow", "in attesa di approvazione"], non_completato: ["gray", "non completato"],
};

export default function Catalogo() {
  const navigate = useNavigate();
  const [righe, setRighe] = useState(null);
  const [cerca, setCerca] = useState("");
  const [errore, setErrore] = useState(null);
  const [esito, setEsito] = useState(null);
  const [inCorso, setInCorso] = useState(null);

  function carica() { api.get("/catalogo").then((r) => setRighe(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare il catalogo"))); }
  useEffect(carica, []);

  async function iscriviti(s) {
    setErrore(null); setEsito(null); setInCorso(s.id);
    try {
      const r = await api.post(`/autoiscrizioni/edizioni/${s.id}`);
      if (r.data.stato === "in_attesa_approvazione") {
        setEsito(`Richiesta inviata per «${s.corso_titolo}»: ${r.data.approva === "formazione" ? "deciderà la Formazione, ti avviseremo" : "in attesa di approvazione del tuo responsabile"}.`);
        carica();
      }
      else if (s.sempre_aperta) navigate(`/sessioni/${s.id}?segui=1`);        // un corso sempre disponibile si guarda subito
      else { setEsito(`Sei iscritto a «${s.corso_titolo}».`); carica(); }
    } catch (e) { setErrore(erroreDi(e, "Iscrizione non riuscita")); }
    setInCorso(null);
  }

  if (errore && !righe) return <div className="error-msg">{errore}</div>;
  if (!righe) return <p className="text-muted">Caricamento...</p>;
  const q = cerca.trim().toLowerCase();
  const visibili = righe.filter((s) => !q || [s.corso_titolo, s.corso_descrizione, ...s.etichette.map((x) => x.nome)].some((t) => (t || "").toLowerCase().includes(q)));
  const completati = visibili.filter((s) => s.mio_stato === "completato");      // in fondo: sono corsi gia' fatti
  const sempre = visibili.filter((s) => s.sempre_aperta && s.mio_stato !== "completato");
  const inProgramma = visibili.filter((s) => !s.sempre_aperta && s.mio_stato !== "completato");

  const azione = (s) => {
    const stato = s.mio_stato;
    if (stato === "iscritto" || stato === "completato" || stato === "in_lista_attesa")
      return <Link to={`/sessioni/${s.id}?segui=1`}>{stato === "completato" ? "Rivedi" : s.sempre_aperta ? "Continua" : "Apri"}</Link>;
    if (stato === "richiesta_in_attesa") return null;
    if (s.bloccato) return <span className="text-muted" style={{ fontSize: 12 }} title={s.bloccato}>🔒 {s.bloccato}</span>;
    const verbo = s.richiede_approvazione ? "Chiedi l'iscrizione" : s.sempre_aperta ? "Guarda il corso" : "Iscriviti";
    return <button type="button" className="btn-sm" disabled={inCorso === s.id} onClick={() => iscriviti(s)}>{inCorso === s.id ? "Un momento..." : verbo}</button>;
  };
  const capsula = (s) => s.mio_stato && STATO_MIO[s.mio_stato] ? <span className={`badge ${STATO_MIO[s.mio_stato][0]}`}>{STATO_MIO[s.mio_stato][1]}</span> : null;

  return (
    <div>
      <div className="page-header"><div><h2>Catalogo</h2><p>I corsi a cui puoi iscriverti da solo: quelli sempre disponibili da guardare quando vuoi, e le sessioni in programma.</p></div></div>
      <div className="card" style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <input type="search" aria-label="Cerca nel catalogo" placeholder="Cerca per titolo, descrizione o etichetta" value={cerca} onChange={(e) => setCerca(e.target.value)} style={{ maxWidth: 380 }} />
        <span className="text-muted" style={{ fontSize: 13 }} aria-live="polite">{visibili.length} {visibili.length === 1 ? "risultato" : "risultati"}</span>
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      {esito && <div className="card card-muted" role="status">{esito}</div>}

      <h3>Sempre disponibili</h3>
      {sempre.length === 0 && (!q || completati.length === 0) && <p className="empty-state">{q ? "Nessun corso corrisponde alla ricerca." : "Nessun corso sempre disponibile per ora."}</p>}
      {sempre.map((s) => (
        <div className="card" key={s.id}>
          <div className="flex-between" style={{ gap: 12, alignItems: "flex-start" }}>
            <div>
              <strong>{s.corso_titolo}</strong> {capsula(s)}
              {s.corso_descrizione && <p className="text-muted" style={{ margin: "4px 0", fontSize: 13 }}>{s.corso_descrizione}</p>}
              <div className="text-muted" style={{ fontSize: 13 }}>
                Video{s.durata_effettiva_minuti ? ` · ${formattaDurata(s.durata_effettiva_minuti)}` : ""} · l'attestato arriva da solo quando lo completi
              </div>
              {s.etichette.length > 0 && <div style={{ marginTop: 4 }}><ChipEtichette etichette={s.etichette} /></div>}
            </div>
            <div>{azione(s)}</div>
          </div>
        </div>
      ))}

      <h3>Sessioni in programma</h3>
      {inProgramma.length === 0 && (!q || completati.length === 0) && <p className="empty-state">{q ? "Nessuna sessione corrisponde alla ricerca." : "Nessuna sessione aperta alle iscrizioni."}</p>}
      {inProgramma.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Corso</th><th>Quando e dove</th><th>Modalità</th><th>Posti</th><th></th></tr></thead>
            <tbody>
              {inProgramma.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.corso_titolo}</strong> {capsula(s)}{s.etichette.length > 0 && <div style={{ marginTop: 4 }}><ChipEtichette etichette={s.etichette} /></div>}</td>
                  <td>{quando(s)} · {dove(s)}{s.durata_effettiva_minuti ? ` · ${formattaDurata(s.durata_effettiva_minuti)}` : ""}</td>
                  <td><span className="badge gray">{MODALITA[s.modalita] || s.modalita}</span></td>
                  <td>{s.posti_liberi == null ? "—" : s.posti_liberi > 0 ? `${s.posti_liberi} liberi` : s.lista_attesa ? "completo (lista d'attesa)" : "completo"}</td>
                  <td>{azione(s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {completati.length > 0 && (
        <>
          <h3>Già completati</h3>
          <div className="table-wrap">
            <table>
              <tbody>
                {completati.map((s) => (
                  <tr key={s.id}>
                    <td><strong>{s.corso_titolo}</strong> {capsula(s)}</td>
                    <td className="text-muted">{s.sempre_aperta ? "Sempre disponibile" : quando(s)}{s.durata_effettiva_minuti ? ` · ${formattaDurata(s.durata_effettiva_minuti)}` : ""}</td>
                    <td style={{ textAlign: "right" }}>{azione(s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
