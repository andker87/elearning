import React, { useEffect, useState } from "react";
import api from "../api";
import AlberoOrigine from "../components/AlberoOrigine";

const PERIODI = [{ value: "", label: "Periodo..." }, { value: "mese", label: "Mese" }, { value: "trimestre", label: "Trimestre" },
                 { value: "semestre", label: "Semestre" }, { value: "anno", label: "Anno" }];
const STATO_LABEL = { in_revisione: "In revisione", approvata_hr: "Inviata (in carico alla Formazione)", rifiutata: "Rifiutata", fusa: "Unita ad altre richieste" };
const STATO_BADGE = { in_revisione: "gray", approvata_hr: "blue", rifiutata: "red" };
const RIGA_VUOTA = { argomento: "", periodo: "", riferimento_periodo: "", numero_persone_stimate: "", note: "" };
const dataIt = (d) => new Date(d).toLocaleDateString("it-IT");

// Una o piu' esigenze in un solo invio: una riga per argomento, "+" per aggiungerne.
function RigheForm({ onSubmit, etichettaInvio = "Invia" }) {
  const [righe, setRighe] = useState([{ ...RIGA_VUOTA }]);
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);
  const imposta = (i, k, v) => setRighe(righe.map((r, n) => (n === i ? { ...r, [k]: v } : r)));
  const compilate = righe.filter((r) => r.argomento.trim());

  async function submit(e) {
    e.preventDefault();
    if (!compilate.length) { setErrore("Indica almeno un argomento"); return; }
    setErrore(null); setInvio(true);
    try {
      await onSubmit(compilate.map((r) => ({
        argomento: r.argomento.trim(), periodo: r.periodo || null, riferimento_periodo: r.riferimento_periodo.trim() || null,
        numero_persone_stimate: r.numero_persone_stimate ? parseInt(r.numero_persone_stimate, 10) : null, note: r.note.trim() || null,
      })));
      setRighe([{ ...RIGA_VUOTA }]);
    } catch (err) {
      setErrore(err.response?.data?.detail || "Errore nell'invio");
    } finally { setInvio(false); }
  }

  return (
    <form onSubmit={submit} className="righe-form">
      <div className="righe-intestazione">
        <span>Argomento</span><span>Periodo</span><span>Riferimento</span><span>N. persone</span><span>Note</span><span />
      </div>
      {righe.map((r, i) => (
        <div className="riga-esigenza" key={i}>
          <input aria-label="Argomento" placeholder="Es. Privacy per i nuovi assunti" value={r.argomento} onChange={(e) => imposta(i, "argomento", e.target.value)} />
          <select aria-label="Periodo" value={r.periodo} onChange={(e) => imposta(i, "periodo", e.target.value)}>
            {PERIODI.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <input aria-label="Riferimento" placeholder="Es. Q2 2027" value={r.riferimento_periodo} onChange={(e) => imposta(i, "riferimento_periodo", e.target.value)} />
          <input aria-label="Numero di persone" type="number" min="0" placeholder="N." value={r.numero_persone_stimate} onChange={(e) => imposta(i, "numero_persone_stimate", e.target.value)} />
          <input aria-label="Note" placeholder="Considerazioni su questa esigenza" value={r.note} onChange={(e) => imposta(i, "note", e.target.value)} />
          <button type="button" className="secondary btn-sm riga-rimuovi" title="Togli questa riga" aria-label="Togli questa riga"
                  disabled={righe.length === 1} onClick={() => setRighe(righe.filter((_, n) => n !== i))}>✕</button>
        </div>
      ))}
      <div className="righe-azioni">
        <button type="button" className="secondary btn-sm" onClick={() => setRighe([...righe, { ...RIGA_VUOTA }])}>+ Aggiungi un'altra esigenza</button>
        <button type="submit" className="btn-sm" disabled={invio || !compilate.length}>
          {compilate.length > 1 ? `${etichettaInvio} (${compilate.length} esigenze)` : etichettaInvio}
        </button>
      </div>
      {errore && <div className="error-msg">{errore}</div>}
    </form>
  );
}

function InvitoUfficio({ invito, onRispondi, onDelega }) {
  const [aperto, setAperto] = useState(false);
  const ha_figli = invito.sotto_uffici.length > 0;
  return (
    <div className="invito-ufficio">
      <div className="invito-testata">
        <strong>{invito.ufficio_nome}</strong>
        {invito.stato === "da_decidere" && <span className="badge yellow">Da decidere</span>}
        {invito.stato === "delegato" && <span className="badge accent">Inoltrata ai sotto-uffici</span>}
        {invito.stato === "risposto" && <span className="badge green">Risposta inviata ({invito.risposte} {invito.risposte === 1 ? "esigenza" : "esigenze"})</span>}
      </div>

      {invito.stato === "da_decidere" && (
        <>
          <div className="scelte">
            <div className={`scelta ${aperto ? "attiva" : ""}`}>
              <strong>Rispondo io</strong>
              <p>Indichi tu le esigenze di formazione di {invito.ufficio_nome}{ha_figli ? " e dei suoi sotto-uffici" : ""}.</p>
              <button type="button" className="btn-sm" onClick={() => setAperto(!aperto)}>{aperto ? "Chiudi il modulo" : "Compila le esigenze"}</button>
            </div>
            {ha_figli && (
              <div className="scelta">
                <strong>Chiedo ai sotto-uffici</strong>
                <p>L'invito passa ai responsabili di {invito.sotto_uffici.join(", ")}. Le loro proposte arriveranno da te da approvare, prima di salire alla Formazione.</p>
                <button type="button" className="secondary btn-sm" onClick={() => onDelega(invito)}>Inoltra ai sotto-uffici</button>
              </div>
            )}
          </div>
          {!ha_figli && <p className="text-muted" style={{ fontSize: 12, margin: "6px 0 0" }}>Il tuo ufficio non ha sotto-uffici: la risposta la dai tu.</p>}
          {aperto && <RigheForm etichettaInvio="Invia la risposta" onSubmit={async (righe) => { await onRispondi(invito, righe); setAperto(false); }} />}
        </>
      )}
      {invito.stato === "delegato" && (
        <p className="text-muted" style={{ fontSize: 13, margin: "6px 0 0" }}>
          Hai chiesto ai responsabili di {invito.sotto_uffici.join(", ")}. Quando rispondono, le proposte compaiono qui sotto in "Da valutare".
        </p>
      )}
      {invito.stato === "risposto" && (
        <p className="text-muted" style={{ fontSize: 13, margin: "6px 0 0" }}>Le trovi in fondo, in "Le mie richieste", con lo stato di avanzamento.</p>
      )}
    </div>
  );
}

const normalizza = (t) => (t || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");

// Richieste dei sotto-uffici da valutare: raggruppate per argomento, con approvazione in blocco
// e fusione delle richieste simili (le originali restano consultabili da chiunque le riguardi).
function DaValutare({ righe, onCambiato, avvisa }) {
  const [sel, setSel] = useState(new Set());
  const [rifiuto, setRifiuto] = useState(null);       // null | testo del motivo
  const [unione, setUnione] = useState(null);         // null | form
  const [provenienza, setProvenienza] = useState(null);
  const [errore, setErrore] = useState(null);

  const gruppi = [];
  righe.forEach((r) => {
    const k = normalizza(r.argomento);
    let g = gruppi.find((x) => x.chiave === k);
    if (!g) { g = { chiave: k, nome: r.argomento, righe: [] }; gruppi.push(g); }
    g.righe.push(r);
  });
  const selezionate = righe.filter((r) => sel.has(r.id));
  const alterna = (id) => { const n = new Set(sel); n.has(id) ? n.delete(id) : n.add(id); setSel(n); };
  const alternaGruppo = (g) => { const n = new Set(sel); const tutte = g.righe.every((r) => n.has(r.id)); g.righe.forEach((r) => (tutte ? n.delete(r.id) : n.add(r.id))); setSel(n); };
  const dopo = (testo) => { setSel(new Set()); setRifiuto(null); setUnione(null); setErrore(null); avvisa(testo); onCambiato(); };
  const errorePre = (err) => setErrore(err.response?.data?.detail || "Operazione non riuscita");

  async function approva() { try { const r = await api.put("/fabbisogno/richieste/approva-multiple", { ids: selezionate.map((x) => x.id) }); dopo(`${r.data.approvate} richieste approvate: proseguono verso l'alto.`); } catch (e) { errorePre(e); } }
  async function rifiuta() { try { const r = await api.put("/fabbisogno/richieste/rifiuta-multiple", { ids: selezionate.map((x) => x.id), motivo: rifiuto }); dopo(`${r.data.rifiutate} richieste rifiutate.`); } catch (e) { errorePre(e); } }
  function apriUnione(rs) {
    const persone = rs.reduce((t, x) => t + (x.numero_persone_stimate || 0), 0);
    const nomi = {}; rs.forEach((x) => { nomi[x.argomento.trim()] = (nomi[x.argomento.trim()] || 0) + 1; });
    const nome = Object.keys(nomi).sort((a, b) => nomi[b] - nomi[a] || (/^[A-ZÀ-Ý]/.test(b) ? 1 : 0) - (/^[A-ZÀ-Ý]/.test(a) ? 1 : 0))[0];
    setUnione({ ids: rs.map((x) => x.id), argomento: nome, persone: String(persone), note: "", righe: rs }); setErrore(null);
  }
  async function confermaUnione(e) {
    e.preventDefault();
    try {
      const r = await api.post("/fabbisogno/richieste/unisci", { ids: unione.ids, argomento: unione.argomento, note: unione.note || null,
        numero_persone_stimate: unione.persone === "" ? null : parseInt(unione.persone, 10) });
      dopo(`Unite ${unione.ids.length} richieste in «${r.data.argomento}». Chi le ha scritte è stato avvisato.`);
    } catch (err) { errorePre(err); }
  }

  return (
    <div className="card">
      <h3>Da valutare: proposte dei tuoi sotto-uffici</h3>
      <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
        Seleziona le richieste per approvarle o rifiutarle insieme. Se più uffici chiedono lo stesso tema, puoi <strong>unirle</strong> in una sola: sale al posto delle originali, che restano sempre consultabili con ufficio, autore e numeri.
      </p>
      {errore && <div className="error-msg">{errore}</div>}

      {selezionate.length > 0 && (
        <div className="barra-selezione">
          <strong>{selezionate.length} {selezionate.length === 1 ? "selezionata" : "selezionate"}</strong>
          <button type="button" className="btn-sm" onClick={approva}>Approva</button>
          {rifiuto === null ? <button type="button" className="danger btn-sm" onClick={() => setRifiuto("")}>Rifiuta...</button> : (
            <>
              <input style={{ minWidth: 220 }} autoFocus placeholder="Motivo (lo vede chi ha scritto la richiesta)" value={rifiuto} onChange={(e) => setRifiuto(e.target.value)} />
              <button type="button" className="danger btn-sm" onClick={rifiuta}>Conferma il rifiuto</button>
              <button type="button" className="secondary btn-sm" onClick={() => setRifiuto(null)}>Annulla</button>
            </>
          )}
          {selezionate.length >= 2 && <button type="button" className="secondary btn-sm" onClick={() => apriUnione(selezionate)}>Unisci in una sola...</button>}
          <button type="button" className="secondary btn-sm" onClick={() => { setSel(new Set()); setRifiuto(null); }}>Deseleziona</button>
        </div>
      )}

      {unione && (
        <form className="card card-muted" onSubmit={confermaUnione}>
          <h3>Unisci {unione.ids.length} richieste</h3>
          <ul style={{ margin: "0 0 .8rem", paddingLeft: "1.2rem", fontSize: 13 }}>
            {unione.righe.map((x) => <li key={x.id}><strong>{x.ufficio_origine_nome}</strong>: «{x.argomento}» — {x.numero_persone_stimate ?? "?"} persone{x.note ? ` — ${x.note}` : ""}</li>)}
          </ul>
          <div className="row">
            <div className="field" style={{ flex: 3 }}><label>Argomento della richiesta unita</label><input required value={unione.argomento} onChange={(e) => setUnione({ ...unione, argomento: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>Persone in totale</label><input type="number" min="0" value={unione.persone} onChange={(e) => setUnione({ ...unione, persone: e.target.value })} /></div>
          </div>
          <p className="text-muted" style={{ fontSize: 12, marginTop: -6 }}>Il totale è la somma delle richieste: correggilo se alcune persone si ripetono tra gli uffici.</p>
          <div className="field"><label>Nota (facoltativa)</label><input placeholder="Considerazioni su questa richiesta unita" value={unione.note} onChange={(e) => setUnione({ ...unione, note: e.target.value })} /></div>
          <p className="text-muted" style={{ fontSize: 12 }}>Le richieste originali non si perdono: chi le ha scritte riceve un avviso e può sempre vedere come sono state unite. Finché nessuno sopra di te le ha valutate, puoi annullare l'unione.</p>
          <button type="submit">Unisci</button>{" "}
          <button type="button" className="secondary" onClick={() => setUnione(null)}>Annulla</button>
        </form>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th style={{ width: 32 }}></th><th>Ufficio</th><th>Argomento</th><th>Periodo</th><th>Persone</th><th>Note</th><th></th></tr></thead>
          <tbody>
            {gruppi.map((g) => (
              <React.Fragment key={g.chiave}>
                {g.righe.length > 1 && (
                  <tr className="gruppo-testata">
                    <td><input type="checkbox" aria-label={`Seleziona le richieste «${g.nome}»`} checked={g.righe.every((r) => sel.has(r.id))} onChange={() => alternaGruppo(g)} /></td>
                    <td colSpan={5}>«{g.nome}» — {g.righe.length} richieste · {g.righe.reduce((t, r) => t + (r.numero_persone_stimate || 0), 0)} persone</td>
                    <td><button type="button" className="secondary btn-sm" onClick={() => apriUnione(g.righe)}>Unisci queste</button></td>
                  </tr>
                )}
                {g.righe.map((r) => (
                  <React.Fragment key={r.id}>
                    <tr>
                      <td><input type="checkbox" aria-label={`Seleziona ${r.argomento}`} checked={sel.has(r.id)} onChange={() => alterna(r.id)} /></td>
                      <td>{r.e_unione ? r.uffici_origine.join(", ") : r.ufficio_origine_nome}</td>
                      <td>
                        {r.argomento}
                        {r.e_unione && <> <span className="badge blue">unione di {r.n_origini}</span> <button type="button" className="secondary btn-sm" onClick={() => setProvenienza(provenienza === r.id ? null : r.id)}>{provenienza === r.id ? "Nascondi" : "Provenienza"}</button></>}
                      </td>
                      <td>{r.riferimento_periodo || r.periodo || "—"}</td>
                      <td>{r.numero_persone_stimate ?? "—"}</td>
                      <td>{r.note || "—"}</td>
                      <td></td>
                    </tr>
                    {provenienza === r.id && <tr className="dettaglio-gruppo"><td></td><td colSpan={6}><AlberoOrigine id={r.id} /></td></tr>}
                  </React.Fragment>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Fabbisogno() {
  const [campagne, setCampagne] = useState([]);
  const [daRevisionare, setDaRevisionare] = useState([]);
  const [mieRichieste, setMieRichieste] = useState([]);
  const [uffici, setUffici] = useState([]);
  const [ufficioSpontanea, setUfficioSpontanea] = useState("");
  const [msg, setMsg] = useState(null);
  const [provenienza, setProvenienza] = useState(null);
  const user = JSON.parse(localStorage.getItem("user") || "null");

  function load() {
    api.get("/fabbisogno/inviti/miei").then((r) => setCampagne(r.data));
    api.get("/fabbisogno/richieste/da-revisionare").then((r) => setDaRevisionare(r.data));
    api.get("/fabbisogno/richieste/mie").then((r) => setMieRichieste(r.data));
  }
  useEffect(() => {
    load();
    if (user?.id) api.get(`/auth/users/${user.id}/uffici-guidati`).then((r) => { setUffici(r.data); if (r.data.length) setUfficioSpontanea(r.data[0].id); });
  }, []); // eslint-disable-line

  const avvisa = (testo) => { setMsg(testo); setTimeout(() => setMsg(null), 6000); };
  async function delega(invito) {
    if (!window.confirm(`Inoltrare l'invito ai sotto-uffici di ${invito.ufficio_nome} (${invito.sotto_uffici.join(", ")})? Poi non potrai più rispondere tu per questa campagna.`)) return;
    await api.post(`/fabbisogno/inviti/${invito.id}/delega`);
    avvisa("Invito inoltrato ai sotto-uffici."); load();
  }
  async function rispondi(invito, righe) {
    await api.post(`/fabbisogno/inviti/${invito.id}/rispondi`, { righe });
    avvisa(`Risposta inviata: ${righe.length} ${righe.length === 1 ? "esigenza" : "esigenze"}.`); load();
  }
  async function creaSpontanea(righe) {
    await api.post("/fabbisogno/richieste", { righe, ufficio_id: ufficioSpontanea });
    avvisa(`Richiesta inviata: ${righe.length} ${righe.length === 1 ? "esigenza" : "esigenze"}.`); load();
  }
  async function scomponi(r) {
    if (!window.confirm(`Annullare l'unione «${r.argomento}»? Le ${r.n_origini} richieste tornano da valutare, come prima.`)) return;
    try { await api.post(`/fabbisogno/richieste/${r.id}/scomponi`); avvisa("Unione annullata: le richieste sono di nuovo da valutare."); load(); }
    catch (err) { avvisa(err.response?.data?.detail || "Non è stato possibile annullare l'unione"); }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Richieste di formazione</h2><p>Segnala le esigenze di formazione del tuo ufficio per il periodo successivo: rispondendo a una campagna della Formazione o, in qualsiasi momento, con una richiesta spontanea.</p></div></div>
      {msg && <div className="card" style={{ color: "var(--green-text)", background: "var(--green-bg)", borderColor: "transparent" }}>{msg}</div>}

      {campagne.map((c) => (
        <div className="card" key={c.campagna_id}>
          <div className="flex-between" style={{ alignItems: "flex-start", gap: 12 }}>
            <div>
              <h3 style={{ marginBottom: 2 }}>Campagna: {c.titolo}</h3>
              {c.descrizione && <p className="text-muted" style={{ margin: 0, fontSize: 13 }}>{c.descrizione}</p>}
            </div>
            {c.scadenza && <span className="badge gray">Scade il {dataIt(c.scadenza)}</span>}
          </div>
          {c.inviti.map((i) => <InvitoUfficio key={i.id} invito={i} onRispondi={rispondi} onDelega={delega} />)}
        </div>
      ))}

      {daRevisionare.length > 0 && <DaValutare righe={daRevisionare} onCambiato={() => { load(); }} avvisa={avvisa} />}

      {uffici.length > 0 && (
        <div className="card">
          <h3>Richiesta spontanea</h3>
          <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>Un'esigenza che non aspetta una campagna. Segue lo stesso percorso: sale ai responsabili sopra di te fino alla Formazione.</p>
          {uffici.length > 1 && (
            <div className="field" style={{ maxWidth: 320 }}>
              <label>Per quale tuo ufficio</label>
              <select value={ufficioSpontanea} onChange={(e) => setUfficioSpontanea(e.target.value)}>
                {uffici.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </div>
          )}
          <RigheForm etichettaInvio="Invia la richiesta" onSubmit={creaSpontanea} />
        </div>
      )}

      <div className="card">
        <h3>Le mie richieste</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Ufficio</th><th>Argomento</th><th>Periodo</th><th>N. persone</th><th>Origine</th><th>Stato</th><th></th></tr></thead>
            <tbody>
              {mieRichieste.map((r) => (
                <React.Fragment key={r.id}>
                  <tr>
                    <td>{r.ufficio_origine_nome}</td>
                    <td>
                      {r.argomento}
                      {r.e_unione && <> <span className="badge blue">unione di {r.n_origini} richieste</span></>}
                      {r.note && <><br /><span className="text-muted" style={{ fontSize: 12 }}>{r.note}</span></>}
                      {r.unita_in && <><br /><span className="text-muted" style={{ fontSize: 12 }}>Unita ad altre in «{r.unita_in.argomento}» da {r.unita_in.ufficio_nome} il {dataIt(r.unita_in.data)}</span></>}
                    </td>
                    <td>{r.riferimento_periodo || r.periodo || "—"}</td>
                    <td>{r.numero_persone_stimate ?? "—"}</td>
                    <td>{r.campagna_titolo ? `Campagna ${r.campagna_titolo}` : "Spontanea"}</td>
                    <td>
                      <span className={`badge ${STATO_BADGE[r.stato_effettivo]}`}>{STATO_LABEL[r.stato_effettivo]}</span>
                      {r.stato_effettivo === "in_revisione" && r.presso_effettivo_nome && <><br /><span className="text-muted" style={{ fontSize: 12 }}>presso {r.presso_effettivo_nome}</span></>}
                      {r.motivo_rifiuto_effettivo && <><br /><span className="text-muted" style={{ fontSize: 12 }}>{r.motivo_rifiuto_effettivo}</span></>}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {(r.e_unione || r.unita_in) && <button type="button" className="secondary btn-sm" onClick={() => setProvenienza(provenienza === r.id ? null : r.id)}>{provenienza === r.id ? "Nascondi" : "Provenienza"}</button>}
                      {r.e_unione && r.stato === "in_revisione" && <> <button type="button" className="secondary btn-sm" onClick={() => scomponi(r)}>Annulla unione</button></>}
                    </td>
                  </tr>
                  {provenienza === r.id && <tr className="dettaglio-gruppo"><td colSpan={7}><AlberoOrigine id={r.unita_in ? r.unita_in.id : r.id} /></td></tr>}
                </React.Fragment>
              ))}
              {mieRichieste.length === 0 && <tr><td colSpan={7} className="empty-state">Nessuna richiesta ancora inviata.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
