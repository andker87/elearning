import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

export default function Edizioni() {
  const [list, setList] = useState([]);
  const [corsi, setCorsi] = useState([]);
  const [video, setVideo] = useState([]);
  const [form, setForm] = useState({ corso_id: "", modalita: "presenza", checkin_mode: "discente_validato", luogo: "", data_inizio: "", data_fine: "", video_id: "" });

  function load() { api.get("/edizioni").then((r) => setList(r.data)); }
  useEffect(() => { load(); api.get("/corsi").then((r) => setCorsi(r.data)); api.get("/video").then((r) => setVideo(r.data.filter((v) => v.stato === "pronto"))); }, []);

  async function submit(e) {
    e.preventDefault();
    const payload = { ...form, data_inizio: form.data_inizio || null, data_fine: form.data_fine || null };
    await api.post("/edizioni", payload);
    setForm({ corso_id: "", modalita: "presenza", checkin_mode: "discente_validato", luogo: "", data_inizio: "", data_fine: "", video_id: "" });
    load();
  }

  const corsoTitolo = (id) => corsi.find((c) => c.id === id)?.titolo || id;

  return (
    <div>
      <div className="page-header"><div><h2>Sessioni</h2></div></div>
      <div className="card">
        <h3>Nuova sessione</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field">
              <label>Corso</label>
              <select required value={form.corso_id} onChange={(e) => setForm({ ...form, corso_id: e.target.value })}>
                <option value="">-- seleziona --</option>
                {corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Modalità</label>
              <select value={form.modalita} onChange={(e) => setForm({ ...form, modalita: e.target.value })}>
                <option value="presenza">Presenza</option>
                <option value="ibrida">Ibrida</option>
                <option value="remoto">Full-remote</option>
                <option value="video">Video</option>
                <option value="esterna">Esterna (ente accreditato)</option>
              </select>
            </div>
          </div>
          {(form.modalita === "presenza" || form.modalita === "ibrida") && (
            <div className="row">
              <div className="field">
                <label>Modalità check-in (parte in sede)</label>
                <select value={form.checkin_mode} onChange={(e) => setForm({ ...form, checkin_mode: e.target.value })}>
                  <option value="discente_validato">Check-in discente + validazione docente</option>
                  <option value="docente">Check-in docente (registro digitale)</option>
                </select>
              </div>
              <div className="field"><label>Luogo</label><input value={form.luogo} onChange={(e) => setForm({ ...form, luogo: e.target.value })} /></div>
            </div>
          )}
          {form.modalita === "video" && (
            <div className="field">
              <label>Contenuto video</label>
              <select required value={form.video_id} onChange={(e) => setForm({ ...form, video_id: e.target.value })}>
                <option value="">-- seleziona --</option>
                {video.map((v) => <option key={v.id} value={v.id}>{v.titolo}</option>)}
              </select>
              {video.length === 0 && <p className="text-muted" style={{ fontSize: 12 }}>Nessun video pronto — caricane uno nella sezione Video.</p>}
            </div>
          )}
          <div className="row">
            <div className="field"><label>Data/ora inizio</label><input type="datetime-local" value={form.data_inizio} onChange={(e) => setForm({ ...form, data_inizio: e.target.value })} /></div>
            <div className="field"><label>Data/ora fine</label><input type="datetime-local" value={form.data_fine} onChange={(e) => setForm({ ...form, data_fine: e.target.value })} /></div>
          </div>
          <button type="submit">Crea sessione</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Modalità</th><th>Data</th><th>Iscritti</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((e) => (
              <tr key={e.id}>
                <td>{corsoTitolo(e.corso_id)}</td>
                <td>{e.modalita}</td>
                <td>{e.data_inizio ? new Date(e.data_inizio).toLocaleString("it-IT") : "-"}</td>
                <td>{e.n_iscritti}</td>
                <td><span className="badge gray">{e.stato}</span></td>
                <td><Link to={`/sessioni/${e.id}`}>Apri</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
