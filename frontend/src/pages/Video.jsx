import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import VideoPlayer from "../components/VideoPlayer";

const SCHEDE = [{ id: "elenco", label: "Elenco video" }, { id: "carica", label: "Carica video" }];
const STATO = { caricato: "gray", in_elaborazione: "yellow", pronto: "green", errore: "red" };

// secondi <-> «m:ss» o «h:mm:ss» (si accetta anche un numero di secondi scritto da solo)
function inTempo(sec) {
  const s = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}` : `${m}:${String(r).padStart(2, "0")}`;
}
function inSecondi(testo) {
  const t = String(testo ?? "").trim();
  if (!t) return null;
  if (/^\d+$/.test(t)) return parseInt(t, 10);
  const m = t.match(/^(?:(\d+):)?(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  return (parseInt(m[1] || "0", 10) * 3600) + parseInt(m[2], 10) * 60 + parseInt(m[3], 10);
}
const qualita = (v) => (v.qualita || []).map((h) => (h >= 2160 ? "4K" : `${h}p`)).join(", ") || "—";

function Pannello({ v, ricarica, chiudi, setErrore }) {
  const [titolo, setTitolo] = useState(v.titolo);
  const [anteprima, setAnteprima] = useState(false);
  const [modCap, setModCap] = useState(null);                        // { id, titolo, tempo }
  const [nuovoCap, setNuovoCap] = useState({ titolo: "", tempo: "" });
  const esegui = async (fn, errore) => { setErrore(null); try { await fn(); await ricarica(); return true; } catch (e) { setErrore(erroreDi(e, errore)); return false; } };
  const pronto = v.stato === "pronto";
  const elaborazione = v.stato === "caricato" || v.stato === "in_elaborazione" || !!v.altre_qualita_in_preparazione;   // finche' lavora, non si elimina

  async function salvaTitolo(e) {
    e.preventDefault();
    await esegui(() => api.put(`/video/${v.id}`, { titolo }), "Impossibile cambiare il titolo");
  }
  async function aggiungiCap(e) {
    e.preventDefault();
    const sec = inSecondi(nuovoCap.tempo);
    if (sec === null) { setErrore("Scrivi il tempo come minuti:secondi (per esempio 2:30)"); return; }
    if (await esegui(() => api.post(`/video/${v.id}/capitoli`, { titolo: nuovoCap.titolo, inizio_secondi: sec }), "Capitolo non aggiunto")) setNuovoCap({ titolo: "", tempo: "" });
  }
  async function salvaCap(e) {
    e.preventDefault();
    const sec = inSecondi(modCap.tempo);
    if (sec === null) { setErrore("Scrivi il tempo come minuti:secondi (per esempio 2:30)"); return; }
    if (await esegui(() => api.put(`/video/${v.id}/capitoli/${modCap.id}`, { titolo: modCap.titolo, inizio_secondi: sec }), "Capitolo non salvato")) setModCap(null);
  }
  async function caricaSottotitoli(f) {
    const fd = new FormData();
    fd.append("file", f);
    setAnteprima(false);
    await esegui(() => api.post(`/video/${v.id}/sottotitoli`, fd, { headers: { "Content-Type": "multipart/form-data" } }), "Sottotitoli non caricati");
  }
  async function eliminaVideo() {
    if (!window.confirm(`Eliminare il video «${v.titolo}»? I suoi file vengono cancellati e non si può annullare.`)) return;
    if (await esegui(() => api.delete(`/video/${v.id}`), "Video non eliminato")) chiudi();
  }

  return (
    <div style={{ padding: "10px 0" }}>
      <div className="row">
        <form className="field" onSubmit={salvaTitolo} style={{ flex: 2 }}>
          <label htmlFor={`vt-${v.id}`}>Titolo</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input id={`vt-${v.id}`} required value={titolo} onChange={(e) => setTitolo(e.target.value)} />
            <button type="submit" className="secondary" disabled={titolo.trim() === v.titolo}>Salva</button>
          </div>
        </form>
        <div className="field">
          <label>Informazioni</label>
          <div className="text-muted" style={{ fontSize: 13 }}>
            Durata {v.durata_secondi ? inTempo(v.durata_secondi) : "—"} · qualità {qualita(v)}
            {v.altre_qualita_in_preparazione && <> · <strong>altre qualità in preparazione</strong> (il video è già guardabile)</>}
            <br />Collegato a {v.usato_in} {v.usato_in === 1 ? "sessione" : "sessioni"}
          </div>
        </div>
      </div>

      {pronto && (
        <>
          <div className="field">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={!!v.blocca_skip_avanti} onChange={() => esegui(() => api.put(`/video/${v.id}`, { blocca_skip_avanti: !v.blocca_skip_avanti }), "Impostazione non salvata")} />
              Blocca avanzamento oltre il punto raggiunto (anti-skip)
            </label>
          </div>
          <div className="field">
            <button type="button" className="secondary btn-sm" onClick={() => setAnteprima(!anteprima)}>{anteprima ? "Chiudi l'anteprima" : "Anteprima del video"}</button>
            {anteprima && (
              <div style={{ marginTop: 8 }}>
                <VideoPlayer video={v} />
                <p className="text-muted" style={{ fontSize: 12, margin: "6px 0 0" }}>Anteprima: non conta come visione e non registra nessun avanzamento.</p>
              </div>
            )}
          </div>

          <div className="field">
            <label>Sottotitoli (.vtt)</label>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              {v.ha_sottotitoli ? <span className="badge green">caricati</span> : <span className="badge gray">nessuno</span>}
              <input type="file" accept=".vtt" aria-label="Carica o sostituisci i sottotitoli" style={{ width: "auto" }} onChange={(e) => { if (e.target.files[0]) { caricaSottotitoli(e.target.files[0]); e.target.value = ""; } }} />
              {v.ha_sottotitoli && <button type="button" className="danger btn-sm" onClick={() => window.confirm("Togliere i sottotitoli?") && esegui(() => api.delete(`/video/${v.id}/sottotitoli`), "Sottotitoli non eliminati")}>Elimina i sottotitoli</button>}
            </div>
          </div>

          <div className="field">
            <label>Capitoli</label>
            <div className="table-wrap">
              <table>
                <thead><tr><th style={{ width: 110 }}>Inizio</th><th>Titolo</th><th style={{ width: 190 }}></th></tr></thead>
                <tbody>
                  {v.capitoli.map((c) => (
                    <tr key={c.id}>
                      {modCap?.id === c.id ? (
                        <>
                          <td><input aria-label="Inizio (minuti:secondi)" value={modCap.tempo} onChange={(e) => setModCap({ ...modCap, tempo: e.target.value })} /></td>
                          <td><input aria-label="Titolo del capitolo" required autoFocus value={modCap.titolo} onChange={(e) => setModCap({ ...modCap, titolo: e.target.value })} /></td>
                          <td>
                            <button type="button" className="btn-sm" onClick={salvaCap}>Salva</button>{" "}
                            <button type="button" className="secondary btn-sm" onClick={() => setModCap(null)}>Annulla</button>
                          </td>
                        </>
                      ) : (
                        <>
                          <td>{inTempo(c.inizio_secondi)}</td>
                          <td>{c.titolo}</td>
                          <td style={{ whiteSpace: "nowrap" }}>
                            <button type="button" className="secondary btn-sm" onClick={() => setModCap({ id: c.id, titolo: c.titolo, tempo: inTempo(c.inizio_secondi) })}>Modifica</button>{" "}
                            <button type="button" className="danger btn-sm" onClick={() => esegui(() => api.delete(`/video/${v.id}/capitoli/${c.id}`), "Capitolo non eliminato")}>Elimina</button>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                  {v.capitoli.length === 0 && <tr><td colSpan={3} className="text-muted">Nessun capitolo.</td></tr>}
                </tbody>
              </table>
            </div>
            <form onSubmit={aggiungiCap} style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <input aria-label="Inizio del nuovo capitolo (minuti:secondi)" placeholder="m:ss (es. 2:30)" required style={{ width: 130 }} value={nuovoCap.tempo} onChange={(e) => setNuovoCap({ ...nuovoCap, tempo: e.target.value })} />
              <input aria-label="Titolo del nuovo capitolo" placeholder="Titolo del capitolo" required style={{ flex: 1, minWidth: 200 }} value={nuovoCap.titolo} onChange={(e) => setNuovoCap({ ...nuovoCap, titolo: e.target.value })} />
              <button type="submit" className="secondary">Aggiungi capitolo</button>
            </form>
          </div>
        </>
      )}
      {!pronto && <p className="text-muted" style={{ fontSize: 13 }}>Il video non è ancora pronto: sottotitoli e capitoli si gestiscono quando l'elaborazione è finita.</p>}

      <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
        <button type="button" className="danger btn-sm" disabled={v.usato_in > 0 || elaborazione} onClick={eliminaVideo}>Elimina il video</button>
        {v.usato_in > 0 && <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>Non si può eliminare finché è collegato a delle sessioni.</span>}
        {v.usato_in === 0 && elaborazione && <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>Non si può eliminare mentre il video è in elaborazione.</span>}
        {" "}<button type="button" className="secondary btn-sm" onClick={chiudi}>Chiudi</button>
      </div>
    </div>
  );
}

export default function Video() {
  const [scheda, setScheda] = useState("elenco");
  const [list, setList] = useState([]);
  const [titolo, setTitolo] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [aperto, setAperto] = useState(null);       // id del video con il pannello aperto
  const [errore, setErrore] = useState(null);

  const carica = () => api.get("/video").then((r) => setList(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i video")));
  useEffect(() => {
    carica();
    const interval = setInterval(carica, 4000); // aggiorna lo stato della transcodifica
    return () => clearInterval(interval);
  }, []);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    setUploading(true); setErrore(null);
    const fd = new FormData();
    fd.append("titolo", titolo);
    fd.append("file", file);
    try { await api.post("/video", fd, { headers: { "Content-Type": "multipart/form-data" } }); }
    catch (err) { setErrore(erroreDi(err, "Caricamento non riuscito")); setUploading(false); return; }
    setTitolo(""); setFile(null); setUploading(false);
    await carica();
    setScheda("elenco");
  }

  return (
    <div>
      <div className="page-header">
        <div><h2>Video</h2><p>Contenuti video caricati sulla piattaforma, normalizzati automaticamente per lo streaming.</p></div>
      </div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      {scheda === "carica" && (
        <div className="card">
          <h3>Carica video</h3>
          <form onSubmit={upload}>
            <div className="field"><label htmlFor="v-titolo">Titolo</label><input id="v-titolo" required value={titolo} onChange={(e) => setTitolo(e.target.value)} /></div>
            <div className="field"><label htmlFor="v-file">File</label><input id="v-file" required type="file" accept="video/*" onChange={(e) => setFile(e.target.files[0])} /></div>
            <p className="text-muted" style={{ fontSize: 13 }}>Dopo il caricamento il video viene elaborato (qualità multiple, cifratura): lo vedi nell'elenco con lo stato aggiornato. Sottotitoli e capitoli si aggiungono dall'elenco, aprendo il video.</p>
            <button type="submit" disabled={uploading}>{uploading ? "Caricamento..." : "Carica"}</button>
          </form>
        </div>
      )}
      {scheda === "elenco" && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Titolo</th><th>Stato</th><th>Durata</th><th>Qualità</th><th>Sottotitoli</th><th>Capitoli</th><th>Anti-skip</th><th>Sessioni</th><th></th></tr></thead>
            <tbody>
              {list.map((v) => (
                <React.Fragment key={v.id}>
                  <tr>
                    <td>{v.titolo}</td>
                    <td><span className={`badge ${STATO[v.stato] || "gray"}`}>{v.stato.replace("_", " ")}</span></td>
                    <td>{v.durata_secondi ? inTempo(v.durata_secondi) : "—"}</td>
                    <td>{qualita(v)}{v.altre_qualita_in_preparazione && <span className="text-muted" style={{ fontSize: 11 }}> (+ in preparazione)</span>}</td>
                    <td>{v.ha_sottotitoli ? <span className="badge green">sì</span> : <span className="text-muted">no</span>}</td>
                    <td>{v.capitoli.length || <span className="text-muted">0</span>}</td>
                    <td>{v.blocca_skip_avanti ? "sì" : <span className="text-muted">no</span>}</td>
                    <td>{v.usato_in}</td>
                    <td style={{ whiteSpace: "nowrap" }}><button type="button" className={aperto === v.id ? "secondary btn-sm" : "btn-sm"} onClick={() => { setErrore(null); setAperto(aperto === v.id ? null : v.id); }}>{aperto === v.id ? "Chiudi" : "Apri"}</button></td>
                  </tr>
                  {aperto === v.id && (
                    <tr>
                      <td colSpan={9} style={{ background: "var(--bg3)" }}>
                        <Pannello v={v} ricarica={carica} chiudi={() => setAperto(null)} setErrore={setErrore} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {list.length === 0 && <tr><td colSpan={9} className="text-muted">Nessun video ancora: caricane uno dalla scheda «Carica video».</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
