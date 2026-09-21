import React, { useEffect, useState } from "react";
import api from "../api";

export default function Azienda() {
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.get("/azienda").then((r) => setForm(r.data)); }, []);

  async function submit(e) {
    e.preventDefault();
    await api.put("/azienda", form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (!form) return <div>Caricamento...</div>;

  return (
    <div>
      <h2>Azienda</h2>
      <div className="card">
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Ragione sociale</label><input value={form.ragione_sociale || ""} onChange={(e) => setForm({ ...form, ragione_sociale: e.target.value })} /></div>
            <div className="field"><label>P.IVA</label><input value={form.partita_iva || ""} onChange={(e) => setForm({ ...form, partita_iva: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Indirizzo</label><input value={form.indirizzo || ""} onChange={(e) => setForm({ ...form, indirizzo: e.target.value })} /></div>
            <div className="field"><label>Città</label><input value={form.citta || ""} onChange={(e) => setForm({ ...form, citta: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Email</label><input value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div className="field"><label>PEC</label><input value={form.pec || ""} onChange={(e) => setForm({ ...form, pec: e.target.value })} /></div>
          </div>
          <button type="submit">Salva</button>
          {saved && <span style={{ marginLeft: 10, color: "#1a7a3e" }}>Salvato</span>}
        </form>
      </div>
    </div>
  );
}
