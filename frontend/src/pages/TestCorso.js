import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { downloadFile } from "../api";

function nuovaDomanda() {
  return { testo: "", ordine: 0, opzioni: [{ testo: "", corretta: true }, { testo: "", corretta: false }] };
}

export default function TestCorso() {
  const { corsoId } = useParams();
  const [corso, setCorso] = useState(null);
  const [tests, setTests] = useState([]);
  const [form, setForm] = useState({ titolo: "", momento: "finale", soglia_superamento_pct: 60, tentativi_max: "", domande: [nuovaDomanda()] });

  function load() {
    api.get(`/corsi/${corsoId}`).then((r) => setCorso(r.data));
    api.get(`/corsi/${corsoId}/test`).then((r) => setTests(r.data));
  }
  useEffect(load, [corsoId]);

  function updateDomanda(i, field, value) {
    const copy = [...form.domande];
    copy[i] = { ...copy[i], [field]: value };
    setForm({ ...form, domande: copy });
  }
  function updateOpzione(di, oi, field, value) {
    const copy = [...form.domande];
    const opzioni = [...copy[di].opzioni];
    if (field === "corretta") {
      opzioni.forEach((o, idx) => { o.corretta = idx === oi; });
    } else {
      opzioni[oi] = { ...opzioni[oi], [field]: value };
    }
    copy[di] = { ...copy[di], opzioni };
    setForm({ ...form, domande: copy });
  }
  function addOpzione(di) {
    const copy = [...form.domande];
    copy[di].opzioni.push({ testo: "", corretta: false });
    setForm({ ...form, domande: copy });
  }
  function addDomanda() { setForm({ ...form, domande: [...form.domande, nuovaDomanda()] }); }

  async function submit(e) {
    e.preventDefault();
    await api.post(`/corsi/${corsoId}/test`, {
      ...form,
      soglia_superamento_pct: parseFloat(form.soglia_superamento_pct),
      tentativi_max: form.tentativi_max ? parseInt(form.tentativi_max) : null,
      domande: form.domande.map((d, i) => ({ ...d, ordine: i })),
    });
    setForm({ titolo: "", momento: "finale", soglia_superamento_pct: 60, tentativi_max: "", domande: [nuovaDomanda()] });
    load();
  }

  async function elimina(id) {
    if (!window.confirm("Eliminare questo test?")) return;
    await api.delete(`/test/${id}`);
    load();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Test — {corso?.titolo}</h2>
          <p>Domande a risposta singola, personalizzabili per momento (iniziale/intermedio/finale) e soglia di superamento.</p>
        </div>
      </div>

      <div className="card">
        <h3>Nuovo test</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Titolo</label><input required value={form.titolo} onChange={(e) => setForm({ ...form, titolo: e.target.value })} /></div>
            <div className="field">
              <label>Momento</label>
              <select value={form.momento} onChange={(e) => setForm({ ...form, momento: e.target.value })}>
                <option value="iniziale">Iniziale</option>
                <option value="intermedio">Intermedio</option>
                <option value="finale">Finale</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div className="field"><label>Soglia superamento (%)</label><input type="number" value={form.soglia_superamento_pct} onChange={(e) => setForm({ ...form, soglia_superamento_pct: e.target.value })} /></div>
            <div className="field"><label>Tentativi massimi (vuoto = illimitati)</label><input type="number" value={form.tentativi_max} onChange={(e) => setForm({ ...form, tentativi_max: e.target.value })} /></div>
          </div>

          {form.domande.map((d, di) => (
            <div key={di} className="card card-muted">
              <div className="field"><label>Domanda {di + 1}</label><input required value={d.testo} onChange={(e) => updateDomanda(di, "testo", e.target.value)} /></div>
              {d.opzioni.map((o, oi) => (
                <div key={oi} className="row" style={{ alignItems: "center", marginBottom: 6 }}>
                  <div className="field" style={{ marginBottom: 0 }}>
                    <input required placeholder={`Opzione ${oi + 1}`} value={o.testo} onChange={(e) => updateOpzione(di, oi, "testo", e.target.value)} />
                  </div>
                  <label style={{ display: "flex", alignItems: "center", gap: 6, width: "auto", marginBottom: 0 }}>
                    <input type="radio" style={{ width: "auto" }} checked={o.corretta} onChange={() => updateOpzione(di, oi, "corretta", true)} /> corretta
                  </label>
                </div>
              ))}
              <button type="button" className="secondary btn-sm" onClick={() => addOpzione(di)}>+ Opzione</button>
            </div>
          ))}
          <button type="button" className="secondary" onClick={addDomanda}>+ Aggiungi domanda</button>
          <div style={{ marginTop: 12 }}><button type="submit">Crea test</button></div>
        </form>
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>Titolo</th><th>Momento</th><th>Soglia</th><th>Domande</th><th></th></tr></thead>
          <tbody>
            {tests.map((t) => (
              <tr key={t.id}>
                <td>{t.titolo}</td><td>{t.momento}</td><td>{t.soglia_superamento_pct}%</td><td>{t.domande.length}</td>
                <td>
                  <button className="secondary btn-sm" onClick={() => downloadFile(`/test/${t.id}/report.csv`, `report_${t.titolo}.csv`)}>Report CSV</button>{" "}
                  <button className="danger btn-sm" onClick={() => elimina(t.id)}>Elimina</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
