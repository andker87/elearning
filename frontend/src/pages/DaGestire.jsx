import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { erroreDi } from "../api";
import Icona from "../components/Icona";
import { conferma } from "../components/conferma";
import { MODALITA, quando } from "../sessioni";

const SCHEDE = [{ id: "tutto", label: "Tutto" }, { id: "richieste", label: "Richieste" }, { id: "sessioni", label: "Sessioni" }, { id: "percorsi", label: "Percorsi" }];
const giorno = (d) => (d ? new Date(d).toLocaleDateString("it-IT", { day: "numeric", month: "long" }) : "");

// Tutto quello che aspetta una decisione della Formazione: richieste di iscrizione e di corsi, sessioni finite da chiudere,
// persone dei percorsi in attesa di una sessione. Ogni riga ha la sua azione.
export default function DaGestire() {
  const navigate = useNavigate();
  const [dati, setDati] = useState(null);
  const [scheda, setScheda] = useState("tutto");
  const [errore, setErrore] = useState(null);
  const [esito, setEsito] = useState(null);
  const [invio, setInvio] = useState(null);

  function carica() { api.get("/da-gestire").then((r) => setDati(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le cose da gestire"))); }
  useEffect(carica, []);

  async function agisci(chiave, fn, messaggio) {
    setInvio(chiave); setErrore(null); setEsito(null);
    try { await fn(); setEsito(messaggio); carica(); } catch (e) { setErrore(erroreDi(e, "Operazione non riuscita")); }
    setInvio(null);
  }
  const approva = (r) => agisci(r.id, () => api.put(`/richieste-iscrizione/${r.id}/approva`), `Iscrizione di ${r.persona} approvata.`);
  async function rifiuta(r) {
    if (!(await conferma("Chi ha chiesto riceve l'esito.", { titolo: `Rifiutare la richiesta per ${r.persona}?`, etichetta: "Rifiuta", pericolo: true }))) return;
    agisci(r.id, () => api.put(`/richieste-iscrizione/${r.id}/rifiuta`, { motivo: null }), `Richiesta per ${r.persona} rifiutata.`);
  }
  async function chiudi(s) {
    if (!(await conferma("Le presenze diventano definitive, si decide chi ha completato e si generano gli attestati. Dopo non si modifica più.", { titolo: `Chiudere «${s.corso_titolo}»?`, etichetta: "Chiudi la sessione" }))) return;
    agisci(s.id, () => api.post(`/edizioni/${s.id}/chiudi`), `Sessione «${s.corso_titolo}» chiusa.`);
  }

  if (errore && !dati) return <div className="error-msg" role="alert">{errore}</div>;
  if (!dati) return <p className="text-muted">Caricamento...</p>;
  const richieste = dati.richieste_iscrizione.length + dati.richieste_corsi.length;
  const conti = { tutto: dati.totale, richieste, sessioni: dati.sessioni_da_chiudere.length, percorsi: dati.percorsi.length };
  const mostra = (gruppo) => scheda === "tutto" || scheda === gruppo;

  return (
    <div>
      <div className="page-header"><div><h2>Da gestire</h2>
        <p>{dati.totale === 0 ? "Niente in sospeso: tutto quello che aspetta una decisione compare qui." : `${dati.totale} ${dati.totale === 1 ? "cosa aspetta" : "cose aspettano"} una decisione.`}</p></div></div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" key={x.id} aria-pressed={scheda === x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}{conti[x.id] > 0 && <span className="tab-conta">{conti[x.id]}</span>}</button>)}
      </div>
      {errore && <div className="error-msg" role="alert">{errore}</div>}
      {esito && <div className="success-msg" role="status">{esito}</div>}
      {dati.totale === 0 && <div className="card"><p className="empty-state" style={{ margin: 0 }}>Nessuna richiesta, nessuna sessione da chiudere, nessuno in attesa nei percorsi.</p></div>}

      {mostra("richieste") && dati.richieste_iscrizione.length > 0 && (
        <div className="card lista-azioni">
          <h3>Richieste di iscrizione <span className="text-muted">({dati.richieste_iscrizione.length})</span></h3>
          {dati.richieste_iscrizione.map((r) => (
            <div className="riga-azione" key={r.id}>
              <Icona nome={r.autorichiesta ? "user" : "users"} />
              <div><strong>{r.persona}</strong> · «{r.corso_titolo}»{r.data_inizio ? ` del ${giorno(r.data_inizio)}` : ""}
                <div className="text-muted piccolo">{r.autorichiesta ? "richiesta dalla persona stessa" : `chiesta da ${r.richiedente}`} · {r.ufficio || "senza ufficio"}{r.posti_liberi != null ? ` · ${r.posti_liberi} posti liberi` : ""}</div></div>
              <div className="azioni"><button type="button" className="secondary btn-sm" disabled={invio === r.id} onClick={() => rifiuta(r)}>Rifiuta</button><button type="button" className="btn-sm" disabled={invio === r.id} onClick={() => approva(r)}>Approva</button></div>
            </div>
          ))}
        </div>
      )}
      {mostra("richieste") && dati.richieste_corsi.length > 0 && (
        <div className="card lista-azioni">
          <h3>Richieste di corsi <span className="text-muted">({dati.richieste_corsi.length})</span></h3>
          {dati.richieste_corsi.map((r) => (
            <div className="riga-azione" key={r.id}>
              <Icona nome="list" />
              <div><strong>{r.ufficio || r.richiedente}</strong> chiede «{r.titolo}»<div className="text-muted piccolo">{r.richiedente}{r.persone ? ` · ${r.persone} ${r.persone === 1 ? "persona interessata" : "persone interessate"}` : ""}{r.a_catalogo ? " · corso a catalogo" : " · argomento nuovo"}</div></div>
              <div className="azioni"><Link className="btn-link" to="/richieste-corso-admin">Valuta</Link></div>
            </div>
          ))}
        </div>
      )}
      {mostra("sessioni") && dati.sessioni_da_chiudere.length > 0 && (
        <div className="card lista-azioni">
          <h3>Sessioni da chiudere <span className="text-muted">({dati.sessioni_da_chiudere.length})</span></h3>
          {dati.sessioni_da_chiudere.map((s) => (
            <div className="riga-azione" key={s.id}>
              <Icona nome="cal" />
              <div><Link to={`/sessioni/${s.id}`}><strong>{s.corso_titolo}</strong></Link> è finita<div className="text-muted piccolo">{MODALITA[s.modalita] || s.modalita} · {quando(s)} · {s.n_iscritti} {s.n_iscritti === 1 ? "iscritto" : "iscritti"} · gli attestati partono alla chiusura</div></div>
              <div className="azioni"><button type="button" className="btn-sm" disabled={invio === s.id} onClick={() => chiudi(s)}>Chiudi</button></div>
            </div>
          ))}
        </div>
      )}
      {mostra("percorsi") && dati.percorsi.length > 0 && (
        <div className="card lista-azioni">
          <h3>Percorsi: persone senza sessione <span className="text-muted">({dati.percorsi.length})</span></h3>
          {dati.percorsi.map((p) => (
            <div className="riga-azione" key={p.corso_id}>
              <Icona nome="route" />
              <div>
                {p.in_attesa > 0 && <><strong>{p.in_attesa} {p.in_attesa === 1 ? "persona aspetta" : "persone aspettano"}</strong> una sessione di «{p.corso_titolo}»</>}
                {p.in_attesa > 0 && p.da_rifare > 0 && "; "}
                {p.da_rifare > 0 && <><strong>{p.da_rifare} da rifare</strong>{p.in_attesa === 0 ? ` in «${p.corso_titolo}»` : ""}</>}
                <div className="text-muted piccolo">{p.percorsi.length === 1 ? "percorso" : "percorsi"} {p.percorsi.join(", ")}{p.in_attesa > 0 ? " · pubblicando una sessione vengono iscritte da sole" : ""}</div>
              </div>
              <div className="azioni"><button type="button" className="btn-sm" onClick={() => navigate(`/sessioni?nuova=${p.corso_id}`)}>Crea una sessione</button></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
