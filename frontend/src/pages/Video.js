import React, { useEffect, useState } from "react";
import api from "../api";

export default function Video() {
  const [list, setList] = useState([]);
  const [titolo, setTitolo] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [capForm, setCapForm] = useState({});

  function load() { api.get("/video").then((r) => setList(r.data)); }
  useEffect(() => {
    load();
    const interval = setInterval(load, 4000); // aggiorna stato transcodifica
    return () => clearInterval(interval);
  }, []);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("titolo", titolo);
    fd.append("file", file);
    await api.post("/video", fd, { headers: { "Content-Type": "multipart/form-data" } });
    setTitolo(""); setFile(null); setUploading(false);
    load();
  }

  async function addCapitolo(videoId) {
    const c = capForm[videoId];
    if (!c || !c.titolo || c.inizio_secondi === undefined) return;
    await api.post(`/video/${videoId}/capitoli`, { titolo: c.titolo, inizio_secondi: parseInt(c.inizio_secondi) });
    setCapForm({ ...capForm, [videoId]: { titolo: "", inizio_secondi: "" } });
    load();
  }

  async function uploadSottotitoli(videoId, f) {
    const fd = new FormData();
    fd.append("file", f);
    await api.post(`/video/${videoId}/sottotitoli`, fd, { headers: { "Content-Type": "multipart/form-data" } });
    load();
  }

  async function toggleSkip(v) {
    await api.put(`/video/${v.id}`, { blocca_skip_avanti: !v.blocca_skip_avanti });
    load();
  }

  const statoBadge = { caricato: "gray", in_elaborazione: "yellow", pronto: "green", errore: "red" };

  return (
    <div>
      <div className="page-header">
        <div><h2>Video</h2><p>Contenuti video caricati sulla piattaforma, normalizzati automaticamente per lo streaming.</p></div>
      </div>
      <div className="card">
        <h3>Carica video</h3>
        <form onSubmit={upload}>
          <div className="field"><label>Titolo</label><input required value={titolo} onChange={(e) => setTitolo(e.target.value)} /></div>
          <div className="field"><label>File</label><input required type="file" accept="video/*" onChange={(e) => setFile(e.target.files[0])} /></div>
          <button type="submit" disabled={uploading}>{uploading ? "Caricamento..." : "Carica"}</button>
        </form>
      </div>

      {list.map((v) => (
        <div className="card" key={v.id}>
          <div className="flex-between">
            <h3>{v.titolo}</h3>
            <span className={`badge ${statoBadge[v.stato]}`}>{v.stato}</span>
          </div>
          {v.durata_secondi && <p className="text-muted">Durata: {Math.floor(v.durata_secondi / 60)}:{String(v.durata_secondi % 60).padStart(2, "0")}</p>}
          {v.qualita?.length > 0 && (
            <p className="text-muted" style={{ fontSize: 13 }}>
              Qualità disponibili: {v.qualita.map((h) => (h >= 2160 ? "4K" : `${h}p`)).join(", ")}
              {v.altre_qualita_in_preparazione && <> · <strong>altre qualità in preparazione</strong> (il video è già guardabile)</>}
            </p>
          )}
          {v.stato === "pronto" && (
            <>
              <label style={{ display: "flex", alignItems: "center", gap: 8, width: "auto" }}>
                <input type="checkbox" style={{ width: "auto" }} checked={v.blocca_skip_avanti} onChange={() => toggleSkip(v)} />
                Blocca avanzamento oltre il punto raggiunto (anti-skip)
              </label>
              <div className="field" style={{ marginTop: 10 }}>
                <label>Carica sottotitoli (.vtt)</label>
                <input type="file" accept=".vtt" onChange={(e) => e.target.files[0] && uploadSottotitoli(v.id, e.target.files[0])} />
                {v.ha_sottotitoli && <span className="badge green" style={{ marginTop: 6 }}>caricati</span>}
              </div>
              <div style={{ marginTop: 10 }}>
                <label>Capitoli</label>
                <ul>{v.capitoli.map((c) => <li key={c.id}>{Math.floor(c.inizio_secondi / 60)}:{String(c.inizio_secondi % 60).padStart(2, "0")} — {c.titolo}</li>)}</ul>
                <div className="row">
                  <div className="field"><input placeholder="Titolo capitolo" value={capForm[v.id]?.titolo || ""} onChange={(e) => setCapForm({ ...capForm, [v.id]: { ...capForm[v.id], titolo: e.target.value } })} /></div>
                  <div className="field" style={{ maxWidth: 120 }}><input type="number" placeholder="secondi" value={capForm[v.id]?.inizio_secondi || ""} onChange={(e) => setCapForm({ ...capForm, [v.id]: { ...capForm[v.id], inizio_secondi: e.target.value } })} /></div>
                  <button type="button" className="secondary btn-sm" onClick={() => addCapitolo(v.id)}>+ Aggiungi</button>
                </div>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
