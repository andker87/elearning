import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

const AZIONI = [
  { value: "concludi_comunque", label: "Concludi comunque" },
  { value: "concludi_scadenza_breve", label: "Concludi, ma ripeti entro N giorni" },
  { value: "rifai_test", label: "Rifai solo il test" },
  { value: "rifai_corso", label: "Rifai il corso da zero" },
];

export default function Corsi() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({
    titolo: "", descrizione: "", categoria: "", validita_mesi: "",
    ha_test_finale: false, azione_test_non_superato: "concludi_comunque", giorni_scadenza_breve: "",
  });

  function load() { api.get("/corsi").then((r) => setList(r.data)); }
  useEffect(load, []);

  async function submit(e) {
    e.preventDefault();
    await api.post("/corsi", {
      ...form,
      validita_mesi: form.validita_mesi ? parseInt(form.validita_mesi) : null,
      giorni_scadenza_breve: form.giorni_scadenza_breve ? parseInt(form.giorni_scadenza_breve) : null,
    });
    setForm({ titolo: "", descrizione: "", categoria: "", validita_mesi: "", ha_test_finale: false, azione_test_non_superato: "concludi_comunque", giorni_scadenza_breve: "" });
    load();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Corsi</h2>
          <p>Definizione del corso, indipendente da come viene erogato: la modalità si sceglie per ogni Edizione.</p>
        </div>
      </div>
      <div className="card">
        <h3>Nuovo corso</h3>
        <form onSubmit={submit}>
          <div className="field"><label>Titolo</label><input required value={form.titolo} onChange={(e) => setForm({ ...form, titolo: e.target.value })} /></div>
          <div className="field"><label>Descrizione</label><textarea value={form.descrizione} onChange={(e) => setForm({ ...form, descrizione: e.target.value })} /></div>
          <div className="row">
            <div className="field"><label>Categoria</label><input placeholder="es. sicurezza, compliance, onboarding" value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })} /></div>
            <div className="field"><label>Validità (mesi, vuoto = nessun rinnovo)</label><input type="number" value={form.validita_mesi} onChange={(e) => setForm({ ...form, validita_mesi: e.target.value })} /></div>
          </div>
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
          <button type="submit">Crea</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Titolo</th><th>Categoria</th><th>Validità</th><th>Se test non superato</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id}>
                <td>{c.titolo}</td><td>{c.categoria}</td>
                <td>{c.validita_mesi ? `${c.validita_mesi} mesi` : "senza scadenza"}</td>
                <td>{c.ha_test_finale ? <span className="badge gray">{AZIONI.find((a) => a.value === c.azione_test_non_superato)?.label}</span> : <span className="text-muted">nessun test finale</span>}</td>
                <td>{c.is_active ? <span className="badge green">attivo</span> : <span className="badge gray">disattivato</span>}</td>
                <td><Link to={`/corsi/${c.id}/test`}>Gestisci test</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
