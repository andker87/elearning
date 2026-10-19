import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import ExportButton from "../components/ExportButton";
import { elencoUffici } from "../uffici";
import { REQUISITI_PASSWORD } from "../passwordPolicy";

const SCHEDE = [{ id: "elenco", label: "Elenco" }, { id: "nuovo", label: "Nuovo utente" }, { id: "csv", label: "Importa da CSV" }];
const PER_PAGINA = [25, 50, 100];
const PERMESSI = { admin: "Admin", formazione: "Formazione", formatore: "Formatore", nessuno: "Nessuno (utente semplice)" };
const VUOTO = { nome: "", cognome: "", email: "", password: "", is_admin: false, is_formazione: false, is_formatore: false, is_external: false,
  organizzazione_id: "", ufficio_id: "", mansione_ids: [], origine_credenziali: "locale" };

// I permessi di una persona in parole: un esterno è Formatore per definizione.
function etichette(u) {
  const v = [];
  if (u.is_admin) v.push("Admin");
  if (u.is_formazione) v.push("Formazione");
  if (u.is_formatore) v.push("Formatore");
  return v;
}

// Modelli del CSV: separatore «;» (Excel in italiano lo apre in colonne) e BOM per gli accenti.
const COLONNE_CSV = ["email", "nome", "cognome", "ufficio", "mansioni", "admin", "formazione", "formatore", "is_external", "organizzazione", "data_ingresso", "password"];
function scaricaModello(nomeFile, intestazione, riga) {
  const testo = "\ufeff" + [intestazione.join(";"), riga.join(";")].join("\r\n") + "\r\n";
  const url = URL.createObjectURL(new Blob([testo], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = nomeFile; a.click();
  URL.revokeObjectURL(url);
}

// Campi comuni a «Nuovo utente» e «Modifica»: tipo di persona, permessi, ufficio, mansioni.
function CampiPersona({ valori, set, uffici, mansioni, orgs, nuovo }) {
  const externo = valori.is_external;
  return (
    <>
      <div className="field">
        <label>Tipo di persona</label>
        <select value={externo ? "esterno" : "interno"} onChange={(e) => set({ ...valori, is_external: e.target.value === "esterno",
          ...(e.target.value === "esterno" ? { is_admin: false, is_formazione: false, ufficio_id: "", mansione_ids: [] } : {}) })}>
          <option value="interno">Interno (persona dell'organizzazione, oggetto di formazione)</option>
          <option value="esterno">Esterno (docente di una società terza)</option>
        </select>
      </div>
      {externo ? (
        <div className="field">
          <label>Organizzazione di riferimento</label>
          <select required value={valori.organizzazione_id} onChange={(e) => set({ ...valori, organizzazione_id: e.target.value })}>
            <option value="">-- seleziona --</option>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.ragione_sociale}</option>)}
          </select>
          <span className="text-muted" style={{ fontSize: 12 }}>Un esterno è un docente: può essere assegnato alle edizioni, non segue corsi e non ha ufficio né mansioni.</span>
        </div>
      ) : (
        <>
          <div className="field">
            <label>Ufficio{valori.is_admin ? " (facoltativo per un Admin)" : ""}</label>
            <select required={!valori.is_admin} value={valori.ufficio_id} onChange={(e) => set({ ...valori, ufficio_id: e.target.value })}>
              <option value="">-- seleziona --</option>
              {uffici.map((g) => <option key={g.id} value={g.id}>{g.percorso}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Permessi e qualifica</label>
            <div>
              <label style={{ marginRight: 16 }}><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={valori.is_admin} onChange={(e) => set({ ...valori, is_admin: e.target.checked })} />Admin</label>
              <label style={{ marginRight: 16 }}><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={valori.is_formazione} onChange={(e) => set({ ...valori, is_formazione: e.target.checked })} />Formazione</label>
              <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={valori.is_formatore} onChange={(e) => set({ ...valori, is_formatore: e.target.checked })} />Formatore (può essere scelto come docente)</label>
            </div>
            <span className="text-muted" style={{ fontSize: 12 }}>Senza nessuna spunta è un utente semplice. Admin configura la piattaforma e ha anche i poteri della Formazione; Formazione gestisce corsi, edizioni, iscrizioni e attestati.</span>
          </div>
          {mansioni.length > 0 && (
            <div className="field">
              <label>Mansioni</label>
              <div>
                {mansioni.map((m) => (
                  <label key={m.id} style={{ marginRight: 16, display: "inline-block" }}>
                    <input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={valori.mansione_ids.includes(m.id)}
                      onChange={(e) => set({ ...valori, mansione_ids: e.target.checked ? [...valori.mansione_ids, m.id] : valori.mansione_ids.filter((x) => x !== m.id) })} />{m.name}
                  </label>
                ))}
              </div>
            </div>
          )}
        </>
      )}
      <div className="field">
        <label>Credenziali</label>
        <select value={valori.origine_credenziali} onChange={(e) => set({ ...valori, origine_credenziali: e.target.value })}>
          <option value="locale">Gestite qui (l'utente può cambiare la password)</option>
          <option value="dominio">Gestite dal dominio aziendale (nessun cambio password qui)</option>
        </select>
      </div>
    </>
  );
}

export default function Utenti() {
  const [scheda, setScheda] = useState("elenco");
  const [filtro, setFiltro] = useState({ testo: "", permesso: "", tipo: "", stato: "", ufficio: "", mansione: "" });
  const [ordine, setOrdine] = useState({ col: "cognome", verso: 1 });
  const [pagina, setPagina] = useState(0);
  const [perPagina, setPerPagina] = useState(25);
  const [list, setList] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [groups, setGroups] = useState([]);
  const [mansioni, setMansioni] = useState([]);
  const [form, setForm] = useState(VUOTO);
  const [modifica, setModifica] = useState(null);       // {id, nome, valori}
  const [erroreModifica, setErroreModifica] = useState(null);
  const [csvFile, setCsvFile] = useState(null);
  const [csvModo, setCsvModo] = useState("nuovi");
  const [csvRisultato, setCsvRisultato] = useState(null);
  const [csvCaricamento, setCsvCaricamento] = useState(false);
  const [creato, setCreato] = useState(null);
  const [erroreCrea, setErroreCrea] = useState(null);

  function load() { api.get("/auth/users").then((r) => setList(r.data)); }
  useEffect(() => {
    load();
    api.get("/organizzazioni").then((r) => setOrgs(r.data));
    api.get("/groups").then((r) => setGroups(r.data));
    api.get("/mansioni").then((r) => setMansioni(r.data));
  }, []);

  const uffici = elencoUffici(groups).map((g) => ({ id: g.id, percorso: g.etichetta }));   // alfabetico a ogni livello, percorso intero
  const percorsoDi = Object.fromEntries(uffici.map((g) => [g.id, g.percorso]));
  const mansioniAttive = mansioni.filter((m) => m.is_active);

  const COLONNE = [
    { id: "cognome", label: "Cognome", valore: (u) => u.cognome || "" },
    { id: "nome", label: "Nome", valore: (u) => u.nome || "" },
    { id: "email", label: "Email", valore: (u) => u.email || "" },
    { id: "permessi", label: "Permessi", valore: (u) => etichette(u).join(", ") },
    { id: "ufficio", label: "Ufficio", valore: (u) => (u.ufficio ? percorsoDi[u.ufficio.id] || u.ufficio.name : "") },
    { id: "mansioni", label: "Mansioni", valore: (u) => (u.mansioni || []).map((m) => m.name).sort().join(", ") },
    { id: "tipo", label: "Tipo", valore: (u) => (u.is_external ? "esterno" : "interno") },
    { id: "stato", label: "Stato", valore: (u) => (u.is_active ? "attivo" : "disabilitato") },
  ];

  function payload(v) {
    return { nome: v.nome, cognome: v.cognome, is_admin: v.is_admin, is_formazione: v.is_formazione, is_formatore: v.is_formatore,
      is_external: v.is_external, organizzazione_id: v.is_external ? v.organizzazione_id : "",
      ufficio_id: v.is_external ? "" : v.ufficio_id, mansione_ids: v.is_external ? [] : v.mansione_ids, origine_credenziali: v.origine_credenziali };
  }

  async function submit(e) {
    e.preventDefault();
    const dati = { ...payload(form), email: form.email, password: form.password,
      organizzazione_id: form.is_external ? form.organizzazione_id : null, ufficio_id: form.is_external ? null : (form.ufficio_id || null) };
    setCreato(null); setErroreCrea(null);
    try { setCreato((await api.post("/auth/users", dati)).data); }
    catch (err) { setErroreCrea(erroreDi(err, "Errore nella creazione")); return; }
    setForm(VUOTO);
    load();
  }

  function apriModifica(u) {
    setErroreModifica(null);
    setModifica({ id: u.id, nome: u.full_name, valori: {
      nome: u.nome, cognome: u.cognome, is_admin: u.is_admin, is_formazione: u.is_formazione, is_formatore: u.is_formatore && !u.is_external,
      is_external: u.is_external, organizzazione_id: u.organizzazione_id || "", ufficio_id: u.ufficio?.id || "",
      mansione_ids: (u.mansioni || []).map((m) => m.id), origine_credenziali: u.origine_credenziali || "locale" } });
  }

  async function salvaModifica(e) {
    e.preventDefault();
    setErroreModifica(null);
    try { await api.put(`/auth/users/${modifica.id}`, payload(modifica.valori)); }
    catch (err) { setErroreModifica(erroreDi(err, "Impossibile salvare le modifiche")); return; }
    setModifica(null);
    load();
  }

  async function toggleActive(u) {
    await api.put(`/auth/users/${u.id}`, { is_active: !u.is_active });
    load();
  }

  async function importaCsv(e) {
    e.preventDefault();
    if (!csvFile) return;
    setCsvCaricamento(true);
    setCsvRisultato(null);
    try {
      const data = new FormData();
      data.append("file", csvFile);
      if (csvModo === "cessati" && !window.confirm("Disattivare tutti gli utenti elencati nel file? Perdono l'accesso e le loro iscrizioni aperte vengono annullate (lo storico resta).")) { setCsvCaricamento(false); return; }
      const r = await api.post("/auth/users/import-csv", data, { params: { modo: csvModo } });
      setCsvRisultato(r.data);
      load();
    } catch (err) {
      setCsvRisultato({ errore: erroreDi(err, "Errore durante l'import") });
    } finally {
      setCsvCaricamento(false);
    }
  }

  function cambiaFiltro(campo, valore) { setFiltro({ ...filtro, [campo]: valore }); setPagina(0); }
  function ordinaPer(col) { setOrdine(ordine.col === col ? { col, verso: -ordine.verso } : { col, verso: 1 }); }

  const cerca = filtro.testo.trim().toLowerCase();
  const colOrdine = COLONNE.find((c) => c.id === ordine.col) || COLONNE[0];
  const visibili = list
    .filter((u) => (!cerca || `${u.nome} ${u.cognome} ${u.email}`.toLowerCase().includes(cerca))
      && (!filtro.permesso || (filtro.permesso === "nessuno" ? etichette(u).length === 0 : etichette(u).includes(PERMESSI[filtro.permesso])))
      && (!filtro.tipo || (filtro.tipo === "esterno") === !!u.is_external)
      && (!filtro.stato || (filtro.stato === "attivo") === !!u.is_active)
      && (!filtro.ufficio || u.ufficio?.id === filtro.ufficio)
      && (!filtro.mansione || (u.mansioni || []).some((m) => m.id === filtro.mansione)))
    .sort((a, b) => ordine.verso * colOrdine.valore(a).localeCompare(colOrdine.valore(b), "it", { sensitivity: "base", numeric: true }));
  const pagineTotali = Math.max(1, Math.ceil(visibili.length / perPagina));
  const paginaCorrente = Math.min(pagina, pagineTotali - 1);
  const inPagina = visibili.slice(paginaCorrente * perPagina, (paginaCorrente + 1) * perPagina);

  return (
    <div>
      <div className="page-header"><div><h2>Utenti</h2></div></div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
      </div>
      {scheda === "nuovo" && <div className="card">
        <h3>Nuovo utente</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome</label><input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></div>
            <div className="field"><label>Cognome</label><input required value={form.cognome} onChange={(e) => setForm({ ...form, cognome: e.target.value })} /></div>
          </div>
          <div className="field"><label>Email</label><input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div className="field"><label>Password iniziale (facoltativa)</label><input type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /><span className="text-muted" style={{ fontSize: 12 }}>Lasciala vuota: se l'invio email è attivo la persona riceve un link per scegliere la sua password, altrimenti te ne genero una temporanea. Se la scrivi tu: {REQUISITI_PASSWORD}; dovrà comunque cambiarla al primo accesso.</span></div>
          <CampiPersona valori={form} set={setForm} uffici={uffici} mansioni={mansioniAttive} orgs={orgs} nuovo />
          <button type="submit">Crea utente</button>
        </form>
        {erroreCrea && <div className="error-msg">{erroreCrea}</div>}
        {creato && (
          <div className="card card-muted" style={{ marginTop: 12 }}>
            <strong>{creato.full_name} è stato creato.</strong>
            {creato.invito_inviato && <p style={{ margin: ".4rem 0 0" }}>Ha ricevuto per email un link, valido 3 giorni, per scegliere la sua password.</p>}
            {creato.password_temporanea && (
              <p style={{ margin: ".4rem 0 0" }}>
                Password temporanea: <code style={{ fontSize: 16 }}>{creato.password_temporanea}</code><br />
                <span className="text-muted" style={{ fontSize: 12 }}>Comunicala a parte: non verrà mostrata di nuovo. Al primo accesso dovrà sceglierne una sua.</span>
              </p>
            )}
            {!creato.invito_inviato && !creato.password_temporanea && <p className="text-muted" style={{ margin: ".4rem 0 0", fontSize: 13 }}>Comunica a parte la password che hai scelto: dovrà cambiarla al primo accesso.</p>}
          </div>
        )}
      </div>}
      {scheda === "csv" && <div className="card">
        <h3>Import massivo da CSV</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Colonne attese (intestazione, maiuscole/minuscole indifferenti): <code>email</code>, <code>nome</code>, <code>cognome</code>,
          <code>ufficio</code> (nome, o percorso intero come <code>Produzione / Linea 2</code> se il nome si ripete; obbligatorio per gli interni che non sono Admin),
          e opzionalmente <code>password</code>, <code>admin</code>, <code>formazione</code>, <code>formatore</code> (sì/no),
          <code>mansioni</code> (nomi separati da <code>;</code> o <code>|</code>), <code>is_external</code>,
          <code>organizzazione</code> (ragione sociale esatta, per gli esterni), <code>data_ingresso</code> (AAAA-MM-GG).
          Se non indicata, la password viene generata automaticamente: se l'invio email è configurato (pagina Azienda) l'utente riceve un link per scegliere la sua password (non la password stessa), altrimenti la password temporanea compare nel risultato qui sotto.
          <br />Per <strong>disattivare</strong> utenti in blocco (es. cessati) scegli «Disattiva cessati»: basta la colonna <code>email</code> e ogni riga disattiva l'account corrispondente, senza toccarne lo storico formativo. Gli Admin non si disattivano da qui.
        </p>
        <p style={{ fontSize: 13 }}>
          <strong>Modelli da scaricare</strong> (cancella la riga di esempio prima di caricarli):{" "}
          <button type="button" className="secondary btn-sm" onClick={() => scaricaModello("modello-nuovi-utenti.csv", COLONNE_CSV,
            ["mario.rossi@azienda.it", "Mario", "Rossi", uffici[0]?.percorso || "Nome dell'ufficio", mansioniAttive[0]?.name || "", "no", "no", "no", "no", "", "2026-01-15", ""])}>Nuovi utenti</button>{" "}
          <button type="button" className="secondary btn-sm" onClick={() => scaricaModello("modello-cessati.csv", ["email"], ["mario.rossi@azienda.it"])}>Disattiva cessati</button>
        </p>
        <form onSubmit={importaCsv}>
          <div className="row">
            <div className="field">
              <label>Cosa fa il file</label>
              <select value={csvModo} onChange={(e) => setCsvModo(e.target.value)}>
                <option value="nuovi">Crea nuovi utenti</option>
                <option value="cessati">Disattiva cessati</option>
              </select>
            </div>
            <div className="field"><label>File CSV</label><input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files[0])} /></div>
            <div className="field" style={{ alignSelf: "flex-end" }}><button type="submit" className={csvModo === "cessati" ? "danger" : undefined} disabled={!csvFile || csvCaricamento}>{csvCaricamento ? "Import in corso..." : csvModo === "cessati" ? "Disattiva" : "Importa"}</button></div>
          </div>
        </form>
        {csvRisultato && csvRisultato.errore && <p style={{ color: "#b02a2a" }}>{csvRisultato.errore}</p>}
        {csvRisultato && !csvRisultato.errore && (
          <div>
            <p>
              <strong>{csvRisultato.creati}</strong> creati
              {csvRisultato.righe.some((r) => r.esito === "disattivato") && <> · <strong>{csvRisultato.righe.filter((r) => r.esito === "disattivato").length}</strong> disattivati</>}
              {" "}su {csvRisultato.totale} righe ({csvRisultato.errori} errori).
            </p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Riga</th><th>Email</th><th>Esito</th><th>Messaggio</th><th>Password</th></tr></thead>
                <tbody>
                  {csvRisultato.righe.map((r) => (
                    <tr key={r.riga}>
                      <td>{r.riga}</td><td>{r.email}</td>
                      <td><span className={`badge ${r.esito === "creato" || r.esito === "disattivato" ? "green" : r.esito === "ignorato" ? "gray" : "red"}`}>{r.esito}</span></td>
                      <td>{r.messaggio}</td>
                      <td>{r.password ? <code>{r.password}</code> : (r.email_inviata ? "invito in invio per email" : "-")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>}
      {scheda === "elenco" && <>
        {modifica && (
          <div className="card">
            <h3>Modifica {modifica.nome}</h3>
            <form onSubmit={salvaModifica}>
              <div className="row">
                <div className="field"><label>Nome</label><input required value={modifica.valori.nome} onChange={(e) => setModifica({ ...modifica, valori: { ...modifica.valori, nome: e.target.value } })} /></div>
                <div className="field"><label>Cognome</label><input required value={modifica.valori.cognome} onChange={(e) => setModifica({ ...modifica, valori: { ...modifica.valori, cognome: e.target.value } })} /></div>
              </div>
              <CampiPersona valori={modifica.valori} set={(v) => setModifica({ ...modifica, valori: v })} uffici={uffici} mansioni={mansioniAttive} orgs={orgs} />
              {erroreModifica && <div className="error-msg">{erroreModifica}</div>}
              <button type="submit">Salva</button>{" "}
              <button type="button" className="secondary" onClick={() => setModifica(null)}>Annulla</button>
            </form>
          </div>
        )}
        <div className="card">
          <div className="row">
            <div className="field"><label htmlFor="u-cerca">Cerca</label><input id="u-cerca" placeholder="nome, cognome o email" value={filtro.testo} onChange={(e) => cambiaFiltro("testo", e.target.value)} /></div>
            <div className="field"><label htmlFor="u-permesso">Permessi</label>
              <select id="u-permesso" value={filtro.permesso} onChange={(e) => cambiaFiltro("permesso", e.target.value)}>
                <option value="">Tutti</option>
                {Object.entries(PERMESSI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div className="field"><label htmlFor="u-ufficio">Ufficio</label>
              <select id="u-ufficio" value={filtro.ufficio} onChange={(e) => cambiaFiltro("ufficio", e.target.value)}>
                <option value="">Tutti</option>
                {uffici.map((g) => <option key={g.id} value={g.id}>{g.percorso}</option>)}
              </select></div>
            <div className="field"><label htmlFor="u-mansione">Mansione</label>
              <select id="u-mansione" value={filtro.mansione} onChange={(e) => cambiaFiltro("mansione", e.target.value)}>
                <option value="">Tutte</option>
                {mansioni.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select></div>
            <div className="field"><label htmlFor="u-tipo">Tipo</label>
              <select id="u-tipo" value={filtro.tipo} onChange={(e) => cambiaFiltro("tipo", e.target.value)}>
                <option value="">Tutti</option><option value="interno">Interno</option><option value="esterno">Esterno</option>
              </select></div>
            <div className="field"><label htmlFor="u-stato">Stato</label>
              <select id="u-stato" value={filtro.stato} onChange={(e) => cambiaFiltro("stato", e.target.value)}>
                <option value="">Tutti</option><option value="attivo">Attivo</option><option value="disabilitato">Disabilitato</option>
              </select></div>
          </div>
          <div className="flex-between">
            <span aria-live="polite" className="text-muted" style={{ fontSize: 13 }}>{visibili.length} utenti{visibili.length !== list.length ? ` su ${list.length}` : ""}</span>
            <ExportButton path="/auth/users/export" filename="utenti" />
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr>
              {COLONNE.map((c) => (
                <th key={c.id} aria-sort={ordine.col === c.id ? (ordine.verso === 1 ? "ascending" : "descending") : "none"}>
                  <button type="button" className="secondary" style={{ border: 0, background: "none", padding: 0, font: "inherit", fontWeight: 600, cursor: "pointer" }} onClick={() => ordinaPer(c.id)}>
                    {c.label}{ordine.col === c.id ? (ordine.verso === 1 ? " ▲" : " ▼") : ""}
                  </button>
                </th>
              ))}
              <th></th>
            </tr></thead>
            <tbody>
              {inPagina.map((u) => (
                <tr key={u.id}>
                  <td>{u.cognome}</td><td>{u.nome}</td><td>{u.email}</td>
                  <td>{etichette(u).map((t) => <span key={t} className="badge" style={{ marginRight: 4 }}>{t}</span>)}{etichette(u).length === 0 && "—"}</td>
                  <td>{u.ufficio ? (percorsoDi[u.ufficio.id] || u.ufficio.name) : "—"}</td>
                  <td>{(u.mansioni || []).map((m) => <span key={m.id} className="badge" style={{ background: m.color, color: "#fff", marginRight: 4 }}>{m.name}</span>)}{(u.mansioni || []).length === 0 && "—"}</td>
                  <td>{u.is_external ? "esterno" : "interno"}</td>
                  <td>{u.is_active ? <span className="badge green">attivo</span> : <span className="badge red">disabilitato</span>}</td>
                  <td>
                    <button className="secondary btn-sm" onClick={() => apriModifica(u)}>Modifica</button>{" "}
                    <button className="secondary btn-sm" onClick={() => toggleActive(u)}>{u.is_active ? "Disabilita" : "Riattiva"}</button>
                  </td>
                </tr>
              ))}
              {inPagina.length === 0 && <tr><td colSpan={9} className="text-muted">Nessun utente corrisponde ai filtri.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="flex-between" style={{ marginTop: 12 }}>
          <span>
            <label htmlFor="u-pp" className="text-muted" style={{ fontSize: 13, marginRight: 6 }}>Per pagina</label>
            <select id="u-pp" style={{ width: "auto" }} value={perPagina} onChange={(e) => { setPerPagina(Number(e.target.value)); setPagina(0); }}>
              {PER_PAGINA.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </span>
          <span>
            <button type="button" className="secondary" disabled={paginaCorrente === 0} onClick={() => setPagina(paginaCorrente - 1)}>Precedente</button>
            <span aria-live="polite" style={{ margin: "0 10px", fontSize: 13 }}>Pagina {paginaCorrente + 1} di {pagineTotali}</span>
            <button type="button" className="secondary" disabled={paginaCorrente >= pagineTotali - 1} onClick={() => setPagina(paginaCorrente + 1)}>Successiva</button>
          </span>
        </div>
      </>}
    </div>
  );
}
