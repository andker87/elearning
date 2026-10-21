import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import ExportButton from "../components/ExportButton";
import PersonePercorso from "../components/PersonePercorso";
import { elencoUffici } from "../uffici";

const MODALITA = {
  libero: ["Libero", "I corsi si fanno in qualunque ordine."],
  sequenziale: ["Sequenziale", "Uno dopo l'altro, nell'ordine dei numeri: non si può saltare."],
  propedeuticita: ["Con propedeuticità", "Liberi, tranne quelli che richiedono di aver fatto prima altri corsi (li scegli tu)."],
};
const TRIGGER_LABEL = { manuale: "Assegnazione manuale", ingresso_azienda: "Automatico all'ingresso in azienda", gruppo: "Automatico per ufficio", mansione: "Automatico per mansione" };
const SCHEDE = [{ id: "elenco", label: "Elenco percorsi" }, { id: "nuovo", label: "Nuovo percorso" }];
const FORM_VUOTO = {
  nome: "", modalita: "libero", triggerTipo: "manuale", triggerGruppoId: "", triggerMansioneId: "",
  steps: [{ corso_id: "", ordine: 1, richiede_step_ordini: [] }],
};

// Il modulo di un percorso: nome, come si assegna, come si procede e i corsi (con le propedeuticità, se la modalità le prevede).
function ModuloPercorso({ form, setForm, corsi, gruppi, mansioni, errore, invio, onSubmit, onAnnulla, etichettaInvio }) {
  const titolo = (id) => corsi.find((c) => c.id === id)?.titolo;
  const aggiorna = (i, campo, valore) => setForm({ ...form, steps: form.steps.map((s, n) => (n === i ? { ...s, [campo]: valore } : s)) });
  const alternaRichiesto = (i, ordine) => {
    const s = form.steps[i];
    aggiorna(i, "richiede_step_ordini", s.richiede_step_ordini.includes(ordine) ? s.richiede_step_ordini.filter((o) => o !== ordine) : [...s.richiede_step_ordini, ordine]);
  };
  const prossimoOrdine = () => (form.steps.reduce((m, s) => Math.max(m, Number(s.ordine) || 0), 0) + 1);
  return (
    <form onSubmit={onSubmit}>
      <div className="row">
        <div className="field"><label htmlFor="p-nome">Nome</label><input id="p-nome" required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></div>
        <div className="field">
          <label htmlFor="p-mod">Come si procede nei corsi</label>
          <select id="p-mod" value={form.modalita} onChange={(e) => setForm({ ...form, modalita: e.target.value })}>
            {Object.entries(MODALITA).map(([k, [nome]]) => <option key={k} value={k}>{nome}</option>)}
          </select>
          <span className="text-muted" style={{ fontSize: 12 }}>{MODALITA[form.modalita][1]}</span>
        </div>
      </div>
      <div className="row">
        <div className="field">
          <label htmlFor="p-trig">Assegnazione</label>
          <select id="p-trig" value={form.triggerTipo} onChange={(e) => setForm({ ...form, triggerTipo: e.target.value })}>
            <option value="manuale">Manuale (la Formazione lo assegna a delle persone)</option>
            <option value="ingresso_azienda">Automatica all'ingresso in azienda</option>
            <option value="gruppo">Automatica per ufficio (sottouffici compresi)</option>
            <option value="mansione">Automatica per mansione</option>
          </select>
        </div>
        {form.triggerTipo === "gruppo" && (
          <div className="field"><label htmlFor="p-uff">Ufficio</label>
            <select id="p-uff" required value={form.triggerGruppoId} onChange={(e) => setForm({ ...form, triggerGruppoId: e.target.value })}>
              <option value="">-- seleziona --</option>{gruppi.map((g) => <option key={g.id} value={g.id}>{g.etichetta}</option>)}
            </select></div>
        )}
        {form.triggerTipo === "mansione" && (
          <div className="field"><label htmlFor="p-man">Mansione</label>
            <select id="p-man" required value={form.triggerMansioneId} onChange={(e) => setForm({ ...form, triggerMansioneId: e.target.value })}>
              <option value="">-- seleziona --</option>{mansioni.filter((m) => m.is_active || m.id === form.triggerMansioneId).map((m) => <option key={m.id} value={m.id}>{m.name}{m.is_active ? "" : " (non attiva)"}</option>)}
            </select></div>
        )}
      </div>

      <h4 style={{ margin: "12px 0 6px" }}>Corsi del percorso</h4>
      {form.modalita !== "libero" && <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>Il numero indica l'ordine.{form.modalita === "sequenziale" ? " Ogni corso richiede il precedente." : " Per ogni corso spunta quali corsi deve aver già completato."}</p>}
      {form.steps.map((s, i) => {
        const altri = form.steps.filter((_, n) => n !== i);
        return (
          <div key={i} className="card card-muted" style={{ marginBottom: 8 }}>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="field"><label htmlFor={`s-corso-${i}`}>Corso {i + 1}</label>
                <select id={`s-corso-${i}`} value={s.corso_id} onChange={(e) => aggiorna(i, "corso_id", e.target.value)} required>
                  <option value="">-- corso --</option>{corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
                </select></div>
              <div className="field" style={{ maxWidth: 110 }}><label htmlFor={`s-ord-${i}`}>Numero d'ordine</label>
                <input id={`s-ord-${i}`} type="number" min="1" required value={s.ordine} onChange={(e) => aggiorna(i, "ordine", parseInt(e.target.value, 10) || 0)} /></div>
              {form.steps.length > 1 && <div className="field"><button type="button" className="danger btn-sm" onClick={() => setForm({ ...form, steps: form.steps.filter((_, n) => n !== i) })}>Togli</button></div>}
            </div>
            {form.modalita === "propedeuticita" && altri.length > 0 && (
              <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                <legend style={{ fontSize: 13, fontWeight: 600, padding: 0 }}>Richiede di aver completato:</legend>
                <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 4 }}>
                  {altri.map((a) => (
                    <label key={a.ordine + "-" + a.corso_id} style={{ display: "flex", alignItems: "center", gap: 6, margin: 0, fontSize: 13 }}>
                      <input type="checkbox" style={{ width: "auto" }} checked={s.richiede_step_ordini.includes(a.ordine)} onChange={() => alternaRichiesto(i, a.ordine)} />
                      {a.ordine}. {titolo(a.corso_id) || "(corso da scegliere)"}
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
          </div>
        );
      })}
      <button type="button" className="secondary" onClick={() => setForm({ ...form, steps: [...form.steps, { corso_id: "", ordine: prossimoOrdine(), richiede_step_ordini: [] }] })}>+ Aggiungi un corso</button>
      {errore && <div className="error-msg" role="alert" style={{ marginTop: 10 }}>{errore}</div>}
      <div style={{ marginTop: 12 }}>
        <button type="submit" disabled={invio}>{invio ? "Salvo..." : etichettaInvio}</button>{" "}
        {onAnnulla && <button type="button" className="secondary" onClick={onAnnulla}>Annulla</button>}
      </div>
    </form>
  );
}

export default function Percorsi() {
  const [scheda, setScheda] = useState("elenco");
  const [list, setList] = useState(null);
  const [corsi, setCorsi] = useState([]);
  const [gruppi, setGruppi] = useState([]);
  const [mansioni, setMansioni] = useState([]);
  const [nuovo, setNuovo] = useState(FORM_VUOTO);
  const [apertura, setApertura] = useState(null);       // { id, tipo: "modifica" | "persone", form }
  const [msg, setMsg] = useState(null);
  const [errore, setErrore] = useState(null);           // errore della pagina
  const [errForm, setErrForm] = useState(null);
  const [invio, setInvio] = useState(false);

  function carica() { api.get("/percorsi").then((r) => setList(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i percorsi"))); }
  useEffect(() => {
    carica();
    api.get("/corsi").then((r) => setCorsi(r.data)).catch(() => {});
    api.get("/groups").then((r) => setGruppi(elencoUffici(r.data))).catch(() => {});
    api.get("/mansioni").then((r) => setMansioni(r.data)).catch(() => {});
  }, []);

  const titoloCorso = (id) => corsi.find((c) => c.id === id)?.titolo || "—";
  const corpo = (f) => ({
    nome: f.nome, modalita: f.modalita, trigger_tipo: f.triggerTipo,
    trigger_gruppo_id: f.triggerTipo === "gruppo" ? f.triggerGruppoId : null, trigger_mansione_id: f.triggerTipo === "mansione" ? f.triggerMansioneId : null,
    steps: f.steps.map((s) => ({ corso_id: s.corso_id, ordine: s.ordine, richiede_step_ordini: f.modalita === "propedeuticita" ? s.richiede_step_ordini : [] })),
  });
  const formDa = (p) => {
    const ordineDi = Object.fromEntries(p.steps.map((s) => [s.id, s.ordine]));
    return { nome: p.nome, modalita: p.modalita || "libero", triggerTipo: p.trigger_tipo, triggerGruppoId: p.trigger_gruppo_id || "", triggerMansioneId: p.trigger_mansione_id || "",
      steps: [...p.steps].sort((a, b) => a.ordine - b.ordine).map((s) => ({ corso_id: s.corso_id, ordine: s.ordine, richiede_step_ordini: s.richiede_step_ids.map((id) => ordineDi[id]).filter((o) => o !== undefined) })) };
  };

  async function crea(e) {
    e.preventDefault(); setErrForm(null); setInvio(true);
    try { await api.post("/percorsi", corpo(nuovo)); setNuovo(FORM_VUOTO); setScheda("elenco"); setMsg("Percorso creato."); carica(); }
    catch (err) { setErrForm(erroreDi(err, "Impossibile creare il percorso")); }
    setInvio(false);
  }
  async function salva(e) {
    e.preventDefault(); setErrForm(null); setInvio(true);
    try { await api.put(`/percorsi/${apertura.id}`, corpo(apertura.form)); setApertura(null); setMsg("Percorso salvato."); carica(); }
    catch (err) { setErrForm(erroreDi(err, "Impossibile salvare il percorso")); }
    setInvio(false);
  }
  async function sincronizza() {
    setErrore(null);
    try {
      const r = await api.post("/percorsi/sincronizza");
      setMsg(`Nuove assegnazioni: ${r.data.nuove_assegnazioni}. Iscrizioni fatte: ${r.data.iscrizioni}${r.data.in_attesa_sessione ? `; ${r.data.in_attesa_sessione} in attesa di una sessione` : ""}.`);
      carica();
    } catch (err) { setErrore(erroreDi(err, "Sincronizzazione non riuscita")); }
  }
  const apri = (p, tipo) => { setErrForm(null); setApertura(apertura?.id === p.id && apertura.tipo === tipo ? null : { id: p.id, tipo, form: formDa(p) }); };
  const props = { corsi, gruppi, mansioni };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Percorsi formativi</h2>
          <p>Pacchetti di corsi da svolgere (onboarding, aggiornamenti periodici). Assegnando un percorso, la persona viene iscritta ai corsi: tutti insieme, uno dopo l'altro o con le propedeuticità che indichi.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}><ExportButton path="/corsi-export/percorsi" filename="percorsi" /><button type="button" className="secondary" onClick={sincronizza}>Sincronizza assegnazioni automatiche</button></div>
      </div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
      </div>
      {msg && <div className="card card-muted" role="status">{msg}</div>}
      {errore && <div className="error-msg" role="alert">{errore}</div>}

      {scheda === "nuovo" && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Nuovo percorso</h3>
          <ModuloPercorso form={nuovo} setForm={setNuovo} {...props} errore={errForm} invio={invio} onSubmit={crea} etichettaInvio="Crea percorso" />
        </div>
      )}

      {scheda === "elenco" && (
        <>
          {!list && !errore && <p className="text-muted">Caricamento...</p>}
          {list && list.length === 0 && <p className="empty-state">Nessun percorso ancora: creane uno dalla scheda «Nuovo percorso».</p>}
          {list && list.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Percorso</th><th>Corsi</th><th>Persone</th><th></th></tr></thead>
                <tbody>
                  {list.map((p) => (
                    <React.Fragment key={p.id}>
                      <tr>
                        <td><strong>{p.nome}</strong>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                            <span className="badge blue" title={MODALITA[p.modalita]?.[1]}>{MODALITA[p.modalita]?.[0] || p.modalita}</span>
                            <span className="badge gray">{TRIGGER_LABEL[p.trigger_tipo]}</span>
                          </div></td>
                        <td>{[...p.steps].sort((a, b) => a.ordine - b.ordine).map((s) => <div key={s.id} style={{ fontSize: 13 }}>{s.ordine}. {titoloCorso(s.corso_id)}</div>)}</td>
                        <td>{p.n_assegnati || <span className="text-muted">—</span>}</td>
                        <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                          <button type="button" className="btn-sm" onClick={() => apri(p, "persone")}>Persone</button>{" "}
                          <button type="button" className="secondary btn-sm" onClick={() => apri(p, "modifica")}>Modifica</button>
                        </td>
                      </tr>
                      {apertura?.id === p.id && (
                        <tr>
                          <td colSpan={4} style={{ background: "var(--bg3)" }}>
                            {apertura.tipo === "persone"
                              ? <PersonePercorso percorso={p} onCambia={carica} />
                              : <>
                                  <h4 style={{ margin: "8px 0" }}>Modifica «{p.nome}»</h4>
                                  <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>Le assegnazioni restano. Le persone che hanno il percorso vengono riallineate: se cambi i corsi o le propedeuticità, chi si trova con un corso sbloccato viene iscritto.</p>
                                  <ModuloPercorso form={apertura.form} setForm={(f) => setApertura({ ...apertura, form: f })} {...props} errore={errForm} invio={invio} onSubmit={salva} onAnnulla={() => setApertura(null)} etichettaInvio="Salva" />
                                </>}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
