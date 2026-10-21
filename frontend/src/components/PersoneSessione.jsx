import React, { useState } from "react";
import api, { erroreDi } from "../api";
import SelettorePersone from "./SelettorePersone";

const RUOLI_DOCENTE = { titolare: "Docente principale", co_docente: "Co-docente" };

// Docenti della sessione: elenco con ruolo e possibilita' di toglierli; si aggiungono solo persone con la qualifica Docente o esterne.
export function SezioneDocenti({ edizione, utenti, puoModificare, ricarica }) {
  const [scelto, setScelto] = useState("");
  const [ruolo, setRuolo] = useState("titolare");
  const [errore, setErrore] = useState(null);
  const gia = new Set(edizione.docenti.map((d) => d.user_id));
  const candidati = utenti.filter((u) => u.is_formatore && !gia.has(u.id));

  async function agisci(fn, msg) {
    setErrore(null);
    try { await fn(); await ricarica(); } catch (e) { setErrore(erroreDi(e, msg)); }
  }

  return (
    <div className="card">
      <h3>Docenti</h3>
      {errore && <div className="error-msg">{errore}</div>}
      {edizione.docenti.length === 0
        ? <p className="text-muted" style={{ margin: "0 0 .6rem" }}>Nessun docente assegnato.</p>
        : (
          <ul style={{ listStyle: "none", padding: 0, margin: "0 0 .8rem" }}>
            {edizione.docenti.map((d) => (
              <li key={d.user_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
                <strong>{d.nome || d.user_id}</strong>
                {d.ruolo === "co_docente" && <span className="badge gray" title="Affianca il docente principale">co-docente</span>}
                {puoModificare && <button type="button" className="danger btn-sm" onClick={() => window.confirm(`Togliere ${d.nome || "questo docente"} dalla sessione?`) && agisci(() => api.delete(`/edizioni/${edizione.id}/docenti/${d.user_id}`), "Impossibile togliere il docente")}>Togli</button>}
              </li>
            ))}
          </ul>
        )}
      {puoModificare && (
        <div className="row" style={{ alignItems: "flex-end" }}>
          <div className="field">
            <label htmlFor="doc-scelta">Aggiungi un docente</label>
            <select id="doc-scelta" value={scelto} onChange={(e) => setScelto(e.target.value)}>
              <option value="">-- scegli --</option>
              {candidati.map((u) => <option key={u.id} value={u.id}>{u.full_name}{u.is_external ? " (esterno)" : ""}</option>)}
            </select>
            {candidati.length === 0 && <span className="text-muted" style={{ fontSize: 12 }}>Nessuno disponibile: si scelgono le persone con la qualifica Docente (si assegna dalla scheda utente) e gli esterni.</span>}
          </div>
          <div className="field" style={{ maxWidth: 180 }}>
            <label htmlFor="doc-ruolo">Ruolo</label>
            <select id="doc-ruolo" value={ruolo} onChange={(e) => setRuolo(e.target.value)}>{Object.entries(RUOLI_DOCENTE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          </div>
          <div className="field"><button type="button" disabled={!scelto} onClick={() => agisci(async () => { await api.post(`/edizioni/${edizione.id}/docenti`, { user_id: scelto, ruolo }); setScelto(""); }, "Impossibile assegnare il docente")}>Aggiungi docente</button></div>
        </div>
      )}
    </div>
  );
}

// Pannello per iscrivere i discenti: ricerca per nome o email, filtri per ufficio (sottouffici compresi) e mansione,
// scelta delle singole persone o di tutti i risultati, un solo clic per iscriverli.
export function AggiungiDiscenti({ edizione, utenti, iscrizioni, ricarica }) {
  const [scelti, setScelti] = useState(new Set());
  const [esito, setEsito] = useState(null);
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);

  const giaIscritti = new Set(iscrizioni.filter((i) => i.stato !== "annullato").map((i) => i.user_id));
  const liberi = edizione.posti_max ? Math.max(0, edizione.posti_max - edizione.n_iscritti) : null;
  const selezionati = [...scelti].filter((id) => utenti.some((u) => u.id === id) && !giaIscritti.has(id));

  async function iscrivi() {
    setInvio(true); setErrore(null); setEsito(null);
    try {
      const r = await api.post(`/edizioni/${edizione.id}/iscrizioni`, selezionati);
      setEsito(r.data);
      setScelti(new Set());
      await ricarica();
    } catch (e) { setErrore(erroreDi(e, "Iscrizione non riuscita")); }
    finally { setInvio(false); }
  }
  const nomiDa = (ids) => ids.map((id) => utenti.find((u) => u.id === id)?.full_name || id);

  return (
    <div className="card card-muted" style={{ marginBottom: "1rem" }}>
      <h4 style={{ margin: "0 0 .6rem" }}>Aggiungi discenti</h4>
      <SelettorePersone utenti={utenti} esclusi={giaIscritti} scelti={scelti} setScelti={setScelti} etichettaTrovate="non ancora iscritte" vuoto="Nessuna persona da iscrivere con questi criteri." />
      <div style={{ marginTop: 10, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" disabled={selezionati.length === 0 || invio} onClick={iscrivi}>{invio ? "Iscrizione in corso..." : `Iscrivi ${selezionati.length} ${selezionati.length === 1 ? "persona" : "persone"}`}</button>
        {liberi !== null && <span className="text-muted" style={{ fontSize: 13 }}>Posti liberi: {liberi} su {edizione.posti_max}</span>}
        {liberi !== null && selezionati.length > liberi && (
          <span style={{ fontSize: 13, color: "var(--yellow-text)" }}>
            ⚠ I posti non bastano: {edizione.lista_attesa_abilitata ? `${selezionati.length - liberi} andranno in lista d'attesa.` : `${selezionati.length - liberi} non verranno iscritte (lista d'attesa non attiva).`}
          </span>
        )}
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      {esito && (
        <div className="success-msg" style={{ marginTop: 8 }}>
          Iscritte {esito.iscritti.length} {esito.iscritti.length === 1 ? "persona" : "persone"}.
          {esito.non_iscritti.length > 0 && <div style={{ color: "var(--red-text)", marginTop: 4 }}>Non iscritte: {esito.non_iscritti.map((x) => `${nomiDa([x.user_id])[0]} (${x.motivo})`).join("; ")}.</div>}
        </div>
      )}
    </div>
  );
}
