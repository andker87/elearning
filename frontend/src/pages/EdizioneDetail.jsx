import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import api, { downloadFile, erroreDi } from "../api";
import VideoPlayer from "../components/VideoPlayer";
import EliminaSessione from "../components/EliminaSessione";
import SpostaIscrizione from "../components/SpostaIscrizione";
import CampoDurata from "../components/CampoDurata";
import { SezioneDocenti, AggiungiDiscenti } from "../components/PersoneSessione";
import { formattaDurata } from "../durata";
import TestPlayer from "../components/TestPlayer";
import Gradimento from "../components/Gradimento";
import SessioneDiscente from "./SessioneDiscente";

// Una sessione ha due volti: chi la segue (discente) e chi la gestisce (Formazione, docenti della sessione).
// Chi non gestisce vede sempre e solo la vista del discente; chi gestisce vede quella di gestione, tranne quando
// arriva per seguire il corso (da «I miei corsi», dal Catalogo): allora vede quella del discente, con un rimando per gestirla.
export default function EdizioneDetail() {
  const { id } = useParams();
  const segui = new URLSearchParams(useLocation().search).get("segui") === "1";
  const user = (() => { try { return JSON.parse(localStorage.getItem("user") || "null"); } catch { return null; } })();
  const [docenti, setDocenti] = useState(undefined);
  const [errore, setErrore] = useState(null);
  useEffect(() => {
    setDocenti(undefined); setErrore(null);
    api.get(`/edizioni/${id}`).then((r) => setDocenti((r.data.docenti || []).map((d) => d.user_id))).catch((e) => setErrore(erroreDi(e, "Impossibile caricare la sessione")));
  }, [id]);
  if (errore) return <div className="error-msg">{errore}</div>;
  if (docenti === undefined) return <p className="text-muted">Caricamento...</p>;
  const gestisce = !!user?.poteri_formazione || docenti.includes(user?.id);
  return gestisce && !segui ? <GestioneSessione /> : <SessioneDiscente id={id} gestisce={gestisce} />;
}

function GestioneSessione() {
  const { id } = useParams();
  const navigate = useNavigate();
  const segui = new URLSearchParams(useLocation().search).get("segui") === "1";   // si arriva da «I miei corsi»: si sta seguendo il corso
  const [anteprimaVideo, setAnteprimaVideo] = useState(false);
  const [modificaDurata, setModificaDurata] = useState(null);   // { valore } mentre si cambia la durata della sessione
  const [edizione, setEdizione] = useState(null);
  const [iscrizioni, setIscrizioni] = useState([]);
  const [utenti, setUtenti] = useState([]);
  const [video, setVideo] = useState(null);
  const [tests, setTests] = useState([]);
  const [teamsUrl, setTeamsUrl] = useState("");
  const [msg, setMsg] = useState(null);
  const [sottoposti, setSottoposti] = useState([]);
  const [comunicazioni, setComunicazioni] = useState([]);
  const [oggettoCom, setOggettoCom] = useState("");
  const [messaggioCom, setMessaggioCom] = useState("");
  const [invioCom, setInvioCom] = useState(false);
  const user = JSON.parse(localStorage.getItem("user") || "null");

  const [erroreCaricamento, setErroreCaricamento] = useState(null);
  const falla = (testo) => (e) => setErroreCaricamento(erroreDi(e, testo));

  function load() {
    setErroreCaricamento(null);  // un nuovo tentativo parte da zero: se fallisce di nuovo, l'errore ricompare
    api.get(`/edizioni/${id}`).then((r) => {
      setEdizione(r.data);
      if (r.data.video_id) api.get(`/video/${r.data.video_id}`).then((rv) => setVideo(rv.data)).catch(falla("Impossibile caricare il video"));
      api.get(`/corsi/${r.data.corso_id}/test`).then((rt) => setTests(rt.data)).catch(falla("Impossibile caricare i test"));
      const puoComunicare = r.data.docenti?.some((d) => d.user_id === user?.id)
        || user?.poteri_formazione;
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
  const isAdmin = !!user?.poteri_formazione;
  const puoGestire = isAdmin || !!isDocente;       // chi gestisce la sessione non la sta seguendo
  const nome = (uid) => utenti.find((u) => u.id === uid)?.full_name || uid;
  const miaIscrizione = iscrizioni.find((i) => i.user_id === user?.id && i.stato !== "annullato");

  // Esegue un'azione e, se il server la rifiuta, mostra il motivo invece di non dire niente.
  async function tenta(azione, erroreDefault) {
    setMsg(null);
    try { await azione(); } catch (e) { setMsg(erroreDi(e, erroreDefault)); }
  }
  // La durata si cambia con lo stesso PUT della sessione (che riceve tutti i campi): si rimandano quelli attuali.
  async function salva(modifiche, erroreDefault, dopo) {
    const e = edizione;
    await tenta(async () => {
      await api.put(`/edizioni/${id}`, { corso_id: e.corso_id, modalita: e.modalita, data_inizio: e.data_inizio, data_fine: e.data_fine, luogo: e.luogo,
        posti_max: e.posti_max, lista_attesa_abilitata: e.lista_attesa_abilitata, checkin_mode: e.checkin_mode, teams_mode: e.teams_mode,
        video_id: e.video_id, ente_erogatore: e.ente_erogatore, note: e.note, sempre_aperta: !!e.sempre_aperta, durata_minuti: e.durata_minuti || null, ...modifiche });
      if (dopo) dopo();
      load();
    }, erroreDefault);
  }
  const salvaDurata = (minuti) => salva({ durata_minuti: minuti || null }, "Impossibile cambiare la durata", () => setModificaDurata(null));
  const [eliminando, setEliminando] = useState(false);
  const [daSpostare, setDaSpostare] = useState(null);       // iscrizione da spostare su un'altra sessione dello stesso corso
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
          <strong>Data:</strong> {edizione.sempre_aperta ? "Sempre disponibile" : edizione.data_inizio ? new Date(edizione.data_inizio).toLocaleString("it-IT") : "-"}
          {edizione.data_inizio && !edizione.sempre_aperta && (
            <button type="button" className="secondary btn-sm" style={{ marginLeft: 10 }}
              onClick={() => downloadFile(`/edizioni/${id}/calendario.ics`, "sessione.ics")}>
              📅 Aggiungi al calendario
            </button>
          )}
        </p>
        <p>
          <strong>Durata:</strong> {edizione.durata_effettiva_minuti ? formattaDurata(edizione.durata_effettiva_minuti) : "non indicata"}
          {edizione.durata_modificata && <span className="badge yellow" style={{ marginLeft: 8 }} title="Diversa da quella del corso">modificata (il corso prevede {formattaDurata(edizione.durata_corso_minuti)})</span>}
          {!edizione.durata_modificata && edizione.durata_effettiva_minuti && edizione.durata_minuti == null && <span className="text-muted" style={{ marginLeft: 8, fontSize: 12 }}>dal corso</span>}
          {isAdmin && edizione.stato !== "chiusa" && !modificaDurata && (
            <button type="button" className="secondary btn-sm" style={{ marginLeft: 10 }} onClick={() => setModificaDurata({ valore: edizione.durata_effettiva_minuti || null })}>Modifica</button>
          )}
        </p>
        {modificaDurata && (
          <div className="card card-muted">
            <CampoDurata valore={modificaDurata.valore} id="edizione-durata" etichetta="Durata di questa sessione" onChange={(v) => setModificaDurata({ valore: v })}
              suggerimento={edizione.durata_corso_minuti ? `Il corso prevede ${formattaDurata(edizione.durata_corso_minuti)}: cambiando il valore forzi la durata solo di questa sessione.` : "Il corso non ha una durata: questo valore vale solo per questa sessione."} />
            <button type="button" onClick={() => salvaDurata(modificaDurata.valore)}>Salva</button>{" "}
            {edizione.durata_corso_minuti && <><button type="button" className="secondary" onClick={() => salvaDurata(edizione.durata_corso_minuti)}>Ripristina quella del corso</button>{" "}</>}
            <button type="button" className="secondary" onClick={() => setModificaDurata(null)}>Annulla</button>
          </div>
        )}
        {edizione.luogo && <p><strong>Luogo:</strong> {edizione.luogo}</p>}
        {isAdmin && edizione.stato !== "chiusa" && edizione.modalita === "video" && (
          <p>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={!!edizione.sempre_aperta}
                onChange={(ev) => salva({ sempre_aperta: ev.target.checked }, "Impossibile cambiare la disponibilità")} />
              <strong>Sempre disponibile (senza date)</strong>
            </label>
            <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>Chi vuole la guarda dal Catalogo; chi la completa riceve l'attestato in automatico. Attivandola si tolgono date e posti.</span>
          </p>
        )}
        {isAdmin && (
          <p>
            <strong>Catalogo:</strong>{" "}
            {edizione.in_catalogo ? <span className="badge green">visibile a tutti</span> : <span className="badge gray">non visibile</span>}
            {!edizione.in_catalogo && <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>
              {edizione.stato === "bozza" ? "La sessione è in bozza: pubblicala."
                : edizione.stato === "chiusa" || edizione.stato === "annullata" ? "La sessione è conclusa."
                : !edizione.corso_autoiscrizione_attiva && !edizione.sempre_aperta ? "Il corso non permette l'auto-iscrizione: attivala da Corsi → Modifica per aprirla a tutti (altrimenti si iscrive chi viene iscritto)."
                : "La sessione non è più aperta alle iscrizioni."}
            </span>}
          </p>
        )}
        {edizione.posti_max && (
          <p><strong>Posti:</strong> {edizione.n_iscritti}/{edizione.posti_max}
            {edizione.n_lista_attesa > 0 && <> — {edizione.n_lista_attesa} in lista d'attesa</>}</p>
        )}
        {(edizione.modalita === "presenza" || edizione.modalita === "ibrida") && (
          <p><strong>Check-in:</strong> {edizione.checkin_mode === "docente" ? "registro docente" : "self check-in + validazione docente"}</p>
        )}
      </div>

      {isAdmin && edizione.stato !== "chiusa" && (
        <p><button type="button" className="danger btn-sm" onClick={() => setEliminando(true)}>Elimina la sessione</button></p>
      )}
      {daSpostare && (
        <SpostaIscrizione nomePersona={daSpostare.user_full_name} titoloCorso={edizione.corso_titolo} corsoId={edizione.corso_id}
          edizioneId={id} iscrizioneId={daSpostare.id} onChiudi={() => setDaSpostare(null)} onSpostata={() => { setDaSpostare(null); load(); }} />
      )}
      {eliminando && <EliminaSessione sessioneId={id} nome={edizione.corso_titolo || "questo corso"} onChiudi={() => setEliminando(false)} onEliminata={() => navigate("/sessioni")} />}
      {isAdmin && edizione.da_chiudere && (
        <div className="card" style={{ borderColor: "var(--yellow)", background: "var(--yellow-bg)" }}>
          <h3>La sessione è finita</h3>
          <p style={{ margin: 0 }}>La data di fine è passata ma la sessione è ancora aperta: il sistema non la chiude da solo. Quando hai controllato tutto, chiudila: chi non ha completato risulterà non completato.</p>
        </div>
      )}
      {isAdmin && edizione.stato === "bozza" && (
        <div className="card" style={{ borderColor: "var(--yellow)", background: "var(--yellow-bg)" }}>
          <h3>La sessione è in bozza</h3>
          <p>Finché è in bozza nessuno la vede e non ci si può iscrivere (nemmeno dal Catalogo o dalle richieste di «Il mio team»). Quando è pronta, pubblicala.</p>
          <button type="button" onClick={() => tenta(async () => { await api.post(`/edizioni/${id}/pianifica`); setMsg("Sessione pubblicata: ora è disponibile."); load(); }, "Impossibile pubblicare la sessione")}>Pubblica</button>
        </div>
      )}
      {isAdmin && edizione.stato === "pianificata" && edizione.n_iscritti === 0 && edizione.n_lista_attesa === 0 && (
        <p><button type="button" className="secondary btn-sm" onClick={() => tenta(async () => { await api.post(`/edizioni/${id}/bozza`); setMsg("Sessione riportata in bozza: non è più visibile a nessuno."); load(); }, "Impossibile riportare in bozza")}>Riporta in bozza</button>
          <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>La ritira finché non è di nuovo pronta (possibile solo senza iscritti).</span></p>
      )}
      {edizione.sempre_aperta && <p className="text-muted">Sessione sempre disponibile: chi completa il video (e supera il test finale, se c'è) riceve l'attestato in automatico.</p>}

      <SezioneDocenti edizione={edizione} utenti={utenti} puoModificare={isAdmin && edizione.stato !== "chiusa"} ricarica={load} />

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

      {edizione.modalita === "video" && video && (puoGestire && !(miaIscrizione && segui) ? (
        // Chi gestisce la sessione non la sta seguendo: vede il video collegato e, se vuole, un'anteprima. Il player vero parte per chi segue il corso.
        <div className="card">
          <h3>Video collegato</h3>
          <p style={{ margin: "0 0 .5rem" }}>
            <strong>{video.titolo}</strong>{" "}
            <span className={`badge ${video.stato === "pronto" ? "green" : video.stato === "errore" ? "red" : "yellow"}`}>{video.stato}</span>
            {video.durata_secondi ? <span className="text-muted"> · durata {Math.floor(video.durata_secondi / 60)}:{String(video.durata_secondi % 60).padStart(2, "0")}</span> : null}
          </p>
          {video.stato === "pronto" && (
            <>
              <button type="button" className="secondary btn-sm" onClick={() => setAnteprimaVideo(!anteprimaVideo)}>{anteprimaVideo ? "Chiudi l'anteprima" : "Anteprima del video"}</button>
              {miaIscrizione && <>{" "}<button type="button" className="secondary btn-sm" onClick={() => navigate(`/sessioni/${id}?segui=1`)}>Segui il video come discente</button></>}
              {anteprimaVideo && (
                <div style={{ marginTop: 10 }}>
                  <VideoPlayer video={video} />
                  <p className="text-muted" style={{ fontSize: 12, margin: "6px 0 0" }}>Anteprima per chi gestisce la sessione: non conta come visione e non registra nessun avanzamento.</p>
                </div>
              )}
            </>
          )}
        </div>
      ) : video.stato === "pronto" && (
        <div className="card">
          <h3>Video</h3>
          {miaIscrizione ? <VideoPlayer video={video} iscrizioneId={miaIscrizione.id} onCompletato={() => { setMsg("Hai completato il corso: il tuo attestato è pronto, lo trovi nello storico dei corsi."); load(); }} /> : <p className="text-muted">Non sei iscritto a questa sessione.</p>}
        </div>
      ))}

      <div className="card">
        <h3>Discenti <span className="text-muted" style={{ fontSize: 13, fontWeight: 400 }}>({iscrizioni.filter((i) => i.stato !== "annullato").length}{edizione.posti_max ? ` su ${edizione.posti_max} posti` : ""})</span></h3>
        {isAdmin && edizione.stato !== "chiusa" && <AggiungiDiscenti edizione={edizione} utenti={utenti} iscrizioni={iscrizioni} ricarica={load} />}
      <div className="table-wrap" style={{ marginBottom: ".2rem" }}>
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
                    {isAdmin && edizione.stato !== "chiusa" && (i.stato === "iscritto" || i.stato === "in_lista_attesa") && (
                      <><button className="secondary btn-sm" onClick={() => setDaSpostare(i)}>Sposta</button>{" "}</>
                    )}
                    {puoAnnullare && <button className="danger btn-sm" onClick={() => annulla(i.id)}>Annulla</button>}
                  </td>
                </tr>
              );
            })}
            {iscrizioni.filter((i) => i.stato !== "annullato").length === 0 && <tr><td colSpan={4} className="text-muted">Nessun discente iscritto.</td></tr>}
          </tbody>
        </table>
      </div>
      </div>

      {miaIscrizione && (edizione.modalita === "presenza" || edizione.modalita === "ibrida") && edizione.checkin_mode === "discente_validato" && edizione.stato !== "chiusa" && (
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
