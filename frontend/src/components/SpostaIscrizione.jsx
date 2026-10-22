import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import Finestra from "./Finestra";
import { quando, dove } from "../sessioni";

// La Formazione sposta una persona su un'altra sessione dello stesso corso (scelta fra quelle aperte alle iscrizioni).
export default function SpostaIscrizione({ nomePersona, titoloCorso, corsoId, edizioneId, iscrizioneId, onChiudi, onSpostata }) {
  const [sessioni, setSessioni] = useState(null);
  const [scelta, setScelta] = useState("");
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);

  useEffect(() => {
    api.get("/edizioni", { params: { corso_id: corsoId } })
      .then((r) => setSessioni(r.data.filter((e) => e.id !== edizioneId && (e.stato === "pianificata" || e.stato === "in_corso") && !e.da_chiudere)))
      .catch((e) => setErrore(erroreDi(e, "Impossibile caricare le sessioni")));
  }, [corsoId, edizioneId]);

  async function sposta() {
    setInvio(true); setErrore(null);
    try { await api.post(`/edizioni/${edizioneId}/iscrizioni/${iscrizioneId}/sposta`, { edizione_id: scelta }); onSpostata(); }
    catch (e) { setErrore(erroreDi(e, "Spostamento non riuscito")); setInvio(false); }
  }

  return (
    <Finestra titolo={`Sposta ${nomePersona}`} onChiudi={onChiudi}
      azioni={<>
        <button type="button" className="secondary" onClick={onChiudi}>Annulla</button>
        <button type="button" disabled={!scelta || invio} onClick={sposta}>{invio ? "Sposto..." : "Sposta"}</button>
      </>}>
      <p style={{ marginTop: 0 }}>Scegli un'altra sessione di <strong>{titoloCorso}</strong>. La persona viene tolta dalla sessione attuale (il posto si libera) e iscritta alla nuova; riceve un avviso.</p>
      {!sessioni && !errore && <p className="text-muted">Caricamento...</p>}
      {sessioni && sessioni.length === 0 && <p className="empty-state">Non ci sono altre sessioni aperte di questo corso: pubblicane una dalla pagina Sessioni.</p>}
      {sessioni && sessioni.length > 0 && (
        <div role="radiogroup" aria-label="Sessione di arrivo">
          {sessioni.map((e) => {
            const piena = e.posti_max && e.n_iscritti >= e.posti_max;
            return (
              <label key={e.id} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", borderBottom: "1px solid var(--border)", margin: 0 }}>
                <input type="radio" name="arrivo" style={{ width: "auto", marginTop: 4 }} checked={scelta === e.id} onChange={() => setScelta(e.id)} />
                <span>
                  <strong>{quando(e)}</strong> · {dove(e)}
                  <span className="text-muted" style={{ display: "block", fontSize: 12 }}>
                    {e.sempre_aperta ? "sempre disponibile" : e.posti_max ? `${e.n_iscritti}/${e.posti_max} posti${piena ? (e.lista_attesa_abilitata ? " — completa, finirebbe in lista d'attesa" : " — completa") : ""}` : `${e.n_iscritti} iscritti, posti illimitati`}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      )}
      {errore && <div className="error-msg" role="alert" style={{ marginTop: 8 }}>{errore}</div>}
    </Finestra>
  );
}
