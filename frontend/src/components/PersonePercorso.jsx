import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import SelettorePersone from "./SelettorePersone";
import SpostaIscrizione from "./SpostaIscrizione";
import { quando } from "../sessioni";
import { conferma } from "./conferma";

export const STATO_PASSO = {
  completato: ["green", "completato"], iscritto: ["blue", "iscritto"], in_lista_attesa: ["yellow", "lista d'attesa"],
  bloccato: ["gray", "bloccato"], in_attesa_sessione: ["yellow", "in attesa di una sessione"], da_rifare: ["red", "da rifare"],
};

// Pannello di un percorso: assegnarlo a delle persone (che vengono subito iscritte ai corsi sbloccati) e vedere a che punto sono.
export default function PersonePercorso({ percorso, onCambia }) {
  const [utenti, setUtenti] = useState([]);
  const [assegnazioni, setAssegnazioni] = useState(null);
  const [scelti, setScelti] = useState(new Set());
  const [invio, setInvio] = useState(false);
  const [esito, setEsito] = useState(null);
  const [errore, setErrore] = useState(null);
  const [daSpostare, setDaSpostare] = useState(null);

  function carica() {
    api.get(`/percorsi/${percorso.id}/assegnazioni`).then((r) => setAssegnazioni(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le assegnazioni")));
  }
  useEffect(() => { api.get("/auth/users/simple").then((r) => setUtenti(r.data)).catch(() => {}); carica(); }, [percorso.id]); // eslint-disable-line

  const gia = new Set((assegnazioni || []).map((a) => a.user_id));
  const selezionati = [...scelti].filter((id) => utenti.some((u) => u.id === id) && !gia.has(id));

  async function assegna() {
    setInvio(true); setErrore(null); setEsito(null);
    try {
      const r = await api.post(`/percorsi/${percorso.id}/assegna`, selezionati);
      setEsito(r.data); setScelti(new Set()); carica(); onCambia && onCambia();
    } catch (e) { setErrore(erroreDi(e, "Assegnazione non riuscita")); }
    setInvio(false);
  }
  async function togli(a) {
    if (!(await conferma("Le iscrizioni già fatte restano; se non servono più vanno annullate una per una dalle sessioni.", { titolo: `Togliere il percorso a ${a.nome}?`, etichetta: "Togli il percorso", pericolo: true }))) return;
    setErrore(null);
    try { await api.delete(`/percorsi/${percorso.id}/assegnazioni/${a.user_id}`); carica(); onCambia && onCambia(); }
    catch (e) { setErrore(erroreDi(e, "Impossibile togliere il percorso")); }
  }

  return (
    <div>
      <h4 style={{ margin: "8px 0" }}>Assegna «{percorso.nome}» a delle persone</h4>
      <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>Chi lo riceve viene iscritto subito ai corsi già sbloccati (gli altri a mano a mano che completa i precedenti) e avvisato. Se un corso non ha ancora una sessione, resta in attesa e viene iscritto appena ne pubblichi una.</p>
      <SelettorePersone utenti={utenti} esclusi={gia} scelti={scelti} setScelti={setScelti} etichettaTrovate="senza questo percorso" vuoto="Nessuna persona da assegnare con questi criteri." />
      <div style={{ margin: "10px 0 16px", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" disabled={selezionati.length === 0 || invio} onClick={assegna}>{invio ? "Assegno..." : `Assegna a ${selezionati.length} ${selezionati.length === 1 ? "persona" : "persone"}`}</button>
      </div>
      {errore && <div className="error-msg" role="alert">{errore}</div>}
      {esito && (
        <div className="success-msg" role="status" style={{ marginBottom: 12 }}>
          Assegnato a {esito.assegnati.length} {esito.assegnati.length === 1 ? "persona" : "persone"}. Iscrizioni fatte: {esito.iscrizioni}{esito.in_lista_attesa ? ` (più ${esito.in_lista_attesa} in lista d'attesa)` : ""}.
          {esito.in_attesa_sessione > 0 && <div style={{ color: "var(--yellow-text)" }}>{esito.in_attesa_sessione} {esito.in_attesa_sessione === 1 ? "corso aspetta" : "corsi aspettano"} una sessione: la Formazione è stata avvisata.</div>}
          {esito.saltati.length > 0 && <div>Saltate: {esito.saltati.map((x) => x.motivo).join("; ")}.</div>}
        </div>
      )}

      <h4 style={{ margin: "8px 0" }}>Chi ha il percorso {assegnazioni && `(${assegnazioni.length})`}</h4>
      {!assegnazioni && !errore && <p className="text-muted">Caricamento...</p>}
      {assegnazioni && assegnazioni.length === 0 && <p className="empty-state">Nessuno ha ancora questo percorso.</p>}
      {assegnazioni && assegnazioni.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Persona</th><th>Corsi</th><th></th></tr></thead>
            <tbody>
              {assegnazioni.map((a) => (
                <tr key={a.user_id}>
                  <td style={{ verticalAlign: "top" }}><strong>{a.nome}</strong>{!a.attivo && <span className="badge gray" style={{ marginLeft: 6 }}>non attiva</span>}
                    <div className="text-muted" style={{ fontSize: 12 }}>{a.ufficio || "senza ufficio"} · {a.completati}/{a.totale} completati</div></td>
                  <td>
                    {a.passi.map((s) => {
                      const [classe, testo] = STATO_PASSO[s.stato] || ["gray", s.stato];
                      return (
                        <div key={s.step_id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "2px 0" }}>
                          <span>{s.ordine}. {s.corso_titolo}</span>
                          <span className={`badge ${classe}`} title={s.stato === "bloccato" && s.richiede_titoli.length ? `Prima: ${s.richiede_titoli.join(", ")}` : undefined}>{testo}</span>
                          {(s.stato === "iscritto" || s.stato === "in_lista_attesa") && <span className="text-muted" style={{ fontSize: 12 }}>{quando({ data_inizio: s.data_inizio, sempre_aperta: s.sempre_aperta })}</span>}
                          {s.stato === "bloccato" && s.richiede_titoli.length > 0 && <span className="text-muted" style={{ fontSize: 12 }}>dopo {s.richiede_titoli.join(", ")}</span>}
                          {(s.stato === "iscritto" || s.stato === "in_lista_attesa") && (
                            <button type="button" className="secondary btn-sm" onClick={() => setDaSpostare({ a, s })}>Sposta</button>
                          )}
                        </div>
                      );
                    })}
                  </td>
                  <td style={{ whiteSpace: "nowrap", textAlign: "right", verticalAlign: "top" }}><button type="button" className="danger btn-sm" onClick={() => togli(a)}>Togli</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {daSpostare && (
        <SpostaIscrizione nomePersona={daSpostare.a.nome} titoloCorso={daSpostare.s.corso_titolo} corsoId={daSpostare.s.corso_id}
          edizioneId={daSpostare.s.edizione_id} iscrizioneId={daSpostare.s.iscrizione_id}
          onChiudi={() => setDaSpostare(null)} onSpostata={() => { setDaSpostare(null); carica(); }} />
      )}
    </div>
  );
}
