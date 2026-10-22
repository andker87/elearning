import React, { useEffect, useState, useRef, useMemo } from "react";
import api, { downloadFile, erroreDi } from "../api";

const CANVAS_WIDTH = 640;

function nuovoCampo(chiave) {
  return { chiave, x: 50, y: 50, font_size: 16, bold: false, align: "left", colore: "#1a1a1a" };
}

export default function TemplateAttestati() {
  const [templates, setTemplates] = useState([]);
  const [campiDisponibili, setCampiDisponibili] = useState([]);
  const [selezionato, setSelezionato] = useState(null); // template completo in editing
  const [nuovoNome, setNuovoNome] = useState("");
  const [drag, setDrag] = useState(null); // { idx, startX, startY, origX, origY }
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);
  const fileRef = useRef(null);

  function carica() {
    api.get("/certificato-templates").then((r) => setTemplates(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i template")));
  }
  useEffect(() => {
    carica();
    api.get("/certificato-templates/campi-disponibili").then((r) => setCampiDisponibili(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i campi disponibili")));
  }, []);

  // L'immagine di sfondo e' protetta: si scarica con il token e si mostra da un indirizzo locale.
  const [sfondoUrl, setSfondoUrl] = useState(null);
  const immagineUrl = selezionato && selezionato.immagine_url;
  const idSelezionato = selezionato && selezionato.id;
  useEffect(() => {
    let attivo = true, locale = null;
    setSfondoUrl(null);
    if (immagineUrl) {
      api.get(immagineUrl, { responseType: "blob" }).then((r) => {
        locale = window.URL.createObjectURL(r.data);
        if (attivo) setSfondoUrl(locale); else window.URL.revokeObjectURL(locale);
      }).catch(() => {});
    }
    return () => { attivo = false; if (locale) window.URL.revokeObjectURL(locale); };
  }, [immagineUrl, idSelezionato]);

  function apri(t) {
    setSelezionato({ ...t, campi: (t.campi || []).map((c) => ({ ...c })) });
    setMsg(null); setErrore(null);
  }

  async function creaTemplate(e) {
    e.preventDefault();
    if (!nuovoNome.trim()) return;
    setErrore(null);
    try {
      const r = await api.post("/certificato-templates", { nome: nuovoNome.trim() });
      setNuovoNome("");
      carica();
      apri(r.data);
    } catch (err) { setErrore(erroreDi(err, "Creazione non riuscita")); }
  }

  async function eliminaTemplate(id) {
    try {
      await api.delete(`/certificato-templates/${id}`);
      if (selezionato?.id === id) setSelezionato(null);
      carica();
    } catch (err) {
      setErrore(erroreDi(err, "Errore nell'eliminazione"));
    }
  }

  async function caricaImmagine(e) {
    const file = e.target.files[0];
    if (!file) return;
    setErrore(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post(`/certificato-templates/${selezionato.id}/immagine`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setSelezionato({ ...r.data, campi: (r.data.campi || []).map((c) => ({ ...c })) });
      carica();
    } catch (err) {
      setErrore(erroreDi(err, "Errore nel caricamento"));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const scala = selezionato?.larghezza_px ? Math.min(CANVAS_WIDTH, selezionato.larghezza_px) / selezionato.larghezza_px : 1;
  const canvasW = selezionato?.larghezza_px ? Math.min(CANVAS_WIDTH, selezionato.larghezza_px) : 0;
  const canvasH = selezionato?.altezza_px ? selezionato.altezza_px * scala : 0;

  const chiaviUsate = useMemo(() => new Set((selezionato?.campi || []).map((c) => c.chiave)), [selezionato]);
  const disponibiliNonUsati = campiDisponibili.filter((c) => !chiaviUsate.has(c.chiave));

  function aggiungiCampo(chiave) {
    setSelezionato((s) => ({ ...s, campi: [...s.campi, nuovoCampo(chiave)] }));
  }
  function rimuoviCampo(idx) {
    setSelezionato((s) => ({ ...s, campi: s.campi.filter((_, i) => i !== idx) }));
  }
  function aggiornaCampo(idx, patch) {
    // forma funzionale: durante il trascinamento la funzione e' quella di un render vecchio, e non deve riportare indietro i campi
    setSelezionato((s) => ({ ...s, campi: s.campi.map((c, i) => (i === idx ? { ...c, ...patch } : c)) }));
  }

  function onMouseDownCampo(e, idx) {
    e.preventDefault();
    e.stopPropagation();
    const c = selezionato.campi[idx];
    setDrag({ idx, startX: e.clientX, startY: e.clientY, origX: c.x, origY: c.y });
  }
  useEffect(() => {
    if (!drag) return;
    function onMove(e) {
      const dx = (e.clientX - drag.startX) / scala;
      const dy = (e.clientY - drag.startY) / scala;
      const nx = Math.max(0, Math.round(drag.origX + dx));
      const ny = Math.max(0, Math.round(drag.origY + dy));
      aggiornaCampo(drag.idx, { x: nx, y: ny });
    }
    function onUp() { setDrag(null); }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [drag, scala]); // eslint-disable-line

  async function salva() {
    setErrore(null);
    try {
      const r = await api.put(`/certificato-templates/${selezionato.id}`, { nome: selezionato.nome, campi: selezionato.campi });
      setSelezionato({ ...r.data, campi: (r.data.campi || []).map((c) => ({ ...c })) });
      carica();
      setMsg("Salvato.");
      setTimeout(() => setMsg(null), 2000);
    } catch (err) { setErrore(erroreDi(err, "Salvataggio non riuscito")); }
  }

  async function impostaPredefinito() {
    setErrore(null);
    try {
      const r = await api.put(`/certificato-templates/${selezionato.id}`, { is_default: !selezionato.is_default });
      setSelezionato((s) => ({ ...s, is_default: r.data.is_default }));  // i campi in modifica non si toccano
      carica();
    } catch (err) { setErrore(erroreDi(err, "Operazione non riuscita")); }
  }

  function anteprimaPdf() {
    setErrore(null);
    downloadFile(`/certificato-templates/${selezionato.id}/anteprima.pdf`, "anteprima_attestato.pdf")
      .catch(() => setErrore("Impossibile generare l'anteprima: salva prima i campi e controlla lo sfondo"));
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Modelli di attestato</h2>
          <p>Carica uno sfondo grafico e posiziona i campi (nome, corso, data, ore...) con il mouse — stile stampa unione.</p>
        </div>
      </div>

      {errore && <div className="error-msg">{errore}</div>}
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div style={{ width: 240, flex: "none" }}>
          <div className="card">
            <h3>Template</h3>
            {templates.map((t) => (
              <div key={t.id} className={`tpl-lista-item ${selezionato?.id === t.id ? "active" : ""}`} onClick={() => apri(t)}>
                <div className="flex-between">
                  <span>{t.nome}{t.is_default && <span className="badge green" style={{ marginLeft: 6 }}>default</span>}</span>
                  <span style={{ cursor: "pointer", color: "#b02a2a" }} onClick={(e) => { e.stopPropagation(); eliminaTemplate(t.id); }}>✕</span>
                </div>
              </div>
            ))}
            {templates.length === 0 && <p className="text-muted" style={{ fontSize: 13 }}>Nessun template ancora.</p>}
            <form onSubmit={creaTemplate} style={{ marginTop: 10 }}>
              <input placeholder="Nome nuovo template" value={nuovoNome} onChange={(e) => setNuovoNome(e.target.value)} />
              <button type="submit" style={{ marginTop: 6, width: "100%" }}>Nuovo template</button>
            </form>
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {!selezionato && <div className="card card-muted">Seleziona o crea un template per iniziare.</div>}
          {selezionato && (
            <div className="card">
              <div className="flex-between">
                <input style={{ fontWeight: 600, fontSize: "1.05rem", border: "none", background: "transparent" }}
                       value={selezionato.nome} onChange={(e) => setSelezionato({ ...selezionato, nome: e.target.value })} />
                <div>
                  <button type="button" className={selezionato.is_default ? "" : "secondary"} onClick={impostaPredefinito}>
                    {selezionato.is_default ? "★ Predefinito" : "Imposta come predefinito"}
                  </button>{" "}
                  {selezionato.immagine_url && <button type="button" className="secondary" onClick={anteprimaPdf}>Anteprima PDF</button>}{" "}
                  <button type="button" onClick={salva}>Salva</button>
                </div>
              </div>
              {msg && <p style={{ color: "#1a7a3e" }}>{msg}</p>}

              {!selezionato.immagine_url && (
                <div style={{ marginTop: 14 }}>
                  <p className="text-muted" style={{ fontSize: 13 }}>Carica l'immagine di sfondo (PNG, JPG o WEBP) per iniziare a posizionare i campi.</p>
                  <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={caricaImmagine} />
                </div>
              )}

              {selezionato.immagine_url && (
                <div className="row" style={{ marginTop: 14, alignItems: "flex-start" }}>
                  <div
                    className="tpl-canvas-wrap"
                    style={{ width: canvasW, height: canvasH }}
                  >
                    <img src={sfondoUrl || undefined} alt="sfondo" className="tpl-canvas-img" style={{ width: canvasW, height: canvasH }} />
                    {selezionato.campi.map((c, idx) => {
                      const label = campiDisponibili.find((d) => d.chiave === c.chiave)?.etichetta || c.chiave;
                      const fontPx = Math.max(9, Math.round((c.font_size || 14) * scala));
                      return (
                        <div
                          key={c.chiave}
                          className="tpl-campo"
                          style={{
                            left: c.x * scala, top: Math.max(0, c.y * scala - fontPx),
                            fontSize: fontPx, fontWeight: c.bold ? 700 : 400, color: c.colore,
                            textAlign: c.align, borderColor: c.colore,
                          }}
                          onMouseDown={(e) => onMouseDownCampo(e, idx)}
                        >
                          {label}
                        </div>
                      );
                    })}
                  </div>

                  <div style={{ flex: 1, minWidth: 260 }}>
                    <h4>Aggiungi campo</h4>
                    <div style={{ marginBottom: 10 }}>
                      {disponibiliNonUsati.map((c) => (
                        <span key={c.chiave} className="tpl-palette-item" onClick={() => aggiungiCampo(c.chiave)}>+ {c.etichetta}</span>
                      ))}
                      {disponibiliNonUsati.length === 0 && <span className="text-muted" style={{ fontSize: 12 }}>Tutti i campi sono già posizionati.</span>}
                    </div>

                    <h4>Campi posizionati</h4>
                    {selezionato.campi.map((c, idx) => {
                      const label = campiDisponibili.find((d) => d.chiave === c.chiave)?.etichetta || c.chiave;
                      return (
                        <div key={c.chiave} className="card-muted" style={{ padding: 10, marginBottom: 8, borderRadius: 6 }}>
                          <div className="flex-between"><strong style={{ fontSize: 13 }}>{label}</strong>
                            <span style={{ cursor: "pointer", color: "#b02a2a", fontSize: 12 }} onClick={() => rimuoviCampo(idx)}>Rimuovi</span>
                          </div>
                          <div className="row" style={{ marginTop: 6 }}>
                            <div className="field"><label style={{ fontSize: 11 }}>Dimensione</label>
                              <input type="number" min={6} max={72} value={c.font_size}
                                     onChange={(e) => aggiornaCampo(idx, { font_size: parseInt(e.target.value, 10) || 14 })} />
                            </div>
                            <div className="field"><label style={{ fontSize: 11 }}>Allineamento</label>
                              <select value={c.align} onChange={(e) => aggiornaCampo(idx, { align: e.target.value })}>
                                <option value="left">Sinistra</option>
                                <option value="center">Centro</option>
                                <option value="right">Destra</option>
                              </select>
                            </div>
                          </div>
                          <div className="row" style={{ marginTop: 6 }}>
                            <div className="field"><label style={{ fontSize: 11 }}>Colore</label>
                              <input type="color" value={c.colore} onChange={(e) => aggiornaCampo(idx, { colore: e.target.value })} />
                            </div>
                            <div className="field">
                              <label style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 6 }}>
                                <input type="checkbox" style={{ width: "auto" }} checked={!!c.bold} onChange={(e) => aggiornaCampo(idx, { bold: e.target.checked })} />
                                Grassetto
                              </label>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    {selezionato.campi.length === 0 && <p className="text-muted" style={{ fontSize: 12 }}>Nessun campo posizionato: aggiungine uno dalla lista sopra, poi trascinalo sull'immagine.</p>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
