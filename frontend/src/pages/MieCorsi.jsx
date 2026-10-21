import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { STATO_PASSO } from "../components/PersonePercorso";
import { quando } from "../sessioni";

const MODALITA_PERCORSO = { libero: "libero", sequenziale: "uno dopo l'altro", propedeuticita: "con propedeuticità" };

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
  const prossime = iscrizioni.filter((i) => (i.stato === "iscritto" || i.stato === "in_lista_attesa") && i.edizione_stato !== "chiusa" && i.edizione_data_inizio && new Date(i.edizione_data_inizio) >= now);
  const inCorsoLibero = iscrizioni.filter((i) => i.edizione_sempre_aperta && i.stato === "iscritto" && i.edizione_stato !== "chiusa");     // corsi sempre disponibili iniziati e non finiti
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
              <strong>{i.corso_titolo}</strong>{i.stato === "in_lista_attesa" && <span className="badge yellow" style={{ marginLeft: 8 }}>in lista d'attesa</span>}
              <div className="text-muted" style={{ fontSize: 13 }}>{new Date(i.edizione_data_inizio).toLocaleString("it-IT")} · {i.edizione_modalita}</div>
            </div>
            <Link to={`/sessioni/${i.edizione_id}?segui=1`}>Apri</Link>
          </div>
        ))}
      </div>

      {inCorsoLibero.length > 0 && (
        <div className="card">
          <h3>Corsi che stai seguendo</h3>
          {inCorsoLibero.map((i) => (
            <div key={i.id} className="flex-between" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
              <div><strong>{i.corso_titolo}</strong><div className="text-muted" style={{ fontSize: 13 }}>Sempre disponibile · l'attestato arriva quando lo completi</div></div>
              <Link to={`/sessioni/${i.edizione_id}?segui=1`}>Continua</Link>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3>Percorsi formativi in corso</h3>
        {percorsiInCorso.length === 0 && <p className="empty-state">Nessun percorso in corso.</p>}
        {percorsiInCorso.map((p) => (
          <div key={p.assegnazione_id} style={{ marginBottom: 14 }}>
            <strong>{p.nome}</strong> <span className="text-muted" style={{ fontSize: 12 }}>({MODALITA_PERCORSO[p.modalita] || p.modalita})</span>
            <ul style={{ marginTop: 6, listStyle: "none", paddingLeft: 0 }}>
              {p.steps.map((s) => {
                const [classe, testo] = STATO_PASSO[s.stato] || ["gray", s.stato];
                return (
                  <li key={s.step_id} style={{ padding: "3px 0", color: s.stato === "bloccato" ? "var(--text3)" : "var(--text)" }}>
                    {s.completato ? "✓" : s.stato === "bloccato" ? "🔒" : "○"} {s.corso_titolo}{" "}
                    <span className={`badge ${classe}`}>{testo}</span>{" "}
                    {s.edizione_id && !s.completato && <>
                      <span className="text-muted" style={{ fontSize: 12 }}>{quando({ data_inizio: s.data_inizio, sempre_aperta: s.sempre_aperta })} </span>
                      <Link to={`/sessioni/${s.edizione_id}?segui=1`}>{s.sempre_aperta ? "Inizia" : "Apri"}</Link>
                    </>}
                    {s.stato === "bloccato" && s.richiede_titoli.length > 0 && <span className="text-muted" style={{ fontSize: 12 }}> — prima: {s.richiede_titoli.join(", ")}</span>}
                    {s.stato === "in_attesa_sessione" && <span className="text-muted" style={{ fontSize: 12 }}> — appena c'è una sessione verrai iscritto</span>}
                    {s.stato === "da_rifare" && <span className="text-muted" style={{ fontSize: 12 }}> — la Formazione ti iscriverà di nuovo</span>}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <p><Link to="/catalogo">Cerca altri corsi nel catalogo →</Link> · <Link to="/storico-corsi">Vedi lo storico completo dei corsi seguiti →</Link></p>
    </div>
  );
}
