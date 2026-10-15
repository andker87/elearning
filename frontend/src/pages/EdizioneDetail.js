import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { downloadFile, erroreDi } from "../api";
import VideoPlayer from "../components/VideoPlayer";
import TestPlayer from "../components/TestPlayer";
import Gradimento from "../components/Gradimento";

export default function EdizioneDetail() {
  const { id } = useParams();
  const [edizione, setEdizione] = useState(null);
  const [iscrizioni, setIscrizioni] = useState([]);
  const [utenti, setUtenti] = useState([]);
  const [video, setVideo] = useState(null);
  const [tests, setTests] = useState([]);
  const [selectedUser, setSelectedUser] = useState("");
  const [teamsUrl, setTeamsUrl] = useState("");
  const [msg, setMsg] = useState(null);
  const [sottoposti, setSottoposti] = useState([]);
  const [selectedSottoposto, setSelectedSottoposto] = useState("");
  const [comunicazioni, setComunicazioni] = useState([]);
  const [oggettoCom, setOggettoCom] = useState("");
  const [messaggioCom, setMessaggioCom] = useState("");
  const [invioCom, setInvioCom] = useState(false);
  const user = JSON.parse(localStorage.getItem("user") || "null");

  const [erroreCaricamento, setErroreCaricamento] = useState(null);
  const falla = (testo) => (e) => setErroreCaricamento(erroreDi(e, testo));

  function load() {
    api.get(`/edizioni/${id}`).then((r) => {
      setEdizione(r.data); setErroreCaricamento(null);
      if (r.data.video_id) api.get(`/video/${r.data.video_id}`).then((rv) => setVideo(rv.data)).catch(falla("Impossibile caricare il video"));
      api.get(`/corsi/${r.data.corso_id}/test`).then((rt) => setTests(rt.data)).catch(falla("Impossibile caricare i test"));
      const puoComunicare = r.data.docenti?.some((d) => d.user_id === user?.id)
        || user?.role === "admin_tecnico" || user?.role === "training_admin";
      if (puoComunicare) api.get(`/edizioni/${id}/comunicazioni`).then((rc) => setComunicazioni(rc.data)).catch(falla("Impossibile caricare le comunicazioni"));
    }).catch(falla("Impossibile caricare la sessione"));
    api.get(`/edizioni/${id}/iscrizioni`).then((r) => setIscrizioni(r.data)).catch(falla("Impossibile caricare le iscrizioni"));
  }
  useEffect(() => {
    load();
    api.get("/auth/users/simple").then((r) => setUtenti(r.data)).catch(falla("Impossibile caricare l'elenco delle persone"));
    if (user?.id) api.get(`/auth/users/${user.id}/sottoposti`).then((r) => setSottoposti(r.data)).catch(falla("Impossibile caricare le persone sotto la tua responsabilità"));
  }, [id]);

  const isDocente = edizione?.docenti?.some((d) => d.user_id === user?.id);
  const isAdmin = user?.role === "admin_tecnico" || user?.role === "training_admin";
  const nome = (uid) => utenti.find((u) => u.id === uid)?.full_name || uid;
  const miaIscrizione = iscrizioni.find((i) => i.user_id === user?.id && i.stato !== "annullato");
  const sottopostiNonIscritti = sottoposti.filter((s) => !iscrizioni.some((i) => i.user_id === s.id && i.stato !== "annullato"));

  // Esegue un'azione e, se il server la rifiuta, mostra il motivo invece di non dire niente.
  async function tenta(azione, erroreDefault) {
    setMsg(null);
    try { await azione(); } catch (e) { setMsg(erroreDi(e, erroreDefault)); }
  }
  async function assegnaDocente() {
    if (!selectedUser) return;
    await tenta(async () => {
      await api.post(`/edizioni/${id}/docenti`, { user_id: selectedUser, ruolo: "titolare" });
      setSelectedUser(""); load();
    }, "Impossibile assegnare il docente");
  }
  async function iscrivi() {
    if (!selectedUser) return;
    await tenta(async () => {
      const r = await api.post(`/edizioni/${id}/iscrizioni`, [selectedUser]);
      if (r.data.non_iscritti?.length) window.alert(`Iscrizione non effettuata: ${r.data.non_iscritti[0].motivo}`);
      setSelectedUser(""); load();
    }, "Iscrizione non riuscita");
  }
  async function iscriviSottoposto() {
    if (!selectedSottoposto) return;
    try {
      const r = await api.post(`/edizioni/${id}/iscrizioni`, [selectedSottoposto]);
      if (r.data.non_iscritti?.length) window.alert(`Iscrizione non effettuata: ${r.data.non_iscritti[0].motivo}`);
    } catch (err) { window.alert(erroreDi(err, "Iscrizione non riuscita")); }
    setSelectedSottoposto(""); load();
  }
  async function autoiscriviti() {
    try {
      const r = await api.post(`/autoiscrizioni/edizioni/${id}`);
      setMsg(r.data.stato === "in_attesa_approvazione" ? "Richiesta inviata: in attesa di approvazione del tuo responsabile." : "Iscrizione effettuata.");
      load();
    } catch (e) { setMsg(erroreDi(e, "Errore")); }
  }
  async function annulla(iscrizioneId) {
    if (!window.confirm("Annullare questa iscrizione?")) return;
    await tenta(async () => { await api.post(`/edizioni/${id}/iscrizioni/${iscrizioneId}/annulla`); load(); }, "Impossibile annullare l'iscrizione");
  }
  async function checkinDiscente(momento) {
    await tenta(async () => { await api.post(`/edizioni/${id}/checkin/discente`, { momento }); setMsg(`Check-in ${momento} registrato`); }, "Check-in non registrato");
  }
  async function checkinDocentePresente(uid) {
    await tenta(async () => { await api.post(`/edizioni/${id}/checkin/docente`, [{ user_id: uid, presente: true }]); load(); }, "Presenza non registrata");
  }
  async function linkTeams() {
    await tenta(async () => { await api.post(`/edizioni/${id}/teams/link`, { join_url: teamsUrl }); load(); }, "Link non salvato");
  }
  async function creaRiunioneAuto() {
    try {
      await api.post(`/edizioni/${id}/teams/crea-riunione`);
      load();
    } catch (e) { setMsg(erroreDi(e, "Errore")); }
  }
  async function sincronizzaPresenze() {
    try {
      const r = await api.post(`/edizioni/${id}/teams/sincronizza-presenze`);
      setMsg(`Presenze sincronizzate: ${r.data.applicati.length}`);
    } catch (e) { setMsg(erroreDi(e, "Errore — usa il report manuale")); }
  }
  async function inviaComunicazione() {
    if (!oggettoCom.trim() || !messaggioCom.trim()) return;
    setInvioCom(true);
    try {
      const r = await api.post(`/edizioni/${id}/comunicazione`, { oggetto: oggettoCom, messaggio: messaggioCom });
      setMsg(`Comunicazione inviata a ${r.data.inviati} iscritti.`);
      setOggettoCom(""); setMessaggioCom("");
      load();
    } catch (e) {
      setMsg(erroreDi(e, "Errore nell'invio della comunicazione"));
    } finally {
      setInvioCom(false);
    }
  }

  async function chiudi() {
    if (!window.confirm("Chiudere la sessione? Le evidenze diventeranno definitive e verranno generati i certificati.")) return;
    await tenta(async () => {
      const r = await api.post(`/edizioni/${id}/chiudi`);
      setMsg(`Sessione chiusa. Completati: ${r.data.esiti.filter((x) => x.completato).length}/${r.data.esiti.length}`);
      load();
    }, "Impossibile chiudere la sessione");
  }

  if (!edizione) return erroreCaricamento ? <div><div className="error-msg">{erroreCaricamento}</div><button type="button" className="secondary btn-sm" onClick={load}>Riprova</button></div> : <div>Caricamento...</div>;

  return (
    <div>
      <div className="page-header">
        <div><h2>Sessione — {edizione.modalita}</h2></div>
        {isAdmin && (
          <div>
            <button className="secondary" onClick={() => downloadFile(`/edizioni/${id}/report/iscrizioni.csv`, "report_iscrizioni.csv")}>Report iscrizioni CSV</button>{" "}
            <button className="secondary" onClick={() => downloadFile(`/edizioni/${id}/report/gradimenti.csv`, "report_gradimenti.csv")}>Report gradimenti CSV</button>
          </div>
        )}
      </div>
      {msg && <div className="card card-muted">{msg}</div>}

      <div className="card">
        <p><strong>Stato:</strong> <span className="badge gray">{edizione.stato}</span></p>
        <p>
          <strong>Data:</strong> {edizione.data_inizio ? new Date(edizione.data_inizio).toLocaleString("it-IT") : "-"}
          {edizione.data_inizio && (
            <button type="button" className="secondary btn-sm" style={{ marginLeft: 10 }}
              onClick={() => downloadFile(`/edizioni/${id}/calendario.ics`, "sessione.ics")}>
              📅 Aggiungi al calendario
            </button>
          )}
        </p>
        {edizione.luogo && <p><strong>Luogo:</strong> {edizione.luogo}</p>}
        {edizione.posti_max && (
          <p><strong>Posti:</strong> {edizione.n_iscritti}/{edizione.posti_max}
            {edizione.n_lista_attesa > 0 && <> — {edizione.n_lista_attesa} in lista d'attesa</>}</p>
        )}
        {(edizione.modalita === "presenza" || edizione.modalita === "ibrida") && (
          <p><strong>Check-in:</strong> {edizione.checkin_mode === "docente" ? "registro docente" : "self check-in + validazione docente"}</p>
        )}
      </div>

      {!isAdmin && !miaIscrizione && edizione.corso_permetti_autoiscrizione && edizione.stato !== "chiusa" && (
        <div className="card">
          <h3>Vuoi partecipare?</h3>
          <button onClick={autoiscriviti}>Iscrivimi a questa sessione</button>
        </div>
      )}

      <div className="card">
        <h3>Docenti</h3>
        <ul>{edizione.docenti.map((d) => <li key={d.user_id}>{nome(d.user_id)} ({d.ruolo})</li>)}</ul>
        {isAdmin && edizione.stato !== "chiusa" && (
          <div className="row">
            <select value={selectedUser} onChange={(e) => setSelectedUser(e.target.value)}>
              <option value="">-- utente --</option>
              {utenti.map((u) => <option key={u.id} value={u.id}>{u.full_name}{u.is_external ? " (esterno)" : ""}</option>)}
            </select>
            <button onClick={assegnaDocente}>Assegna come docente</button>
            <button className="secondary" onClick={iscrivi}>Iscrivi come discente</button>
          </div>
        )}
      </div>

      {!isAdmin && sottopostiNonIscritti.length > 0 && edizione.stato !== "chiusa" && (
        <div className="card">
          <h3>Iscrivi una tua risorsa</h3>
          <div className="row">
            <select value={selectedSottoposto} onChange={(e) => setSelectedSottoposto(e.target.value)}>
              <option value="">-- persona --</option>
              {sottopostiNonIscritti.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
            </select>
            <button className="secondary" onClick={iscriviSottoposto}>Iscrivi</button>
          </div>
        </div>
      )}

      {(edizione.modalita === "ibrida" || edizione.modalita === "remoto") && edizione.stato !== "chiusa" && (
        <div className="card">
          <h3>Componente Teams</h3>
          {edizione.teams_join_url && <p>Link riunione: <a href={edizione.teams_join_url} target="_blank" rel="noreferrer">{edizione.teams_join_url}</a></p>}
          <div className="row">
            <div className="field"><label>Incolla link riunione Teams</label><input value={teamsUrl} onChange={(e) => setTeamsUrl(e.target.value)} /></div>
          </div>
          <button className="secondary" onClick={linkTeams}>Salva link</button>{" "}
          <button className="secondary" onClick={creaRiunioneAuto}>Crea automaticamente (richiede Graph API)</button>{" "}
          <button className="secondary" onClick={sincronizzaPresenze}>Sincronizza presenze da Teams</button>
        </div>
      )}

      {edizione.modalita === "video" && video && video.stato === "pronto" && (
        <div className="card">
          <h3>Video</h3>
          {miaIscrizione ? <VideoPlayer video={video} iscrizioneId={miaIscrizione.id} /> : <p className="text-muted">Non sei iscritto a questa sessione.</p>}
        </div>
      )}

      <div className="table-wrap" style={{ marginBottom: "1.1rem" }}>
        <table>
          <thead><tr><th>Nome</th><th>Stato</th><th>Evidenze</th><th></th></tr></thead>
          <tbody>
            {iscrizioni.filter((i) => i.stato !== "annullato").map((i) => {
              const puoAnnullare = edizione.stato !== "chiusa" && (isAdmin || i.user_id === user?.id || sottoposti.some((s) => s.id === i.user_id));
              return (
                <tr key={i.id}>
                  <td>{i.user_full_name}</td>
                  <td><span className={`badge ${i.stato === "completato" ? "green" : i.stato === "non_completato" ? "red" : i.stato === "in_lista_attesa" ? "gray" : "gray"}`}>{i.stato === "in_lista_attesa" ? "in lista d'attesa" : i.stato}</span></td>
                  <td>{i.n_evidenze}</td>
                  <td>
                    {isDocente && edizione.checkin_mode === "docente" && edizione.stato !== "chiusa" && (
                      <button className="secondary btn-sm" onClick={() => checkinDocentePresente(i.user_id)}>Segna presente</button>
                    )}{" "}
                    {puoAnnullare && <button className="danger btn-sm" onClick={() => annulla(i.id)}>Annulla</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {(edizione.modalita === "presenza" || edizione.modalita === "ibrida") && edizione.checkin_mode === "discente_validato" && edizione.stato !== "chiusa" && (
        <div className="card">
          <h3>Il mio check-in</h3>
          <button onClick={() => checkinDiscente("inizio")}>Segna inizio presenza</button>{" "}
          <button className="secondary" onClick={() => checkinDiscente("fine")}>Segna fine presenza</button>
        </div>
      )}

      {miaIscrizione && tests.map((t) => <TestPlayer key={t.id} testId={t.id} iscrizioneId={miaIscrizione.id} />)}

      {miaIscrizione && miaIscrizione.stato === "completato" && (
        <Gradimento iscrizioneId={miaIscrizione.id} docenti={edizione.docenti.map((d) => ({ id: d.user_id, nome: nome(d.user_id) }))} />
      )}

      {(isDocente || isAdmin) && (
        <div className="card">
          <h3>Comunicazioni agli iscritti</h3>
          <p className="text-muted" style={{ fontSize: 13 }}>
            Invia un annuncio a tutti gli iscritti (compresa la lista d'attesa): lo ricevono via notifica in-app, email e notifica push.
          </p>
          <div className="field"><label>Oggetto</label><input value={oggettoCom} onChange={(e) => setOggettoCom(e.target.value)} placeholder="Es. Promemoria materiale da portare" /></div>
          <div className="field"><label>Messaggio</label><textarea rows={3} value={messaggioCom} onChange={(e) => setMessaggioCom(e.target.value)} /></div>
          <button type="button" disabled={invioCom || !oggettoCom.trim() || !messaggioCom.trim()} onClick={inviaComunicazione}>
            {invioCom ? "Invio..." : "Invia comunicazione"}
          </button>
          {comunicazioni.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="text-muted" style={{ fontSize: 12, marginBottom: 6 }}>Comunicazioni inviate</div>
              {comunicazioni.map((c) => (
                <div key={c.id} style={{ padding: ".5rem 0", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{c.oggetto}</div>
                  <div style={{ fontSize: 12, color: "var(--text2)" }}>{c.messaggio}</div>
                  <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2 }}>
                    {c.mittente} · {new Date(c.created_at).toLocaleString("it-IT")} · {c.n_destinatari} destinatari
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {(isDocente || isAdmin) && edizione.stato !== "chiusa" && (
        <div className="card">
          <h3>Chiusura sessione</h3>
          <p className="text-muted">Attesta definitivamente le evidenze raccolte e genera i certificati per chi risulta completato. Operazione non reversibile.</p>
          <button onClick={chiudi}>Chiudi e attesta sessione</button>
        </div>
      )}
    </div>
  );
}
