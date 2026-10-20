import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import { formattaDurata } from "../durata";
import { MODALITA, quando, dove } from "../sessioni";

const ESITO = { approvata: ["green", "approvata"], rifiutata: ["red", "rifiutata"] };
const SCHEDE = [{ id: "attesa", label: "Da approvare" }, { id: "gestite", label: "Gestite" }];

// Richieste con cui i responsabili chiedono alla Formazione di iscrivere le persone del loro team a un corso «su richiesta».
export default function RichiesteIscrizione() {
  const [dati, setDati] = useState({ in_attesa: [], gestite: [] });
  const [scheda, setScheda] = useState("attesa");
  const [errore, setErrore] = useState(null);
  const [rifiuto, setRifiuto] = useState(null);     // { id, motivo }
  const [occupata, setOccupata] = useState(null);

  const carica = () => api.get("/richieste-iscrizione").then((r) => setDati(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le richieste")));
  useEffect(() => { carica(); }, []);

  async function esegui(id, fn, msg) {
    setErrore(null); setOccupata(id);
    try { await fn(); setRifiuto(null); await carica(); } catch (e) { setErrore(erroreDi(e, msg)); }
    finally { setOccupata(null); }
  }
  const dataBreve = (d) => (d ? new Date(d).toLocaleDateString("it-IT") : "—");

  return (
    <div>
      <div className="page-header"><div><h2>Richieste di iscrizione</h2>
        <p>Le richieste di iscrizione da approvare: quelle dei responsabili per le persone del loro team (corsi «su richiesta»), quelle delle persone stesse (corsi con approvazione della Formazione) e quelle di chi non ha un responsabile. Approvando, la persona viene iscritta (rispettando posti e lista d'attesa); chi ha chiesto riceve l'esito.</p></div></div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>
          {x.label}{x.id === "attesa" && dati.in_attesa.length > 0 ? ` (${dati.in_attesa.length})` : ""}</button>)}
      </div>
      {errore && <div className="error-msg">{errore}</div>}

      {scheda === "attesa" && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Richiesta</th><th>Persona</th><th>Corso e sessione</th><th>Posti</th><th></th></tr></thead>
            <tbody>
              {dati.in_attesa.map((r) => (
                <React.Fragment key={r.id}>
                  <tr>
                    <td>{dataBreve(r.created_at)}<div className="text-muted" style={{ fontSize: 12 }}>{r.autorichiesta ? "richiesta dalla persona stessa" : `di ${r.richiedente}`}</div></td>
                    <td><strong>{r.persona}</strong><div className="text-muted" style={{ fontSize: 12 }}>{r.ufficio || "senza ufficio"}</div></td>
                    <td>
                      <strong>{r.corso_titolo}</strong> <span className="badge gray">{MODALITA[r.modalita] || r.modalita}</span>
                      <div className="text-muted" style={{ fontSize: 12 }}>{quando(r)} · {dove(r)}{r.durata_effettiva_minuti ? ` · ${formattaDurata(r.durata_effettiva_minuti)}` : ""}</div>
                    </td>
                    <td>{r.posti_liberi === null ? <span className="text-muted">illimitati</span> : r.posti_liberi > 0 ? `${r.posti_liberi} liberi` : <span className="badge yellow">esauriti</span>}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", whiteSpace: "nowrap" }}>
                        <button type="button" className="btn-sm" disabled={occupata === r.id} onClick={() => esegui(r.id, () => api.put(`/richieste-iscrizione/${r.id}/approva`), "Richiesta non approvata")}>Approva</button>
                        <button type="button" className="danger btn-sm" disabled={occupata === r.id} onClick={() => setRifiuto(rifiuto?.id === r.id ? null : { id: r.id, motivo: "" })}>Rifiuta</button>
                      </div>
                    </td>
                  </tr>
                  {rifiuto?.id === r.id && (
                    <tr>
                      <td colSpan={5} style={{ background: "var(--bg3)" }}>
                        <form style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", padding: "6px 0" }}
                          onSubmit={(e) => { e.preventDefault(); esegui(r.id, () => api.put(`/richieste-iscrizione/${r.id}/rifiuta`, { motivo: rifiuto.motivo }), "Richiesta non rifiutata"); }}>
                          <div className="field" style={{ flex: 1, minWidth: 260, margin: 0 }}>
                            <label htmlFor={`m-${r.id}`}>Motivo (facoltativo, lo legge chi ha chiesto)</label>
                            <input id={`m-${r.id}`} autoFocus value={rifiuto.motivo} onChange={(e) => setRifiuto({ ...rifiuto, motivo: e.target.value })} placeholder="es. posti riservati ad altri uffici" />
                          </div>
                          <button type="submit" className="danger">Conferma il rifiuto</button>
                          <button type="button" className="secondary" onClick={() => setRifiuto(null)}>Annulla</button>
                        </form>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {dati.in_attesa.length === 0 && <tr><td colSpan={5} className="text-muted">Nessuna richiesta in attesa.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {scheda === "gestite" && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Gestita il</th><th>Persona</th><th>Corso</th><th>Richiesta da</th><th>Esito</th></tr></thead>
            <tbody>
              {dati.gestite.map((r) => {
                const [classe, testo] = ESITO[r.stato] || ["gray", r.stato];
                return (
                  <tr key={r.id}>
                    <td>{dataBreve(r.valutata_at)}</td>
                    <td>{r.persona}</td>
                    <td>{r.corso_titolo}<div className="text-muted" style={{ fontSize: 12 }}>{quando(r)}</div></td>
                    <td>{r.autorichiesta ? "la persona stessa" : r.richiedente}</td>
                    <td><span className={`badge ${classe}`}>{testo}</span>{r.motivo_rifiuto && <div className="text-muted" style={{ fontSize: 12 }}>{r.motivo_rifiuto}</div>}</td>
                  </tr>
                );
              })}
              {dati.gestite.length === 0 && <tr><td colSpan={5} className="text-muted">Ancora nessuna richiesta gestita.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
