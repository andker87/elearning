import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

function addMonths(date, months) {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}

export default function MieCorsi() {
  const [iscrizioni, setIscrizioni] = useState([]);
  const [percorsi, setPercorsi] = useState([]);

  useEffect(() => {
    api.get("/edizioni/mie/iscrizioni").then((r) => setIscrizioni(r.data));
    api.get("/percorsi/mie").then((r) => setPercorsi(r.data));
  }, []);

  const now = new Date();
  const prossime = iscrizioni.filter((i) => i.edizione_stato !== "chiusa" && i.edizione_data_inizio && new Date(i.edizione_data_inizio) >= now);
  const percorsiInCorso = percorsi.filter((p) => !p.completato);

  const inScadenza = iscrizioni
    .filter((i) => i.stato === "completato" && i.completato_at && i.corso_validita_mesi)
    .map((i) => ({ ...i, scadenza: addMonths(i.completato_at, i.corso_validita_mesi) }))
    .filter((i) => (i.scadenza - now) / (1000 * 3600 * 24) <= 30);

  const daRipetere = iscrizioni.filter((i) => i.ripeti_entro);

  return (
    <div>
      <div className="page-header"><div><h2>I miei corsi</h2><p>Le tue prossime formazioni, i percorsi in corso e le scadenze da tenere d'occhio.</p></div></div>

      {(inScadenza.length > 0 || daRipetere.length > 0) && (
        <div className="card" style={{ borderColor: "var(--yellow)", background: "var(--yellow-bg)" }}>
          <h3>Da tenere d'occhio</h3>
          {inScadenza.map((i) => (
            <p key={i.id}>⏰ <strong>{i.corso_titolo}</strong> {i.scadenza < now ? "è scaduto" : `scade il ${i.scadenza.toLocaleDateString("it-IT")}`} — è previsto un rinnovo.</p>
          ))}
          {daRipetere.map((i) => (
            <p key={i.id}>🔁 <strong>{i.corso_titolo}</strong> va ripetuto entro il {new Date(i.ripeti_entro).toLocaleDateString("it-IT")} (test non superato).</p>
          ))}
        </div>
      )}

      <div className="card">
        <h3>Prossime formazioni</h3>
        {prossime.length === 0 && <p className="empty-state">Nessuna formazione in programma.</p>}
        {prossime.map((i) => (
          <div key={i.id} className="flex-between" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
            <div>
              <strong>{i.corso_titolo}</strong>
              <div className="text-muted" style={{ fontSize: 13 }}>{new Date(i.edizione_data_inizio).toLocaleString("it-IT")} · {i.edizione_modalita}</div>
            </div>
            <Link to={`/sessioni/${i.edizione_id}`}>Apri</Link>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Percorsi formativi in corso</h3>
        {percorsiInCorso.length === 0 && <p className="empty-state">Nessun percorso in corso.</p>}
        {percorsiInCorso.map((p) => (
          <div key={p.assegnazione_id} style={{ marginBottom: 14 }}>
            <strong>{p.nome}</strong>
            <ul style={{ marginTop: 6 }}>
              {p.steps.map((s) => (
                <li key={s.step_id} style={{ color: s.completato ? "var(--green-text)" : s.sbloccato ? "var(--text)" : "var(--text3)" }}>
                  {s.completato ? "✓" : s.sbloccato ? "○" : "🔒"} {s.corso_titolo}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <p><Link to="/storico-corsi">Vedi lo storico completo dei corsi seguiti →</Link></p>
    </div>
  );
}
