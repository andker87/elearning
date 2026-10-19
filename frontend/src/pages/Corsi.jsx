import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { erroreDi } from "../api";
import { useFamiglie, SceltaEtichette, ChipEtichette, FiltroEtichette } from "../components/Etichette";
import ExportButton from "../components/ExportButton";
import CampoDurata from "../components/CampoDurata";
import { formattaDurata } from "../durata";

const AZIONI = [
  { value: "concludi_comunque", label: "Concludi comunque" },
  { value: "concludi_scadenza_breve", label: "Concludi, ma ripeti entro N giorni" },
  { value: "rifai_test", label: "Rifai solo il test" },
  { value: "rifai_corso", label: "Rifai il corso da zero" },
];
const SCHEDE = [{ id: "elenco", label: "Elenco corsi" }, { id: "nuovo", label: "Nuovo corso" }];
const VUOTO = {
  titolo: "", descrizione: "", validita_mesi: "", durata_minuti: null,
  ha_test_finale: false, azione_test_non_superato: "concludi_comunque", giorni_scadenza_breve: "",
  confronta_pre_post_test: false, permetti_autoiscrizione: false, richiedi_approvazione_responsabile: false,
  rinnovo_automatico: false, rinnovo_giorni_anticipo: 30, certificato_template_id: "", is_active: true, etichette: [],
};

// Dal corso come lo restituisce il server ai valori del modulo (testi per i campi numerici).
function valoriDa(c) {
  return {
    titolo: c.titolo, descrizione: c.descrizione || "", validita_mesi: c.validita_mesi ?? "", durata_minuti: c.durata_minuti ?? null,
    ha_test_finale: c.ha_test_finale, azione_test_non_superato: c.azione_test_non_superato, giorni_scadenza_breve: c.giorni_scadenza_breve ?? "",
    confronta_pre_post_test: c.confronta_pre_post_test, permetti_autoiscrizione: c.permetti_autoiscrizione,
    richiedi_approvazione_responsabile: c.richiedi_approvazione_responsabile,
    rinnovo_automatico: c.rinnovo_automatico, rinnovo_giorni_anticipo: c.rinnovo_giorni_anticipo,
    certificato_template_id: c.certificato_template_id || "", is_active: c.is_active, etichette: c.etichette.map((e) => e.id),
  };
}

// Dai valori del modulo al corpo della richiesta (crea e modifica mandano lo stesso).
function corpoDa(v, categoria = null) {
  return {
    ...v, categoria,
    validita_mesi: v.validita_mesi ? parseInt(v.validita_mesi) : null,
    durata_minuti: v.durata_minuti || null,
    giorni_scadenza_breve: v.ha_test_finale && v.azione_test_non_superato === "concludi_scadenza_breve" && v.giorni_scadenza_breve ? parseInt(v.giorni_scadenza_breve) : null,
    rinnovo_automatico: !!v.validita_mesi && v.rinnovo_automatico,
    rinnovo_giorni_anticipo: parseInt(v.rinnovo_giorni_anticipo) || 30,
    certificato_template_id: v.certificato_template_id || null,
  };
}

// Campi del corso, uguali per «Nuovo corso» e per «Modifica».
function CampiCorso({ v, set, famiglie, templates, modifica, anteprima, onAnteprima }) {
  const spunta = (campo, testo, extra) => (
    <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <input type="checkbox" style={{ width: "auto" }} checked={v[campo]} onChange={(e) => set({ ...v, [campo]: e.target.checked, ...(extra ? extra(e.target.checked) : {}) })} />
      {testo}
    </label>
  );
  return (
    <>
      <div className="field"><label>Titolo</label><input required value={v.titolo} onChange={(e) => set({ ...v, titolo: e.target.value })} /></div>
      <div className="field"><label>Descrizione</label><textarea value={v.descrizione} onChange={(e) => set({ ...v, descrizione: e.target.value })} /></div>
      <div className="row">
        <CampoDurata valore={v.durata_minuti} onChange={(d) => set({ ...v, durata_minuti: d })} id="corso-durata" suggerimento="Quanto dura il corso. Le sessioni la ereditano (chi le organizza può cambiarla) e finisce sull'attestato." />
      </div>
      <div className="row">
        <div className="field"><label>Validità (mesi, vuoto = nessun rinnovo)</label><input type="number" min="1" value={v.validita_mesi} onChange={(e) => set({ ...v, validita_mesi: e.target.value })} /></div>
        <div className="field">
          <label>Attestato</label>
          <select value={v.certificato_template_id} onChange={(e) => set({ ...v, certificato_template_id: e.target.value })}>
            <option value="">Predefinito aziendale</option>
            {templates.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Etichette</label>
        {famiglie.length === 0
          ? <p className="text-muted" style={{ fontSize: 13, margin: 0 }}>Non hai ancora definito nessuna famiglia di etichette (tematica, norma, ambito...). Puoi farlo in <Link to="/etichette">Etichette dei corsi</Link>: le etichette servono a classificare i corsi e a filtrare registro e matrice.</p>
          : <SceltaEtichette famiglie={famiglie} valore={v.etichette} onChange={(e) => set({ ...v, etichette: e })} />}
      </div>
      {v.validita_mesi && (
        <div className="field">
          {spunta("rinnovo_automatico", "Rinnovo automatico: iscrivi alla prossima sessione quando l'attestato sta per scadere")}
          {v.rinnovo_automatico && (
            <div style={{ marginTop: 6, fontSize: 13 }}>
              Iscrivi <input type="number" min="1" max="365" style={{ width: 70, display: "inline-block" }} value={v.rinnovo_giorni_anticipo} onChange={(e) => set({ ...v, rinnovo_giorni_anticipo: e.target.value })} /> giorni prima della scadenza.
              <span className="text-muted"> Se non c'è nessuna sessione disponibile, ti avvisiamo.</span>
              {modifica && <> <button type="button" className="secondary btn-sm" onClick={onAnteprima}>{anteprima ? "Nascondi" : "Chi verrebbe rinnovato"}</button></>}
              {modifica && anteprima && (
                <div className="card card-muted" style={{ marginTop: 8 }}>
                  <p style={{ margin: "0 0 6px", fontSize: 13 }}>
                    {anteprima.persone.length === 0 ? "Nessuno è in scadenza nei prossimi " + anteprima.giorni_anticipo + " giorni." :
                      `${anteprima.persone.length} ${anteprima.persone.length === 1 ? "persona" : "persone"} da rinnovare: ${anteprima.persone.map((p) => `${p.nome} (${p.scaduto ? "scaduto" : "scade"} il ${new Date(p.scadenza).toLocaleDateString("it-IT")})`).join(", ")}.`}
                  </p>
                  <p style={{ margin: 0, fontSize: 13 }}>
                    {anteprima.sessioni.length === 0 ? <span style={{ color: "var(--red-text)" }}>Nessuna sessione disponibile: pianificane una, altrimenti il rinnovo non può partire.</span> :
                      `Sessioni utili: ${anteprima.sessioni.map((e) => `${e.data_inizio ? new Date(e.data_inizio).toLocaleDateString("it-IT") : "sempre aperta"}${e.posti_liberi != null ? ` (${e.posti_liberi} posti liberi)` : ""}`).join(", ")}.`}
                  </p>
                  <p className="text-muted" style={{ margin: "6px 0 0", fontSize: 12 }}>Il controllo gira ogni notte alle 02:00 sulle impostazioni salvate.</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      <div className="field">{spunta("ha_test_finale", "Il corso prevede un test finale")}</div>
      {v.ha_test_finale && (
        <div className="row">
          <div className="field">
            <label>Se il test finale non è superato</label>
            <select value={v.azione_test_non_superato} onChange={(e) => set({ ...v, azione_test_non_superato: e.target.value })}>
              {AZIONI.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>
          {v.azione_test_non_superato === "concludi_scadenza_breve" && (
            <div className="field"><label>Giorni entro cui ripetere</label><input type="number" required min="1" value={v.giorni_scadenza_breve} onChange={(e) => set({ ...v, giorni_scadenza_breve: e.target.value })} /></div>
          )}
        </div>
      )}
      <div className="field">{spunta("confronta_pre_post_test", "Confronta test iniziale/finale (misura il delta di apprendimento, se il corso ha entrambi)")}</div>
      <div className="field">{spunta("permetti_autoiscrizione", "Permetti auto-iscrizione (il discente si iscrive da sé a una sessione con posti disponibili)", (on) => (on ? {} : { richiedi_approvazione_responsabile: false }))}</div>
      {v.permetti_autoiscrizione && <div className="field">{spunta("richiedi_approvazione_responsabile", "Richiedi approvazione del responsabile")}</div>}
      {modifica && <div className="field">{spunta("is_active", "Corso attivo (se lo spegni non si può più assegnare, lo storico resta)")}</div>}
    </>
  );
}

export default function Corsi() {
  const navigate = useNavigate();
  const [scheda, setScheda] = useState("elenco");
  const [list, setList] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState(VUOTO);
  const famiglie = useFamiglie();
  const [filtroEtichette, setFiltroEtichette] = useState([]);
  const [modifica, setModifica] = useState(null);       // { id, titolo, categoria, valori }
  const [erroreModifica, setErroreModifica] = useState(null);
  const [anteprimaId, setAnteprimaId] = useState(null);
  const [anteprima, setAnteprima] = useState(null);
  const [errore, setErrore] = useState(null);
  const [versioneApertaId, setVersioneApertaId] = useState(null);
  const [versioneForm, setVersioneForm] = useState({ richiedi_ripetizione: false, nota: "" });
  const [versioneMsg, setVersioneMsg] = useState(null);

  function load() { api.get("/corsi").then((r) => setList(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i corsi"))); }
  useEffect(load, []);
  useEffect(() => { api.get("/certificato-templates").then((r) => setTemplates(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i template degli attestati"))); }, []);
  useEffect(() => { if (modifica?.id) document.getElementById("c-form-modifica")?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [modifica?.id]);

  function apriModifica(c) {
    setErroreModifica(null); setAnteprimaId(null); setVersioneApertaId(null);
    setModifica({ id: c.id, titolo: c.titolo, categoria: c.categoria, valori: valoriDa(c) });
  }

  async function salvaModifica(e) {
    e.preventDefault();
    setErroreModifica(null);
    try { await api.put(`/corsi/${modifica.id}`, corpoDa(modifica.valori, modifica.categoria)); }
    catch (err) { setErroreModifica(erroreDi(err, "Errore nel salvataggio")); return; }
    setModifica(null); setAnteprimaId(null);
    load();
  }

  async function mostraAnteprima() {
    if (anteprimaId === modifica.id) { setAnteprimaId(null); return; }
    setErroreModifica(null);
    try { setAnteprima((await api.get(`/corsi/${modifica.id}/rinnovo/anteprima`)).data); setAnteprimaId(modifica.id); }
    catch (err) { setErroreModifica(erroreDi(err, "Impossibile calcolare l'anteprima del rinnovo")); }
  }

  function apriNuovaVersione(c) {
    setModifica(null);
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
    try { await api.post("/corsi", corpoDa(form)); } catch (err) { setErrore(erroreDi(err, "Errore nella creazione")); return; }
    setForm(VUOTO);
    setScheda("elenco");
    load();
  }

  const visibili = list.filter((c) => {
    if (!filtroEtichette.length) return true;
    const mie = new Set(c.etichette.map((e) => e.id));
    const perFamiglia = {};
    famiglie.forEach((f) => f.etichette.forEach((e) => { if (filtroEtichette.includes(e.id)) (perFamiglia[f.id] = perFamiglia[f.id] || []).push(e.id); }));
    return Object.values(perFamiglia).every((gruppo) => gruppo.some((id) => mie.has(id)));
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Corsi</h2>
          <p>Definizione del corso, indipendente da come viene erogato: la modalità si sceglie per ogni Edizione. Le etichette si definiscono in <Link to="/etichette">Etichette dei corsi</Link>.</p>
        </div>
        <ExportButton path="/corsi-export/elenco" filename="corsi" />
      </div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      {scheda === "nuovo" && (
        <div className="card">
          <h3>Nuovo corso</h3>
          <form onSubmit={submit}>
            <CampiCorso v={form} set={setForm} famiglie={famiglie} templates={templates} />
            <button type="submit">Crea</button>
          </form>
        </div>
      )}
      {scheda === "elenco" && <>
        <div style={{ maxWidth: 420 }}><FiltroEtichette valore={filtroEtichette} onChange={setFiltroEtichette} /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Titolo</th><th>Etichette</th><th>Durata</th><th>Validità</th><th>Versione</th><th>Stato</th><th></th></tr></thead>
            <tbody>
              {visibili.map((c) => (
                <React.Fragment key={c.id}>
                  <tr>
                    <td>
                      {c.titolo}
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                        {c.ha_test_finale && <span className="badge gray">test finale</span>}
                        {c.rinnovo_automatico && <span className="badge gray">rinnovo automatico ({c.rinnovo_giorni_anticipo} gg prima)</span>}
                        {c.permetti_autoiscrizione && <span className="badge gray">{c.richiedi_approvazione_responsabile ? "auto-iscrizione con approvazione" : "auto-iscrizione"}</span>}
                      </div>
                    </td>
                    <td style={{ minWidth: 180 }}>
                      <ChipEtichette etichette={c.etichette} />
                      {c.etichette_mancanti?.length > 0 && <div style={{ fontSize: 11, color: "var(--red-text)", marginTop: 3 }}>manca: {c.etichette_mancanti.join(", ")}</div>}
                      {c.avvisi_etichette?.map((a) => <div key={a} style={{ fontSize: 11, color: "var(--yellow-text)", marginTop: 3 }}>⚠ {a}</div>)}
                    </td>
                    <td>{c.durata_minuti ? formattaDurata(c.durata_minuti) : <span className="text-muted">—</span>}</td>
                    <td>{c.validita_mesi ? `${c.validita_mesi} mesi` : "senza scadenza"}</td>
                    <td>v{c.versione}</td>
                    <td>{c.is_active ? <span className="badge green">attivo</span> : <span className="badge gray">disattivato</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button type="button" className="btn-sm" onClick={() => apriModifica(c)}>Modifica</button>{" "}
                      <button type="button" className="secondary btn-sm" onClick={() => navigate(`/corsi/${c.id}/test`)}>Test</button>{" "}
                      <button type="button" className="secondary btn-sm" onClick={() => apriNuovaVersione(c)}>Nuova versione</button>
                    </td>
                  </tr>
                  {modifica?.id === c.id && (
                    <tr>
                      <td colSpan={7} style={{ background: "var(--bg3)" }}>
                        <form id="c-form-modifica" onSubmit={salvaModifica}>
                          <h4 style={{ margin: "8px 0" }}>Modifica «{c.titolo}»</h4>
                          <CampiCorso v={modifica.valori} set={(valori) => setModifica({ ...modifica, valori })} famiglie={famiglie} templates={templates}
                            modifica anteprima={anteprimaId === c.id ? anteprima : null} onAnteprima={mostraAnteprima} />
                          {erroreModifica && <div className="error-msg">{erroreModifica}</div>}
                          <button type="submit">Salva</button>{" "}
                          <button type="button" className="secondary" onClick={() => { setModifica(null); setAnteprimaId(null); }}>Annulla</button>
                        </form>
                      </td>
                    </tr>
                  )}
                  {versioneApertaId === c.id && (
                    <tr>
                      <td colSpan={7} style={{ background: "var(--bg3)" }}>
                        <div style={{ padding: "8px 0" }}>
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
              {visibili.length === 0 && <tr><td colSpan={7} className="text-muted">{list.length === 0 ? "Nessun corso ancora: creane uno dalla scheda «Nuovo corso»." : "Nessun corso corrisponde ai filtri."}</td></tr>}
            </tbody>
          </table>
        </div>
      </>}
    </div>
  );
}
