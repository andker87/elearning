import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { downloadFile, erroreDi } from "../api";
import VideoPlayer from "../components/VideoPlayer";
import TestPlayer from "../components/TestPlayer";
import Gradimento from "../components/Gradimento";
import { formattaDurata } from "../durata";
import { MODALITA, quando, dove } from "../sessioni";

// La sessione vista da chi segue il corso: solo cio' che serve a seguirlo. Niente elenchi di colleghi, niente strumenti di gestione.
export default function SessioneDiscente({ id, gestisce }) {
  const user = (() => { try { return JSON.parse(localStorage.getItem("user") || "null"); } catch { return null; } })();
  const [edizione, setEdizione] = useState(null);
  const [mia, setMia] = useState(undefined);     // la mia iscrizione: undefined = non ancora caricata, null = non iscritto
  const [video, setVideo] = useState(null);
  const [tests, setTests] = useState([]);
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);

  function carica() {
    setErrore(null);
    api.get(`/edizioni/${id}`).then((r) => {
      setEdizione(r.data);
      if (r.data.video_id) api.get(`/video/${r.data.video_id}`).then((rv) => setVideo(rv.data)).catch(() => setVideo(null));
      api.get(`/corsi/${r.data.corso_id}/test`).then((rt) => setTests(rt.data)).catch(() => setTests([]));
    }).catch((e) => setErrore(erroreDi(e, "Impossibile caricare la sessione")));
    api.get(`/edizioni/${id}/iscrizioni`).then((r) => setMia(r.data.find((i) => i.user_id === user?.id && i.stato !== "annullato") || null))
      .catch((e) => setErrore(erroreDi(e, "Impossibile caricare la tua iscrizione")));
  }
  useEffect(carica, [id]); // eslint-disable-line

  async function iscriviti() {
    setInvio(true); setMsg(null);
    try {
      const r = await api.post(`/autoiscrizioni/edizioni/${id}`);
      setMsg(r.data.stato === "in_attesa_approvazione" ? "Richiesta inviata: in attesa di approvazione del tuo responsabile." : "Sei iscritto.");
      carica();
    } catch (e) { setMsg(erroreDi(e, "Iscrizione non riuscita")); }
    setInvio(false);
  }
  async function annulla() {
    if (!window.confirm("Annullare la tua iscrizione?")) return;
    try { await api.post(`/edizioni/${id}/iscrizioni/${mia.id}/annulla`); setMsg("Iscrizione annullata."); carica(); }
    catch (e) { setMsg(erroreDi(e, "Impossibile annullare l'iscrizione")); }
  }
  async function checkin(momento) {
    try { await api.post(`/edizioni/${id}/checkin/discente`, { momento }); setMsg(`Presenza registrata (${momento === "inizio" ? "inizio" : "fine"}).`); }
    catch (e) { setMsg(erroreDi(e, "Presenza non registrata")); }
  }

  if (errore && (!edizione || mia === undefined)) return <div><div className="error-msg">{errore}</div><button type="button" className="secondary btn-sm" onClick={carica}>Riprova</button></div>;
  if (!edizione || mia === undefined) return <p className="text-muted">Caricamento...</p>;
  if (edizione.stato === "bozza" && !gestisce) return <div className="card"><p>Questa sessione non è ancora disponibile.</p><Link to="/catalogo">← Torna al catalogo</Link></div>;

  const chiusa = edizione.stato === "chiusa" || edizione.stato === "annullata";
  const completato = mia?.stato === "completato";
  const puoIscriversi = !mia && !chiusa && edizione.stato !== "bozza" && edizione.corso_permetti_autoiscrizione;
  const docenti = (edizione.docenti || []).map((d) => d.nome).filter(Boolean);
  const inLista = mia?.stato === "in_lista_attesa";
  const segue = mia && !inLista;
  const eVideo = edizione.modalita === "video";

  const capsulaStato = mia && (
    <span className={`badge ${completato ? "green" : mia.stato === "non_completato" ? "red" : inLista ? "yellow" : "green"}`}>
      {completato ? "completato" : mia.stato === "non_completato" ? "non completato" : inLista ? "in lista d'attesa" : "stai seguendo"}</span>
  );
  const intestazione = (
    <div className="page-header">
      <div><h2 style={{ marginBottom: 4 }}>{edizione.corso_titolo}</h2>
        <p className="text-muted" style={{ margin: 0 }}>
          {MODALITA[edizione.modalita] || edizione.modalita}
          {edizione.durata_effettiva_minuti ? ` · ${formattaDurata(edizione.durata_effettiva_minuti)}` : ""}
          {edizione.sempre_aperta ? " · sempre disponibile" : edizione.data_inizio ? ` · ${quando(edizione)}` : ""}
          {" "}{capsulaStato}
        </p>
      </div>
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        {gestisce && <Link to={`/sessioni/${id}`}>Gestisci questa sessione →</Link>}
        <Link to="/miei-corsi">I miei corsi</Link>
      </div>
    </div>
  );
  const informazioni = (
    <div className="card">
      {edizione.corso_descrizione && <p style={{ marginTop: 0 }}>{edizione.corso_descrizione}</p>}
      {!eVideo && <p><strong>Quando:</strong> {quando(edizione)}
        {edizione.data_inizio && mia && (
          <button type="button" className="secondary btn-sm" style={{ marginLeft: 10 }} onClick={() => downloadFile(`/edizioni/${id}/calendario.ics`, "sessione.ics")}>📅 Aggiungi al calendario</button>
        )}</p>}
      {!eVideo && <p><strong>Dove:</strong> {dove(edizione)}</p>}
      {!eVideo && edizione.durata_effettiva_minuti ? <p><strong>Durata:</strong> {formattaDurata(edizione.durata_effettiva_minuti)}</p> : null}
      {docenti.length > 0 && <p><strong>{docenti.length === 1 ? "Docente" : "Docenti"}:</strong> {docenti.join(", ")}</p>}
      {mia && edizione.teams_join_url && <p><strong>Collegamento online:</strong> <a href={edizione.teams_join_url} target="_blank" rel="noreferrer">entra nella riunione</a></p>}
      {edizione.sempre_aperta && <p className="text-muted" style={{ margin: 0 }}>Puoi guardarlo quando vuoi: quando lo completi{tests.length ? " e superi il test" : ""} ricevi l'attestato.</p>}
      {!edizione.corso_descrizione && !docenti.length && !edizione.sempre_aperta && eVideo && <p className="text-muted" style={{ margin: 0 }}>Nessuna informazione aggiuntiva.</p>}
    </div>
  );
  const iscrizione = !mia && (
    <div className="card">
      {puoIscriversi
        ? <button type="button" disabled={invio} onClick={iscriviti}>{edizione.sempre_aperta ? "Inizia il corso" : "Iscrivimi a questa sessione"}</button>
        : <p style={{ margin: 0 }}>{chiusa ? "Questa sessione è conclusa." : "Non sei iscritto a questa sessione: l'iscrizione la fa la Formazione o il tuo responsabile."}</p>}
    </div>
  );
  // Per un corso video il video e' il cuore della pagina: grande, subito sotto il titolo, senza cornici attorno.
  const video_ = segue && eVideo && (
    <div style={{ marginBottom: "1.2rem" }}>
      {video && video.stato === "pronto"
        ? <VideoPlayer video={video} iscrizioneId={mia.id} grande onCompletato={() => { setMsg("Hai completato il corso: il tuo attestato è pronto, lo trovi nello storico dei corsi."); carica(); }} />
        : <div className="card"><p className="text-muted" style={{ margin: 0 }}>Il video non è ancora pronto.</p></div>}
    </div>
  );
  const resto = (
    <>
      {inLista && <div className="card"><p style={{ margin: 0 }}>Sei in lista d'attesa: ti avviseremo se si libera un posto.</p></div>}
      {segue && (edizione.modalita === "presenza" || edizione.modalita === "ibrida") && edizione.checkin_mode === "discente_validato" && !chiusa && (
        <div className="card">
          <h3>La mia presenza</h3>
          <button type="button" onClick={() => checkin("inizio")}>Segna inizio presenza</button>{" "}
          <button type="button" className="secondary" onClick={() => checkin("fine")}>Segna fine presenza</button>
        </div>
      )}
      {segue && tests.map((t) => <TestPlayer key={t.id} testId={t.id} iscrizioneId={mia.id} />)}
      {completato && (
        <div className="card">
          <p style={{ marginTop: 0 }}>Hai completato questo corso. Il tuo attestato è nello <Link to="/storico-corsi">storico dei corsi</Link>.</p>
        </div>
      )}
      {completato && <Gradimento iscrizioneId={mia.id} />}
      {mia && !completato && !chiusa && (
        <p><button type="button" className="secondary btn-sm" onClick={annulla}>Annulla la mia iscrizione</button></p>
      )}
    </>
  );

  return (
    <div>
      {intestazione}
      {msg && <div className="card card-muted" role="status">{msg}</div>}
      {eVideo ? <>{video_}{iscrizione}{resto}{informazioni}</> : <>{informazioni}{iscrizione}{resto}</>}
    </div>
  );
}
