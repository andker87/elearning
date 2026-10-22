import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import { Capsule } from "../components/Capsule";
import { formattaDurata } from "../durata";
import { MODALITA, STATI, STATI_ISCRIZIONE, quando, dove } from "../sessioni";
import { dataIt } from "../date";

const SCHEDE = [
  { id: "team", label: "Il mio team" }, { id: "formazione", label: "Formazione del team" },
  { id: "corsi", label: "Corsi disponibili" }, { id: "approvare", label: "Richieste e approvazioni" },
];
const MODO = { diretta: ["iscrizione diretta", "Puoi iscrivere direttamente le tue persone"], su_richiesta: ["su richiesta", "Chiedi l'iscrizione: la Formazione approva"] };
const utenteCorrente = () => { try { return JSON.parse(localStorage.getItem("user") || "{}") || {}; } catch { return {}; } };   // letto a ogni uso: dopo un cambio di accesso non resta quello vecchio
const capsulaStato = (s) => { const [c, t] = STATI_ISCRIZIONE[s] || ["gray", s]; return <span className={`badge ${c}`}>{t}</span>; };

// --- scheda 1: il team ad albero ---------------------------------------------------------------------

function SituazioneFormativa({ personaId }) {
  const [d, setD] = useState(null);
  const [errore, setErrore] = useState(null);
  useEffect(() => { api.get(`/team/persone/${personaId}/formazione`).then((r) => setD(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare la formazione"))); }, [personaId]);
  if (errore) return <div className="error-msg">{errore}</div>;
  if (!d) return <p className="text-muted">Caricamento...</p>;
  const prossime = d.iscrizioni.filter((i) => ["iscritto", "in_lista_attesa"].includes(i.stato) && i.edizione_stato !== "chiusa");
  const fatte = d.iscrizioni.filter((i) => ["completato", "non_completato"].includes(i.stato));
  return (
    <div style={{ padding: "8px 0 4px" }}>
      <strong>Sessioni a cui partecipa</strong>
      {prossime.length === 0 && d.richieste_in_attesa.length === 0 ? <p className="text-muted" style={{ margin: "4px 0 10px" }}>Nessuna sessione in programma.</p> : (
        <ul style={{ margin: "4px 0 10px", paddingLeft: "1.2rem" }}>
          {prossime.map((i) => <li key={i.edizione_id}>{i.corso_titolo} — {quando(i)} · {dove(i)}{i.durata_effettiva_minuti ? ` · ${formattaDurata(i.durata_effettiva_minuti)}` : ""} {capsulaStato(i.stato)}</li>)}
          {d.richieste_in_attesa.map((r) => <li key={r.edizione_id}>{r.corso_titolo} — {dataIt(r.data_inizio)} {capsulaStato("richiesta_in_attesa")}</li>)}
        </ul>
      )}
      <strong>Corsi svolti</strong>
      {fatte.length === 0 ? <p className="text-muted" style={{ margin: "4px 0" }}>Ancora nessun corso concluso.</p> : (
        <ul style={{ margin: "4px 0", paddingLeft: "1.2rem" }}>
          {fatte.map((i) => (
            <li key={i.edizione_id}>{i.corso_titolo} {capsulaStato(i.stato)} — {dataIt(i.completato_at)}
              {i.scadenza && <> · {i.scaduto ? <span className="badge red">scaduto il {dataIt(i.scadenza)}</span> : i.in_scadenza ? <span className="badge yellow">scade il {dataIt(i.scadenza)}</span> : <span className="text-muted">valido fino al {dataIt(i.scadenza)}</span>}</>}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Ufficio({ n, aperta, setAperta }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", padding: "6px 0" }}>
        <span className="badge" style={{ background: n.color, color: "#fff", fontSize: ".82rem" }}>{n.name}</span>
        <span className="text-muted" style={{ fontSize: 13 }}>{n.responsabile ? `responsabile: ${n.responsabile.nome}` : "senza responsabile"}{n.e_mio ? " (tu)" : ""}</span>
      </div>
      <div style={{ marginLeft: 14, paddingLeft: 14, borderLeft: "2px solid var(--border)" }}>
        {n.persone.length === 0 && <p className="text-muted" style={{ margin: "2px 0", fontSize: 13 }}>Nessuna persona in questo ufficio.</p>}
        {n.persone.map((p) => (
          <div key={p.id} style={{ borderBottom: "1px solid var(--border)", padding: "6px 0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <strong>{p.full_name}</strong>
              {p.e_responsabile && <span className="badge gray">responsabile</span>}
              <Capsule utente={p} />
              {p.mansioni.map((m) => <span key={m.id} className="badge" style={{ background: m.color, color: "#fff" }}>{m.name}</span>)}
              <span style={{ flex: 1 }} />
              {p.id === utenteCorrente().id ? <span className="badge gray">sei tu</span> : (
                <button type="button" className="secondary btn-sm" onClick={() => setAperta(aperta === p.id ? null : p.id)}>{aperta === p.id ? "Chiudi" : "Situazione formativa"}</button>
              )}
            </div>
            {aperta === p.id && <SituazioneFormativa personaId={p.id} />}
          </div>
        ))}
        {n.figli.map((f) => <Ufficio key={f.id} n={f} aperta={aperta} setAperta={setAperta} />)}
      </div>
    </div>
  );
}

function SchedaTeam({ org }) {
  const [aperta, setAperta] = useState(null);
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Gli uffici che guidi <span className="text-muted" style={{ fontSize: 13, fontWeight: 400 }}>({org.totale_persone} persone)</span></h3>
      {org.uffici.map((n) => <Ufficio key={n.id} n={n} aperta={aperta} setAperta={setAperta} />)}
    </div>
  );
}

// --- scheda 2: la formazione del team ---------------------------------------------------------------

function SchedaFormazione() {
  const [vista, setVista] = useState("sessione");
  const [concluse, setConcluse] = useState(false);
  const [righe, setRighe] = useState(null);
  const [errore, setErrore] = useState(null);
  useEffect(() => { api.get("/team/sessioni", { params: { concluse } }).then((r) => setRighe(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le sessioni del team"))); }, [concluse]);
  if (errore) return <div className="error-msg">{errore}</div>;
  if (!righe) return <p className="text-muted">Caricamento...</p>;
  const perPersona = {};
  righe.forEach((s) => s.persone.forEach((p) => {       // per identificativo, non per nome: due omonimi restano due persone
    const sc = perPersona[p.user_id] = perPersona[p.user_id] || { nome: p.nome, sessioni: [] };
    sc.sessioni.push({ ...s, stato_persona: p.stato });
  }));
  const persone = Object.keys(perPersona).sort((a, b) => perPersona[a].nome.localeCompare(perPersona[b].nome, "it", { sensitivity: "base" }));
  const dettaglio = (s) => <>{quando(s)} · {dove(s)}{s.durata_effettiva_minuti ? ` · ${formattaDurata(s.durata_effettiva_minuti)}` : ""}</>;
  return (
    <>
      <div className="card" style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
        <span>
          <label style={{ marginRight: 8 }}><input type="radio" name="vista" checked={vista === "sessione"} onChange={() => setVista("sessione")} style={{ width: "auto", marginRight: 4 }} />Per sessione</label>
          <label><input type="radio" name="vista" checked={vista === "persona"} onChange={() => setVista("persona")} style={{ width: "auto", marginRight: 4 }} />Per persona</label>
        </span>
        <label><input type="checkbox" checked={concluse} onChange={(e) => setConcluse(e.target.checked)} style={{ width: "auto", marginRight: 6 }} />Includi le sessioni concluse</label>
        <span className="text-muted" style={{ fontSize: 13 }} aria-live="polite">{righe.length} {righe.length === 1 ? "sessione" : "sessioni"} con persone del tuo team</span>
      </div>
      {righe.length === 0 && <p className="empty-state">Nessuna persona del tuo team è iscritta a sessioni {concluse ? "" : "in programma"}.</p>}
      {vista === "sessione" && righe.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Corso</th><th>Quando e dove</th><th>Modalità</th><th>Stato</th><th>Le tue persone</th></tr></thead>
            <tbody>
              {righe.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.corso_titolo}</strong></td>
                  <td>{dettaglio(s)}</td>
                  <td><span className="badge gray">{MODALITA[s.modalita] || s.modalita}</span></td>
                  <td><span className={`badge ${(STATI[s.stato] || ["gray"])[0]}`}>{(STATI[s.stato] || [, s.stato])[1]}</span></td>
                  <td>{s.persone.map((p) => <div key={p.user_id}>{p.nome} {capsulaStato(p.stato)}</div>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {vista === "persona" && persone.map((id) => (
        <div className="card" key={id}>
          <h4 style={{ marginTop: 0 }}>{perPersona[id].nome}</h4>
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {perPersona[id].sessioni.map((s) => <li key={s.id}><strong>{s.corso_titolo}</strong> — {dettaglio(s)} {capsulaStato(s.stato_persona)}</li>)}
          </ul>
        </div>
      ))}
    </>
  );
}

// --- scheda 3: corsi disponibili ---------------------------------------------------------------------

function Sessione({ s, team, ricarica, setErrore }) {
  const [aperta, setAperta] = useState(false);
  const [scelte, setScelte] = useState(new Set());
  const [esito, setEsito] = useState(null);
  const [invio, setInvio] = useState(false);
  const libere = team.filter((p) => !s.persone_stato[p.id]);
  const diretta = s.modo === "diretta";
  const alterna = (id) => { const n = new Set(scelte); n.has(id) ? n.delete(id) : n.add(id); setScelte(n); };
  const [etichetta, aiuto] = MODO[s.modo] || [s.modo, ""];

  async function conferma() {
    setInvio(true); setErrore(null); setEsito(null);
    try {
      const ids = [...scelte];
      if (diretta) {
        const r = await api.post(`/edizioni/${s.id}/iscrizioni`, ids);
        setEsito(`Iscritte ${r.data.iscritti.length} ${r.data.iscritti.length === 1 ? "persona" : "persone"}.` + (r.data.non_iscritti.length ? ` Non iscritte: ${r.data.non_iscritti.map((x) => x.motivo).join("; ")}.` : ""));
      } else {
        const r = await api.post("/team/richieste", { edizione_id: s.id, user_ids: ids });
        const bloccati = (r.data.bloccati || []).map((x) => `${x.nome} (${x.motivo})`);
        setEsito((r.data.richieste ? `Richiesta inviata alla Formazione per ${r.data.richieste} ${r.data.richieste === 1 ? "persona" : "persone"}.` : "Nessuna nuova richiesta.")
          + (bloccati.length ? ` Non richieste, hanno ancora dei corsi da completare: ${bloccati.join("; ")}.` : ""));
      }
      setScelte(new Set()); await ricarica();
    } catch (e) { setErrore(erroreDi(e, diretta ? "Iscrizione non riuscita" : "Richiesta non riuscita")); }
    finally { setInvio(false); }
  }

  return (
    <>
      <tr>
        <td><strong>{s.corso_titolo}</strong><div><span className="badge gray" title={aiuto}>{etichetta}</span></div></td>
        <td>{quando(s)}<div className="text-muted" style={{ fontSize: 12 }}>{dove(s)}{s.durata_effettiva_minuti ? ` · ${formattaDurata(s.durata_effettiva_minuti)}` : ""}</div></td>
        <td><span className="badge gray">{MODALITA[s.modalita] || s.modalita}</span></td>
        <td>{s.posti_liberi === null ? <span className="text-muted">illimitati</span> : s.posti_liberi > 0 ? `${s.posti_liberi} liberi` : <span className="badge yellow">{s.lista_attesa_abilitata ? "lista d'attesa" : "esauriti"}</span>}</td>
        <td>{Object.keys(s.persone_stato).length ? Object.entries(s.persone_stato).map(([id, st]) => <div key={id} style={{ fontSize: 13 }}>{team.find((p) => p.id === id)?.nome} {capsulaStato(st)}</div>) : <span className="text-muted">—</span>}</td>
        <td><button type="button" className={aperta ? "secondary btn-sm" : "btn-sm"} onClick={() => setAperta(!aperta)}>{aperta ? "Chiudi" : diretta ? "Iscrivi persone" : "Chiedi l'iscrizione"}</button></td>
      </tr>
      {aperta && (
        <tr>
          <td colSpan={6} style={{ background: "var(--bg3)" }}>
            <div style={{ padding: "6px 0" }}>
              <strong>{diretta ? "Scegli chi iscrivere" : "Scegli per chi chiedere l'iscrizione"}</strong>
              <div style={{ margin: "6px 0", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 4 }}>
                {team.map((p) => (
                  <label key={p.id} style={{ display: "flex", gap: 6, alignItems: "center", opacity: s.persone_stato[p.id] ? .55 : 1 }}>
                    <input type="checkbox" style={{ width: "auto" }} disabled={!!s.persone_stato[p.id]} checked={scelte.has(p.id)} onChange={() => alterna(p.id)} />
                    {p.nome} <span className="text-muted" style={{ fontSize: 12 }}>{p.ufficio || ""}</span>{s.persone_stato[p.id] && capsulaStato(s.persone_stato[p.id])}
                  </label>
                ))}
              </div>
              <button type="button" className="secondary btn-sm" disabled={libere.length === 0} onClick={() => setScelte(scelte.size === libere.length ? new Set() : new Set(libere.map((p) => p.id)))}>{scelte.size === libere.length && libere.length ? "Deseleziona tutte" : "Seleziona tutte"}</button>{" "}
              <button type="button" disabled={scelte.size === 0 || invio} onClick={conferma}>
                {invio ? "Invio in corso..." : diretta ? `Iscrivi ${scelte.size} ${scelte.size === 1 ? "persona" : "persone"}` : `Chiedi l'iscrizione per ${scelte.size} ${scelte.size === 1 ? "persona" : "persone"}`}
              </button>
              {!diretta && <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>La richiesta arriva alla Formazione, che la approva o la rifiuta.</span>}
              {esito && <div className="success-msg">{esito}</div>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function SchedaCorsi() {
  const [d, setD] = useState(null);
  const [errore, setErrore] = useState(null);
  const [cerca, setCerca] = useState("");
  const carica = () => api.get("/team/corsi-disponibili").then((r) => setD(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i corsi disponibili")));
  useEffect(() => { carica(); }, []);
  if (!d) return errore ? <div className="error-msg">{errore}</div> : <p className="text-muted">Caricamento...</p>;
  const visibili = d.sessioni.filter((s) => !cerca.trim() || s.corso_titolo.toLowerCase().includes(cerca.trim().toLowerCase()));
  return (
    <>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="card">
        <div className="field" style={{ maxWidth: 320, margin: 0 }}><label htmlFor="t-cerca">Cerca un corso</label><input id="t-cerca" value={cerca} onChange={(e) => setCerca(e.target.value)} placeholder="titolo del corso" /></div>
        <p className="text-muted" style={{ fontSize: 13, margin: "8px 0 0" }}>Le prossime sessioni dei corsi aperti ai responsabili. «Iscrizione diretta»: iscrivi tu le persone. «Su richiesta»: la Formazione approva.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corso</th><th>Quando e dove</th><th>Modalità</th><th>Posti</th><th>Il tuo team</th><th></th></tr></thead>
          <tbody>
            {visibili.map((s) => <Sessione key={s.id} s={s} team={d.team} ricarica={carica} setErrore={setErrore} />)}
            {visibili.length === 0 && <tr><td colSpan={6} className="text-muted">{d.sessioni.length === 0 ? "Al momento nessun corso aperto ai responsabili ha sessioni in programma." : "Nessun corso corrisponde alla ricerca."}</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}

// --- scheda 4: richieste e approvazioni --------------------------------------------------------------

function SchedaApprovare() {
  const [auto, setAuto] = useState([]);
  const [mie, setMie] = useState([]);
  const [errore, setErrore] = useState(null);
  const carica = () => {
    api.get("/autoiscrizioni/da-approvare").then((r) => setAuto(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le auto-iscrizioni")));
    api.get("/team/richieste").then((r) => setMie(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le tue richieste")));
  };
  useEffect(carica, []);
  async function decidi(id, azione) {
    setErrore(null);
    try { await api.put(`/autoiscrizioni/${id}/${azione}`); } catch (e) { setErrore(erroreDi(e, "Operazione non riuscita")); }
    carica();
  }
  const ESITO = { in_attesa: ["yellow", "in attesa"], approvata: ["green", "approvata"], rifiutata: ["red", "rifiutata"] };
  return (
    <>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Auto-iscrizioni da approvare</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>Persone del tuo team che si sono iscritte da sole a un corso che richiede la tua approvazione.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Persona</th><th>Corso</th><th></th></tr></thead>
            <tbody>
              {auto.map((r) => (
                <tr key={r.id}><td>{r.user_nome}</td><td>{r.corso_titolo}</td>
                  <td><div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}><button type="button" className="btn-sm" onClick={() => decidi(r.id, "approva")}>Approva</button><button type="button" className="danger btn-sm" onClick={() => decidi(r.id, "rifiuta")}>Rifiuta</button></div></td></tr>
              ))}
              {auto.length === 0 && <tr><td colSpan={3} className="text-muted">Nessuna auto-iscrizione da approvare.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Le tue richieste alla Formazione</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Richiesta del</th><th>Persona</th><th>Corso</th><th>Esito</th></tr></thead>
            <tbody>
              {mie.map((r) => { const [c, t] = ESITO[r.stato] || ["gray", r.stato]; return (
                <tr key={r.id}><td>{dataIt(r.created_at)}</td><td>{r.persona}</td><td>{r.corso_titolo}<div className="text-muted" style={{ fontSize: 12 }}>{dataIt(r.data_inizio)}</div></td>
                  <td><span className={`badge ${c}`}>{t}</span>{r.motivo_rifiuto && <div className="text-muted" style={{ fontSize: 12 }}>{r.motivo_rifiuto}</div>}</td></tr>
              ); })}
              {mie.length === 0 && <tr><td colSpan={4} className="text-muted">Non hai fatto richieste.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

export default function IlMioTeam() {
  const [scheda, setScheda] = useState("team");
  const [org, setOrg] = useState(null);
  const [errore, setErrore] = useState(null);
  useEffect(() => { api.get("/team/organigramma").then((r) => setOrg(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare il tuo team"))); }, []);

  return (
    <div>
      <div className="page-header"><div><h2>Il mio team</h2><p>Le persone che guidi (i tuoi uffici e i sottouffici), la loro formazione e i corsi a cui puoi iscriverle.</p></div></div>
      {errore ? <div className="error-msg">{errore}</div> : (
        <>
          <div className="tabs">
            {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
          </div>
          {scheda === "team" && (org ? <SchedaTeam org={org} /> : <p className="text-muted">Caricamento...</p>)}
          {scheda === "formazione" && <SchedaFormazione />}
          {scheda === "corsi" && <SchedaCorsi />}
          {scheda === "approvare" && <SchedaApprovare />}
        </>
      )}
    </div>
  );
}
