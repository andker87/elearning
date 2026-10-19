import React, { useEffect, useMemo, useState } from "react";
import api, { erroreDi } from "../api";
import { elencoUffici } from "../uffici";

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
  const [testo, setTesto] = useState("");
  const [ufficio, setUfficio] = useState("");
  const [mansione, setMansione] = useState("");
  const [scelti, setScelti] = useState(new Set());
  const [gruppi, setGruppi] = useState([]);
  const [mansioni, setMansioni] = useState([]);
  const [esito, setEsito] = useState(null);
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);
  useEffect(() => { api.get("/groups").then((r) => setGruppi(r.data)).catch(() => {}); api.get("/mansioni").then((r) => setMansioni(r.data)).catch(() => {}); }, []);

  const uffici = useMemo(() => elencoUffici(gruppi), [gruppi]);
  const nomeUfficio = useMemo(() => Object.fromEntries(uffici.map((g) => [g.id, g.etichetta])), [uffici]);
  const nomeMansione = useMemo(() => Object.fromEntries(mansioni.map((m) => [m.id, m.name])), [mansioni]);
  // un ufficio comprende anche i suoi sottouffici
  const ufficiInclusi = useMemo(() => {
    if (!ufficio) return null;
    const figli = {};
    gruppi.forEach((g) => { if (g.parent_id) (figli[g.parent_id] = figli[g.parent_id] || []).push(g.id); });
    const insieme = new Set(); const coda = [ufficio];
    while (coda.length) { const x = coda.pop(); if (insieme.has(x)) continue; insieme.add(x); (figli[x] || []).forEach((f) => coda.push(f)); }
    return insieme;
  }, [ufficio, gruppi]);

  const giaIscritti = new Set(iscrizioni.filter((i) => i.stato !== "annullato").map((i) => i.user_id));
  const cerca = testo.trim().toLowerCase();
  const risultati = utenti.filter((u) => !u.is_external && !giaIscritti.has(u.id)
    && (!cerca || `${u.full_name} ${u.email}`.toLowerCase().includes(cerca))
    && (!ufficiInclusi || (u.ufficio_id && ufficiInclusi.has(u.ufficio_id)))
    && (!mansione || (u.mansione_ids || []).includes(mansione)));
  const MOSTRATI = 100;
  const liberi = edizione.posti_max ? Math.max(0, edizione.posti_max - edizione.n_iscritti) : null;
  const selezionati = [...scelti].filter((id) => utenti.some((u) => u.id === id) && !giaIscritti.has(id));
  const tutteSelezionate = risultati.length > 0 && risultati.every((u) => scelti.has(u.id));

  function alterna(id) { const n = new Set(scelti); n.has(id) ? n.delete(id) : n.add(id); setScelti(n); }
  function tutti() { const n = new Set(scelti); risultati.forEach((u) => (tutteSelezionate ? n.delete(u.id) : n.add(u.id))); setScelti(n); }

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
      <div className="row">
        <div className="field"><label htmlFor="dis-cerca">Cerca per nome o email</label><input id="dis-cerca" value={testo} onChange={(e) => setTesto(e.target.value)} placeholder="es. Rossi" /></div>
        <div className="field">
          <label htmlFor="dis-uff">Ufficio (con i sottouffici)</label>
          <select id="dis-uff" value={ufficio} onChange={(e) => setUfficio(e.target.value)}><option value="">Tutti</option>{uffici.map((g) => <option key={g.id} value={g.id}>{g.etichetta}</option>)}</select>
        </div>
        <div className="field">
          <label htmlFor="dis-man">Mansione</label>
          <select id="dis-man" value={mansione} onChange={(e) => setMansione(e.target.value)}><option value="">Tutte</option>{mansioni.filter((m) => m.is_active).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
        </div>
      </div>
      <div className="flex-between" style={{ margin: "4px 0 8px" }}>
        <span className="text-muted" aria-live="polite" style={{ fontSize: 13 }}>
          {risultati.length} {risultati.length === 1 ? "persona" : "persone"} {cerca || ufficio || mansione ? "trovate" : "non ancora iscritte"}
          {risultati.length > MOSTRATI && ` (ne mostro ${MOSTRATI}: restringi con la ricerca o i filtri; «Seleziona tutti» le prende tutte)`}
        </span>
        <button type="button" className="secondary btn-sm" disabled={risultati.length === 0} onClick={tutti}>{tutteSelezionate ? "Deseleziona i risultati" : "Seleziona tutti i risultati"}</button>
      </div>
      <div className="table-wrap" style={{ maxHeight: 280, overflowY: "auto" }}>
        <table>
          <tbody>
            {risultati.slice(0, MOSTRATI).map((u) => (
              <tr key={u.id}>
                <td style={{ width: 34 }}><input type="checkbox" style={{ width: "auto" }} aria-label={`Scegli ${u.full_name}`} checked={scelti.has(u.id)} onChange={() => alterna(u.id)} /></td>
                <td>{u.full_name}<div className="text-muted" style={{ fontSize: 12 }}>{u.email}</div></td>
                <td className="text-muted" style={{ fontSize: 13 }}>{nomeUfficio[u.ufficio_id] || "—"}</td>
                <td>{(u.mansione_ids || []).map((m) => nomeMansione[m] && <span key={m} className="badge gray" style={{ marginRight: 4 }}>{nomeMansione[m]}</span>)}</td>
              </tr>
            ))}
            {risultati.length === 0 && <tr><td className="text-muted">Nessuna persona da iscrivere con questi criteri.</td></tr>}
          </tbody>
        </table>
      </div>
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
