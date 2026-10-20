import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import Finestra from "./Finestra";

// Finestra per eliminare una sessione creata per errore. Controlla prima cosa impedisce l'eliminazione e cosa verrebbe tolto.
export default function EliminaSessione({ sessioneId, nome, onChiudi, onEliminata }) {
  const [esame, setEsame] = useState(null);
  const [conferma, setConferma] = useState("");
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);

  useEffect(() => {
    api.get(`/edizioni/${sessioneId}/eliminazione`).then((r) => setEsame(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile controllare la sessione")));
  }, [sessioneId]);

  const conIscritti = esame?.iscrizioni_vive > 0;
  const puoProcedere = esame?.eliminabile && (!conIscritti || esame.puoi_con_iscritti);
  const confermaOk = !conIscritti || conferma.trim() === "ELIMINA";

  async function elimina() {
    setInvio(true); setErrore(null);
    try { await api.post(`/edizioni/${sessioneId}/elimina`, { conferma: conferma.trim() || null }); onEliminata(); }
    catch (e) { setErrore(erroreDi(e, "Eliminazione non riuscita")); setInvio(false); }
  }

  return (
    <Finestra titolo={`Eliminare la sessione di «${nome}»?`} onChiudi={onChiudi}
      azioni={<>
        <button type="button" className="secondary" onClick={onChiudi}>{puoProcedere ? "Annulla" : "Chiudi"}</button>
        {puoProcedere && <button type="button" className="danger" disabled={invio || !confermaOk} onClick={elimina}>Elimina definitivamente</button>}
      </>}>
      {!esame && !errore && <p className="text-muted">Controllo in corso...</p>}
      {esame && !esame.eliminabile && (
        <><p>Questa sessione <strong>non si può eliminare</strong>:</p><ul>{esame.motivi.map((m) => <li key={m}>{m}</li>)}</ul><p>È parte dello storico della formazione.</p></>
      )}
      {esame && esame.eliminabile && !conIscritti && (
        <><p><strong>L'eliminazione è definitiva e non si può annullare.</strong></p><p>La sessione non ha persone iscritte{esame.iscrizioni_annullate ? ` (solo ${esame.iscrizioni_annullate} ${esame.iscrizioni_annullate === 1 ? "iscrizione annullata" : "iscrizioni annullate"}, che vanno via con lei)` : ""}. Se vuoi solo ritirarla, meglio riportarla in bozza.</p></>
      )}
      {esame && esame.eliminabile && conIscritti && !esame.puoi_con_iscritti && (
        <p>A questa sessione {esame.iscrizioni_vive === 1 ? "è iscritta 1 persona" : `sono iscritte ${esame.iscrizioni_vive} persone`}: la Formazione può eliminare solo le sessioni senza iscritti. Annulla prima le iscrizioni, oppure chiedi all'admin tecnico.</p>
      )}
      {esame && esame.eliminabile && conIscritti && esame.puoi_con_iscritti && (
        <>
          <p><strong>Attenzione: {esame.iscrizioni_vive === 1 ? "c'è 1 persona iscritta" : `ci sono ${esame.iscrizioni_vive} persone iscritte`}.</strong> Con la sessione vanno via le loro iscrizioni, i progressi e gli esiti; le persone non ricevono nessun avviso. L'eliminazione è definitiva.</p>
          <div className="field">
            <label htmlFor="conferma-elimina-sessione">Per confermare scrivi <strong>ELIMINA</strong></label>
            <input id="conferma-elimina-sessione" value={conferma} autoComplete="off" onChange={(e) => setConferma(e.target.value)} />
          </div>
        </>
      )}
      {errore && <div className="error-msg" role="alert">{errore}</div>}
    </Finestra>
  );
}
