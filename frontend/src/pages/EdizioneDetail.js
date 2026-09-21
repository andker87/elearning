import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api";
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
  const user = JSON.parse(localStorage.getItem("user") || "null");

  function load() {
    api.get(`/edizioni/${id}`).then((r) => {
      setEdizione(r.data);
      if (r.data.video_id) api.get(`/video/${r.data.video_id}`).then((rv) => setVideo(rv.data));
      api.get(`/corsi/${r.data.corso_id}/test`).then((rt) => setTests(rt.data));
    });
    api.get(`/edizioni/${id}/iscrizioni`).then((r) => setIscrizioni(r.data));
  }
  useEffect(() => { load(); api.get("/auth/users/simple").then((r) => setUtenti(r.data)); }, [id]);

  const isDocente = edizione?.docenti?.some((d) => d.user_id === user?.id);
  const isAdmin = user?.role === "admin_tecnico" || user?.role === "training_admin";
  const nome = (uid) => utenti.find((u) => u.id === uid)?.full_name || uid;
  const miaIscrizione = iscrizioni.find((i) => i.user_id === user?.id);

  async function assegnaDocente() {
    if (!selectedUser) return;
    await api.post(`/edizioni/${id}/docenti`, { user_id: selectedUser, ruolo: "titolare" });
    setSelectedUser(""); load();
  }
  async function iscrivi() {
    if (!selectedUser) return;
    await api.post(`/edizioni/${id}/iscrizioni`, [selectedUser]);
    setSelectedUser(""); load();
  }
  async function checkinDiscente(momento) {
    await api.post(`/edizioni/${id}/checkin/discente`, { momento });
    setMsg(`Check-in ${momento} registrato`);
  }
  async function checkinDocentePresente(uid) {
    await api.post(`/edizioni/${id}/checkin/docente`, [{ user_id: uid, presente: true }]);
    load();
  }
  async function linkTeams() {
    await api.post(`/edizioni/${id}/teams/link`, { join_url: teamsUrl });
    load();
  }
  async function creaRiunioneAuto() {
    try {
      await api.post(`/edizioni/${id}/teams/crea-riunione`);
      load();
    } catch (e) { setMsg(e.response?.data?.detail || "Errore"); }
  }
  async function sincronizzaPresenze() {
    try {
      const r = await api.post(`/edizioni/${id}/teams/sincronizza-presenze`);
      setMsg(`Presenze sincronizzate: ${r.data.applicati.length}`);
    } catch (e) { setMsg(e.response?.data?.detail || "Errore — usa il report manuale"); }
  }
  async function chiudi() {
    if (!window.confirm("Chiudere la sessione? Le evidenze diventeranno definitive e verranno generati i certificati.")) return;
    const r = await api.post(`/edizioni/${id}/chiudi`);
    setMsg(`Sessione chiusa. Completati: ${r.data.esiti.filter((x) => x.completato).length}/${r.data.esiti.length}`);
    load();
  }

  if (!edizione) return <div>Caricamento...</div>;

  return (
    <div>
      <div className="page-header">
        <div><h2>Sessione — {edizione.modalita}</h2></div>
        {isAdmin && (
          <div>
            <a className="btn secondary" href={`/api/edizioni/${id}/report/iscrizioni.csv`} target="_blank" rel="noreferrer">Report iscrizioni CSV</a>{" "}
            <a className="btn secondary" href={`/api/edizioni/${id}/report/gradimenti.csv`} target="_blank" rel="noreferrer">Report gradimenti CSV</a>
          </div>
        )}
      </div>
      {msg && <div className="card card-muted">{msg}</div>}

      <div className="card">
        <p><strong>Stato:</strong> <span className="badge gray">{edizione.stato}</span></p>
        <p><strong>Data:</strong> {edizione.data_inizio ? new Date(edizione.data_inizio).toLocaleString("it-IT") : "-"}</p>
        {edizione.luogo && <p><strong>Luogo:</strong> {edizione.luogo}</p>}
        {(edizione.modalita === "presenza" || edizione.modalita === "ibrida") && (
          <p><strong>Check-in:</strong> {edizione.checkin_mode === "docente" ? "registro docente" : "self check-in + validazione docente"}</p>
        )}
      </div>

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
            {iscrizioni.map((i) => (
              <tr key={i.id}>
                <td>{i.user_full_name}</td>
                <td><span className={`badge ${i.stato === "completato" ? "green" : i.stato === "non_completato" ? "red" : "gray"}`}>{i.stato}</span></td>
                <td>{i.n_evidenze}</td>
                <td>
                  {isDocente && edizione.checkin_mode === "docente" && edizione.stato !== "chiusa" && (
                    <button className="secondary btn-sm" onClick={() => checkinDocentePresente(i.user_id)}>Segna presente</button>
                  )}
                </td>
              </tr>
            ))}
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

      {miaIscrizione && miaIscrizione.stato === "completato" && <Gradimento iscrizioneId={miaIscrizione.id} />}

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
