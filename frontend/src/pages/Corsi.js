import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { erroreDi } from "../api";
import { useFamiglie, SceltaEtichette, ChipEtichette, FiltroEtichette } from "../components/Etichette";
import ExportButton from "../components/ExportButton";

const AZIONI = [
  { value: "concludi_comunque", label: "Concludi comunque" },
  { value: "concludi_scadenza_breve", label: "Concludi, ma ripeti entro N giorni" },
  { value: "rifai_test", label: "Rifai solo il test" },
  { value: "rifai_corso", label: "Rifai il corso da zero" },
];

export default function Corsi() {
  const [list, setList] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState({
    titolo: "", descrizione: "", categoria: "", validita_mesi: "",
    ha_test_finale: false, azione_test_non_superato: "concludi_comunque", giorni_scadenza_breve: "",
    confronta_pre_post_test: false, permetti_autoiscrizione: false, richiedi_approvazione_responsabile: false,
    rinnovo_automatico: false, rinnovo_giorni_anticipo: 30, etichette: [],
  });
  const famiglie = useFamiglie();
  const [filtroEtichette, setFiltroEtichette] = useState([]);
  const [etichetteAperte, setEtichetteAperte] = useState(null);   // { id, valore }
  const [anteprimaId, setAnteprimaId] = useState(null);
  const [anteprima, setAnteprima] = useState(null);
  const [errore, setErrore] = useState(null);
  const [versioneApertaId, setVersioneApertaId] = useState(null);
  const [versioneForm, setVersioneForm] = useState({ richiedi_ripetizione: false, nota: "" });
  const [versioneMsg, setVersioneMsg] = useState(null);

  function load() { api.get("/corsi").then((r) => setList(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i corsi"))); }
  useEffect(load, []);
  useEffect(() => { api.get("/certificato-templates").then((r) => setTemplates(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i template degli attestati"))); }, []);

  // Il PUT riceve le etichette solo quando si cambiano davvero: negli altri casi non si toccano.
  const corpo = (c, campi) => { const { etichette, etichette_mancanti, avvisi_etichette, ...resto } = c; return { ...resto, ...campi }; };
  async function salvaEtichette(c) {
    setErrore(null);
    try { await api.put(`/corsi/${c.id}`, corpo(c, { etichette: etichetteAperte.valore })); setEtichetteAperte(null); load(); }
    catch (err) { setErrore(erroreDi(err, "Errore nel salvataggio")); }
  }
  async function cambiaRinnovo(c, campi) {
    setErrore(null);
    try { await api.put(`/corsi/${c.id}`, corpo(c, campi)); load(); if (anteprimaId === c.id) setAnteprimaId(null); }
    catch (err) { setErrore(erroreDi(err, "Errore nel salvataggio")); }
  }
  async function mostraAnteprima(c) {
    if (anteprimaId === c.id) { setAnteprimaId(null); return; }
    setErrore(null);
    try { setAnteprima((await api.get(`/corsi/${c.id}/rinnovo/anteprima`)).data); setAnteprimaId(c.id); }
    catch (err) { setErrore(erroreDi(err, "Impossibile calcolare l'anteprima del rinnovo")); }
  }

  async function cambiaTemplate(c, certificato_template_id) {
    setErrore(null);
    try { await api.put(`/corsi/${c.id}`, corpo(c, { certificato_template_id: certificato_template_id || null })); }
    catch (err) { setErrore(erroreDi(err, "Impossibile cambiare il template")); }
    load();
  }

  function apriNuovaVersione(c) {
    setVersioneApertaId(c.id);
    setVersioneForm({ richiedi_ripetizione: false, nota: "" });
    setVersioneMsg(null);
  }

  async function confermaNuovaVersione(corsoId) {
    try {
      const r = await api.post(`/corsi/${corsoId}/nuova-versione`, versioneForm);
      setVersioneMsg(`Versione ${r.data.versione} creata` + (r.data.notificati > 0 ? ` — ${r.data.notificati} notifiche inviate.` : "."));
      load();
    } catch (err) { setVersioneMsg(erroreDi(err, "Nuova versione non creata")); }
  }

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try { await api.post("/corsi", {
      ...form,
      validita_mesi: form.validita_mesi ? parseInt(form.validita_mesi) : null,
      giorni_scadenza_breve: form.giorni_scadenza_breve ? parseInt(form.giorni_scadenza_breve) : null,
      rinnovo_automatico: !!form.validita_mesi && form.rinnovo_automatico,
      rinnovo_giorni_anticipo: parseInt(form.rinnovo_giorni_anticipo) || 30,
    }); } catch (err) { setErrore(erroreDi(err, "Errore nella creazione")); return; }
    setForm({ titolo: "", descrizione: "", categoria: "", validita_mesi: "", ha_test_finale: false, azione_test_non_superato: "concludi_comunque", giorni_scadenza_breve: "", confronta_pre_post_test: false, permetti_autoiscrizione: false, richiedi_approvazione_responsabile: false, rinnovo_automatico: false, rinnovo_giorni_anticipo: 30, etichette: [] });
    load();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Corsi</h2>
          <p>Definizione del corso, indipendente da come viene erogato: la modalità si sceglie per ogni Edizione.</p>
        </div>
        <ExportButton path="/corsi-export/elenco" filename="corsi" />
      </div>
      <div className="card">
        <h3>Nuovo corso</h3>
        <form onSubmit={submit}>
          <div className="field"><label>Titolo</label><input required value={form.titolo} onChange={(e) => setForm({ ...form, titolo: e.target.value })} /></div>
          <div className="field"><label>Descrizione</label><textarea value={form.descrizione} onChange={(e) => setForm({ ...form, descrizione: e.target.value })} /></div>
          <div className="row">
            <div className="field"><label>Validità (mesi, vuoto = nessun rinnovo)</label><input type="number" value={form.validita_mesi} onChange={(e) => setForm({ ...form, validita_mesi: e.target.value })} /></div>
          </div>
          <div className="field"><label>Etichette</label><SceltaEtichette famiglie={famiglie} valore={form.etichette} onChange={(v) => setForm({ ...form, etichette: v })} /></div>
          {form.validita_mesi && (
            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" style={{ width: "auto" }} checked={form.rinnovo_automatico} onChange={(e) => setForm({ ...form, rinnovo_automatico: e.target.checked })} />
                Rinnovo automatico: iscrivi alla prossima sessione quando l'attestato sta per scadere
              </label>
              {form.rinnovo_automatico && (
                <div style={{ marginTop: 6, fontSize: 13 }}>
                  Iscrivi <input type="number" min="1" max="365" style={{ width: 70, display: "inline-block" }} value={form.rinnovo_giorni_anticipo} onChange={(e) => setForm({ ...form, rinnovo_giorni_anticipo: e.target.value })} /> giorni prima della scadenza.
                  <span className="text-muted"> Se non c'è nessuna sessione disponibile, ti avvisiamo.</span>
                </div>
              )}
            </div>
          )}
          <div className="field">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={form.ha_test_finale} onChange={(e) => setForm({ ...form, ha_test_finale: e.target.checked })} />
              Il corso prevede un test finale
            </label>
          </div>
          {form.ha_test_finale && (
            <div className="row">
              <div className="field">
                <label>Se il test finale non è superato</label>
                <select value={form.azione_test_non_superato} onChange={(e) => setForm({ ...form, azione_test_non_superato: e.target.value })}>
                  {AZIONI.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                </select>
              </div>
              {form.azione_test_non_superato === "concludi_scadenza_breve" && (
                <div className="field"><label>Giorni entro cui ripetere</label><input type="number" required value={form.giorni_scadenza_breve} onChange={(e) => setForm({ ...form, giorni_scadenza_breve: e.target.value })} /></div>
              )}
            </div>
          )}
          <div className="field">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={form.confronta_pre_post_test} onChange={(e) => setForm({ ...form, confronta_pre_post_test: e.target.checked })} />
              Confronta test iniziale/finale (misura il delta di apprendimento, se il corso ha entrambi)
            </label>
          </div>
          <div className="field">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={form.permetti_autoiscrizione} onChange={(e) => setForm({ ...form, permetti_autoiscrizione: e.target.checked, richiedi_approvazione_responsabile: e.target.checked ? form.richiedi_approvazione_responsabile : false })} />
              Permetti auto-iscrizione (il discente si iscrive da sé a una sessione con posti disponibili)
            </label>
          </div>
          {form.permetti_autoiscrizione && (
            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" style={{ width: "auto" }} checked={form.richiedi_approvazione_responsabile} onChange={(e) => setForm({ ...form, richiedi_approvazione_responsabile: e.target.checked })} />
                Richiedi approvazione del responsabile
              </label>
            </div>
          )}
          <button type="submit">Crea</button>
        </form>
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      <div style={{ maxWidth: 420 }}><FiltroEtichette valore={filtroEtichette} onChange={setFiltroEtichette} /></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Titolo</th><th>Etichette</th><th>Validità</th><th>Rinnovo automatico</th><th>Se test non superato</th><th>Auto-iscrizione</th><th>Versione</th><th>Attestato</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.filter((c) => {
              if (!filtroEtichette.length) return true;
              const mie = new Set(c.etichette.map((e) => e.id));
              const perFamiglia = {};
              famiglie.forEach((f) => f.etichette.forEach((e) => { if (filtroEtichette.includes(e.id)) (perFamiglia[f.id] = perFamiglia[f.id] || []).push(e.id); }));
              return Object.values(perFamiglia).every((gruppo) => gruppo.some((id) => mie.has(id)));
            }).map((c) => (
              <React.Fragment key={c.id}>
                <tr>
                  <td>{c.titolo}</td>
                  <td style={{ minWidth: 180 }}>
                    <ChipEtichette etichette={c.etichette} />
                    {c.etichette_mancanti?.length > 0 && <div style={{ fontSize: 11, color: "var(--red-text)", marginTop: 3 }}>manca: {c.etichette_mancanti.join(", ")}</div>}
                    {c.avvisi_etichette?.map((a) => <div key={a} style={{ fontSize: 11, color: "var(--yellow-text)", marginTop: 3 }}>⚠ {a}</div>)}
                    <button type="button" className="secondary btn-sm" style={{ marginTop: 4 }} onClick={() => setEtichetteAperte(etichetteAperte?.id === c.id ? null : { id: c.id, valore: c.etichette.map((e) => e.id) })}>{etichetteAperte?.id === c.id ? "Chiudi" : "Modifica"}</button>
                  </td>
                  <td>{c.validita_mesi ? `${c.validita_mesi} mesi` : "senza scadenza"}</td>
                  <td>
                    {c.validita_mesi ? (
                      <>
                        <label style={{ display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
                          <input type="checkbox" style={{ width: "auto" }} checked={c.rinnovo_automatico} onChange={(e) => cambiaRinnovo(c, { rinnovo_automatico: e.target.checked })} />
                          {c.rinnovo_automatico ? `${c.rinnovo_giorni_anticipo} gg prima` : "spento"}
                        </label>
                        {c.rinnovo_automatico && <button type="button" className="secondary btn-sm" style={{ marginTop: 4 }} onClick={() => mostraAnteprima(c)}>{anteprimaId === c.id ? "Nascondi" : "Chi verrebbe iscritto"}</button>}
                      </>
                    ) : <span className="text-muted">—</span>}
                  </td>
                  <td>{c.ha_test_finale ? <span className="badge gray">{AZIONI.find((a) => a.value === c.azione_test_non_superato)?.label}</span> : <span className="text-muted">nessun test finale</span>}</td>
                  <td>{c.permetti_autoiscrizione ? <span className="badge gray">{c.richiedi_approvazione_responsabile ? "sì, con approvazione" : "sì"}</span> : <span className="text-muted">no</span>}</td>
                  <td>v{c.versione}</td>
                  <td>
                    <select value={c.certificato_template_id || ""} onChange={(e) => cambiaTemplate(c, e.target.value)} style={{ fontSize: 12 }}>
                      <option value="">Predefinito aziendale</option>
                      {templates.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
                    </select>
                  </td>
                  <td>{c.is_active ? <span className="badge green">attivo</span> : <span className="badge gray">disattivato</span>}</td>
                  <td>
                    <Link to={`/corsi/${c.id}/test`}>Gestisci test</Link>{" "}
                    <button type="button" className="secondary btn-sm" onClick={() => apriNuovaVersione(c)}>Nuova versione</button>
                  </td>
                </tr>
                {etichetteAperte?.id === c.id && (
                  <tr>
                    <td colSpan={10}>
                      <div className="card card-muted">
                        <strong>Etichette di "{c.titolo}"</strong>
                        <div style={{ marginTop: 8 }}><SceltaEtichette famiglie={famiglie} valore={etichetteAperte.valore} onChange={(v) => setEtichetteAperte({ ...etichetteAperte, valore: v })} /></div>
                        <button type="button" onClick={() => salvaEtichette(c)}>Salva le etichette</button>{" "}
                        <button type="button" className="secondary" onClick={() => setEtichetteAperte(null)}>Annulla</button>
                      </div>
                    </td>
                  </tr>
                )}
                {anteprimaId === c.id && anteprima && (
                  <tr>
                    <td colSpan={10}>
                      <div className="card card-muted">
                        <strong>Rinnovo automatico di "{c.titolo}"</strong>
                        <p style={{ margin: "6px 0", fontSize: 13 }}>
                          {anteprima.persone.length === 0 ? "Nessuno è in scadenza nei prossimi " + anteprima.giorni_anticipo + " giorni." :
                            `${anteprima.persone.length} ${anteprima.persone.length === 1 ? "persona" : "persone"} da rinnovare: ${anteprima.persone.map((p) => `${p.nome} (${p.scaduto ? "scaduto" : "scade"} il ${new Date(p.scadenza).toLocaleDateString("it-IT")})`).join(", ")}.`}
                        </p>
                        <p style={{ margin: 0, fontSize: 13 }}>
                          {anteprima.sessioni.length === 0 ? <span style={{ color: "var(--red-text)" }}>Nessuna sessione disponibile: pianificane una, altrimenti il rinnovo non può partire.</span> :
                            `Sessioni utili: ${anteprima.sessioni.map((e) => `${e.data_inizio ? new Date(e.data_inizio).toLocaleDateString("it-IT") : "sempre aperta"}${e.posti_liberi != null ? ` (${e.posti_liberi} posti)` : ""}`).join(", ")}.`}
                        </p>
                        <p className="text-muted" style={{ margin: "6px 0 0", fontSize: 12 }}>Il controllo gira ogni notte alle 02:00.</p>
                      </div>
                    </td>
                  </tr>
                )}
                {versioneApertaId === c.id && (
                  <tr>
                    <td colSpan={10}>
                      <div className="card card-muted">
                        <p>Stai creando la <strong>versione {c.versione + 1}</strong> di "{c.titolo}". Chi ha già completato questo corso:</p>
                        <div className="field">
                          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <input type="checkbox" style={{ width: "auto" }} checked={versioneForm.richiedi_ripetizione}
                                   onChange={(e) => setVersioneForm({ ...versioneForm, richiedi_ripetizione: e.target.checked })} />
                            Richiedi a chi lo ha già fatto di ripeterlo (non più compliant finché non lo rifà — usalo solo per aggiornamenti normativi sostanziali)
                          </label>
                        </div>
                        {!versioneForm.richiedi_ripetizione && (
                          <p className="text-muted" style={{ fontSize: 13 }}>
                            Senza spunta: chi l'ha già completato resta compliant, vedrà solo un'etichetta informativa "aggiornamento disponibile".
                          </p>
                        )}
                        <div className="field"><label>Nota (opzionale, cosa è cambiato)</label><input value={versioneForm.nota} onChange={(e) => setVersioneForm({ ...versioneForm, nota: e.target.value })} /></div>
                        <button type="button" onClick={() => confermaNuovaVersione(c.id)}>Confermo nuova versione</button>{" "}
                        <button type="button" className="secondary" onClick={() => setVersioneApertaId(null)}>Annulla</button>
                        {versioneMsg && <p>{versioneMsg}</p>}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
