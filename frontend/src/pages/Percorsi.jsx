import React, { useEffect, useState } from "react";
import api from "../api";
import ExportButton from "../components/ExportButton";
import { elencoUffici } from "../uffici";

const FORM_VUOTO = {
  nome: "", motivo: "policy_interna", motivoNota: "", triggerTipo: "manuale", triggerGruppoId: "", triggerMansioneId: "",
  steps: [{ corso_id: "", ordine: 1, richiede_step_ordini: [] }],
};

export default function Percorsi() {
  const [list, setList] = useState([]);
  const [corsi, setCorsi] = useState([]);
  const [gruppi, setGruppi] = useState([]);
  const [mansioni, setMansioni] = useState([]);
  const [form, setForm] = useState(FORM_VUOTO);
  const [editingId, setEditingId] = useState(null);
  const [msg, setMsg] = useState(null);

  function load() { api.get("/percorsi").then((r) => setList(r.data)); }
  useEffect(() => {
    load();
    api.get("/corsi").then((r) => setCorsi(r.data));
    api.get("/groups").then((r) => setGruppi(elencoUffici(r.data)));
    api.get("/mansioni").then((r) => setMansioni(r.data));
  }, []);

  function addStep() {
    setForm({ ...form, steps: [...form.steps, { corso_id: "", ordine: form.steps.length + 1, richiede_step_ordini: [] }] });
  }
  function updateStep(i, field, value) {
    const copy = [...form.steps];
    copy[i] = { ...copy[i], [field]: value };
    setForm({ ...form, steps: copy });
  }
  function rimuoviStep(i) {
    setForm({ ...form, steps: form.steps.filter((_, idx) => idx !== i) });
  }

  function iniziaModifica(p) {
    const stepByStepId = Object.fromEntries(p.steps.map((s) => [s.id, s.ordine]));
    setForm({
      nome: p.nome, motivo: p.motivo, motivoNota: p.motivo_nota || "",
      triggerTipo: p.trigger_tipo, triggerGruppoId: p.trigger_gruppo_id || "", triggerMansioneId: p.trigger_mansione_id || "",
      steps: p.steps.map((s) => ({
        corso_id: s.corso_id, ordine: s.ordine,
        richiede_step_ordini: s.richiede_step_ids.map((id) => stepByStepId[id]).filter((o) => o !== undefined),
      })),
    });
    setEditingId(p.id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function annullaModifica() {
    setEditingId(null);
    setForm(FORM_VUOTO);
  }

  async function submit(e) {
    e.preventDefault();
    const payload = {
      nome: form.nome, steps: form.steps,
      trigger_tipo: form.triggerTipo, trigger_gruppo_id: form.triggerTipo === "gruppo" ? form.triggerGruppoId : null,
      trigger_mansione_id: form.triggerTipo === "mansione" ? form.triggerMansioneId : null,
    };
    if (editingId) {
      await api.put(`/percorsi/${editingId}`, payload);
    } else {
      await api.post("/percorsi", payload);
    }
    setEditingId(null);
    setForm(FORM_VUOTO);
    load();
  }

  async function sincronizza() {
    const r = await api.post("/percorsi/sincronizza");
    setMsg(`Nuove assegnazioni create: ${r.data.nuove_assegnazioni}`);
    load();
  }

  const TRIGGER_LABEL = { manuale: "Assegnazione manuale", ingresso_azienda: "Automatico all'ingresso in azienda", gruppo: "Automatico per ufficio", mansione: "Automatico per mansione" };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Percorsi formativi</h2>
          <p>Sequenze obbligatorie di corsi (onboarding, refresh periodici) con eventuale propedeuticità tra step.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}><ExportButton path="/corsi-export/percorsi" filename="percorsi" /><button className="secondary" onClick={sincronizza}>Sincronizza assegnazioni automatiche</button></div>
      </div>
      {msg && <div className="card card-muted">{msg}</div>}

      <div className="card">
        <h3>{editingId ? "Modifica percorso" : "Nuovo percorso"}</h3>
        <form onSubmit={submit}>
          <div className="field"><label>Nome</label><input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></div>
          <div className="row">
            <div className="field">
              <label>Assegnazione</label>
              <select value={form.triggerTipo} onChange={(e) => setForm({ ...form, triggerTipo: e.target.value })}>
                <option value="manuale">Manuale</option>
                <option value="ingresso_azienda">Automatica all'ingresso in azienda</option>
                <option value="gruppo">Automatica per ufficio (sottouffici compresi)</option>
                <option value="mansione">Automatica per mansione</option>
              </select>
            </div>
            {form.triggerTipo === "gruppo" && (
              <div className="field">
                <label>Ufficio</label>
                <select required value={form.triggerGruppoId} onChange={(e) => setForm({ ...form, triggerGruppoId: e.target.value })}>
                  <option value="">-- seleziona --</option>
                  {gruppi.map((g) => <option key={g.id} value={g.id}>{g.etichetta}</option>)}
                </select>
              </div>
            )}
            {form.triggerTipo === "mansione" && (
              <div className="field">
                <label>Mansione</label>
                <select required value={form.triggerMansioneId} onChange={(e) => setForm({ ...form, triggerMansioneId: e.target.value })}>
                  <option value="">-- seleziona --</option>
                  {mansioni.filter((m) => m.is_active || m.id === form.triggerMansioneId).map((m) => <option key={m.id} value={m.id}>{m.name}{m.is_active ? "" : " (non attiva)"}</option>)}
                </select>
              </div>
            )}
          </div>
          <label>Step (in ordine)</label>
          {form.steps.map((s, i) => (
            <div className="row" key={i} style={{ marginBottom: 8, alignItems: "center" }}>
              <div className="field">
                <select value={s.corso_id} onChange={(e) => updateStep(i, "corso_id", e.target.value)} required>
                  <option value="">-- corso --</option>
                  {corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
                </select>
              </div>
              <div className="field" style={{ maxWidth: 100 }}>
                <input type="number" value={s.ordine} onChange={(e) => updateStep(i, "ordine", parseInt(e.target.value))} />
              </div>
              <div className="field">
                <input placeholder="richiede ordine (es. 1,2)" value={s.richiede_step_ordini.join(",")}
                       onChange={(e) => updateStep(i, "richiede_step_ordini", e.target.value.split(",").filter(Boolean).map(Number))} />
              </div>
              {form.steps.length > 1 && (
                <button type="button" className="danger btn-sm" style={{ marginBottom: 16 }} onClick={() => rimuoviStep(i)}>Rimuovi</button>
              )}
            </div>
          ))}
          <button type="button" className="secondary" onClick={addStep}>+ Aggiungi step</button>
          <div style={{ marginTop: 12 }}>
            <button type="submit">{editingId ? "Salva modifiche" : "Crea percorso"}</button>{" "}
            {editingId && <button type="button" className="secondary" onClick={annullaModifica}>Annulla</button>}
          </div>
        </form>
      </div>
      {list.map((p) => (
        <div className="card" key={p.id}>
          <div className="flex-between">
            <strong>{p.nome}</strong>
            <div>
              <span className="badge gray">{TRIGGER_LABEL[p.trigger_tipo]}</span>{" "}
              <button className="secondary btn-sm" onClick={() => iniziaModifica(p)}>Modifica</button>
            </div>
          </div>
          <p className="text-muted">{p.steps.length} step</p>
        </div>
      ))}
    </div>
  );
}
