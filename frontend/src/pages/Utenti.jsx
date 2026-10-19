import React, { useEffect, useState } from "react";
import api, { downloadFile, erroreDi } from "../api";
import ExportButton from "../components/ExportButton";
import { elencoUffici } from "../uffici";
import Finestra from "../components/Finestra";
import { REQUISITI_PASSWORD } from "../passwordPolicy";

const SCHEDE = [{ id: "elenco", label: "Elenco" }, { id: "nuovo", label: "Nuovo utente" }, { id: "csv", label: "Importa da Excel o CSV" }];
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

// Riepilogo delle righe con problemi, scaricabile (CSV con «;» e BOM: Excel lo apre in colonne).
function scaricaRiepilogo(risultato) {
  const righe = risultato.righe.filter((r) => r.esito === "errore" || (r.avvisi && r.avvisi.length) || r.esito === "ignorato");
  const testo = "\ufeff" + [["riga", "email", "esito", "dettaglio"], ...righe.map((r) => [r.riga, r.email, r.esito, (r.avvisi && r.avvisi.length ? r.avvisi.join(" | ") : r.messaggio)])]
    .map((r) => r.map((c) => { const t = String(c); return `"${(/^[=+\-@\t\r]/.test(t) ? "'" + t : t).replace(/"/g, '""')}"`; }).join(";")).join("\r\n") + "\r\n";   // mai una formula in Excel
  const url = URL.createObjectURL(new Blob([testo], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = "riepilogo-importazione.csv"; a.click();
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
  const [anteprima, setAnteprima] = useState(null);     // riepilogo del controllo, mostrato in una finestra prima di importare
  const [creato, setCreato] = useState(null);
  const [erroreCrea, setErroreCrea] = useState(null);

  function load() { api.get("/auth/users").then((r) => setList(r.data)); }
  useEffect(() => { if (modifica?.id) document.getElementById("u-form-modifica")?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [modifica?.id]);
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

  // 1) si controlla il file senza creare nulla; 2) la persona vede il riepilogo e conferma o annulla.
  async function controllaFile(e) {
    e.preventDefault();
    if (!csvFile) return;
    setCsvCaricamento(true);
    setCsvRisultato(null);
    try {
      const data = new FormData();
      data.append("file", csvFile);
      const r = await api.post("/auth/users/import-csv", data, { params: { modo: csvModo, anteprima: true } });
      setAnteprima(r.data);
    } catch (err) {
      setCsvRisultato({ errore: erroreDi(err, "Errore durante il controllo del file") });
    } finally {
      setCsvCaricamento(false);
    }
  }

  async function confermaImportazione() {
    setCsvCaricamento(true);
    try {
      const data = new FormData();
      data.append("file", csvFile);
      const r = await api.post("/auth/users/import-csv", data, { params: { modo: csvModo, controllo: anteprima?.controllo } });   // la conferma vale solo per il risultato visto nel controllo
      setAnteprima(null);
      setCsvRisultato(r.data);
      load();
    } catch (err) {
      setAnteprima(null);
      setCsvRisultato({ errore: erroreDi(err, "Errore durante l'importazione") });
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
      && (!filtro.ufficio || (filtro.ufficio === "__nessuno__" ? !u.ufficio && !u.is_external : u.ufficio?.id === filtro.ufficio))
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
        <h3>Importazione da Excel o CSV</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Puoi caricare un file <strong>Excel (.xlsx)</strong> o un <strong>CSV</strong>. Parti da un modello: ha le colonne giuste, e nel modello Excel i fogli «Uffici» e «Mansioni» elencano i nomi validi (la colonna Ufficio ha anche un menu a tendina).
          Colonne (maiuscole/minuscole indifferenti): <code>email</code>, <code>nome</code>, <code>cognome</code>, <code>ufficio</code> (nome, o percorso intero come <code>Produzione / Linea 2</code> se il nome si ripete),
          e opzionalmente <code>mansioni</code> (separate da <code>;</code>), <code>admin</code>, <code>formazione</code>, <code>formatore</code>, <code>is_external</code> (sì/no), <code>organizzazione</code> (per gli esterni), <code>data_ingresso</code> (AAAA-MM-GG), <code>password</code>.
        </p>
        <p className="text-muted" style={{ fontSize: 13 }}>
          <strong>Prima di importare il file viene controllato</strong> e vedi un riepilogo per persona: solo se confermi si crea qualcosa. Uffici e mansioni non vengono mai creati dal file: se un nome non esiste (o l'ufficio è vuoto) la persona viene creata <em>senza</em> quell'ufficio o quella mansione e te lo diciamo nel riepilogo. Le righe inutilizzabili (email, nome o cognome mancanti, email già presente, esterno senza organizzazione...) vengono scartate.
          Per <strong>disattivare</strong> in blocco (es. cessati) scegli «Disattiva cessati»: basta la colonna <code>email</code>; gli Admin non si disattivano da qui.
        </p>
        <p style={{ fontSize: 13 }}>
          <strong>Modelli da scaricare</strong> (cancella la riga di esempio):{" "}
          Nuovi utenti:{" "}
          <button type="button" className="secondary btn-sm" onClick={() => downloadFile("/auth/users/import-modello?formato=xlsx&modo=nuovi", "modello-nuovi-utenti.xlsx")}>Excel</button>{" "}
          <button type="button" className="secondary btn-sm" onClick={() => downloadFile("/auth/users/import-modello?formato=csv&modo=nuovi", "modello-nuovi-utenti.csv")}>CSV</button>
          {" · "}Disattiva cessati:{" "}
          <button type="button" className="secondary btn-sm" onClick={() => downloadFile("/auth/users/import-modello?formato=xlsx&modo=cessati", "modello-cessati.xlsx")}>Excel</button>{" "}
          <button type="button" className="secondary btn-sm" onClick={() => downloadFile("/auth/users/import-modello?formato=csv&modo=cessati", "modello-cessati.csv")}>CSV</button>
        </p>
        <form onSubmit={controllaFile}>
          <div className="row">
            <div className="field">
              <label htmlFor="csv-modo">Cosa fa il file</label>
              <select id="csv-modo" value={csvModo} onChange={(e) => { setCsvModo(e.target.value); setCsvRisultato(null); }}>
                <option value="nuovi">Crea nuovi utenti</option>
                <option value="cessati">Disattiva cessati</option>
              </select>
            </div>
            <div className="field"><label htmlFor="csv-file">File Excel (.xlsx) o CSV</label><input id="csv-file" type="file" accept=".xlsx,.csv" onChange={(e) => { setCsvFile(e.target.files[0]); setCsvRisultato(null); }} /></div>
            <div className="field" style={{ alignSelf: "flex-end" }}><button type="submit" disabled={!csvFile || csvCaricamento}>{csvCaricamento ? "Controllo in corso..." : "Controlla il file"}</button></div>
          </div>
        </form>
        {csvRisultato && csvRisultato.errore && <div className="error-msg">{csvRisultato.errore}</div>}
        {csvRisultato && !csvRisultato.errore && (
          <div>
            <p>
              {csvRisultato.disattivati !== undefined && csvModo === "cessati"
                ? <>Persone disattivate: <strong>{csvRisultato.disattivati}</strong></>
                : <>Persone create: <strong>{csvRisultato.creati}</strong>{csvRisultato.con_avvisi > 0 && <> (di cui <strong>{csvRisultato.con_avvisi}</strong> con avvisi)</>}</>}
              {". "}Righe lette: {csvRisultato.totale}, scartate: {csvRisultato.errori}.{" "}
              {csvRisultato.righe.some((r) => r.esito === "errore" || r.esito === "ignorato" || (r.avvisi && r.avvisi.length)) && (
                <button type="button" className="secondary btn-sm" onClick={() => scaricaRiepilogo(csvRisultato)}>Scarica il riepilogo dei problemi</button>
              )}{" "}
              {csvRisultato.righe.some((r) => (r.avvisi || []).some((a) => a.includes("senza ufficio"))) && (
                <button type="button" className="secondary btn-sm" onClick={() => { setFiltro({ ...filtro, ufficio: "__nessuno__" }); setPagina(0); setScheda("elenco"); }}>Mostra le persone senza ufficio</button>
              )}
            </p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Riga</th><th>Email</th><th>Esito</th><th>Dettaglio</th><th>Password</th></tr></thead>
                <tbody>
                  {csvRisultato.righe.map((r) => (
                    <tr key={r.riga}>
                      <td>{r.riga}</td><td>{r.email}</td>
                      <td><span className={`badge ${r.esito === "creato" && r.avvisi?.length ? "yellow" : r.esito === "creato" || r.esito === "disattivato" ? "green" : r.esito === "ignorato" ? "gray" : "red"}`}>{r.esito === "creato" && r.avvisi?.length ? "creato, con avvisi" : r.esito}</span></td>
                      <td>{r.avvisi?.length && r.esito === "creato" ? <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>{r.avvisi.map((a, i) => <li key={i}>{a}</li>)}</ul> : r.messaggio}</td>
                      <td>{r.password ? <code>{r.password}</code> : (r.email_inviata ? "invito in invio per email" : "-")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {anteprima && (() => {
          const scartate = anteprima.righe.filter((r) => r.esito === "errore");
          const conAvvisi = anteprima.righe.filter((r) => r.esito === "creato" && r.avvisi?.length);
          const ignorate = anteprima.righe.filter((r) => r.esito === "ignorato");
          const daFare = csvModo === "cessati" ? anteprima.disattivati : anteprima.creati;
          const senzaProblemi = !scartate.length && !conAvvisi.length;
          return (
            <Finestra titolo={csvModo === "cessati" ? "Controllo dell'elenco dei cessati" : "Controllo del file"} onChiudi={csvCaricamento ? undefined : () => setAnteprima(null)}
              azioni={<>
                <button type="button" className="secondary" disabled={csvCaricamento} onClick={() => setAnteprima(null)}>Annulla</button>
                <button type="button" disabled={daFare === 0 || csvCaricamento} className={csvModo === "cessati" ? "danger" : undefined} onClick={confermaImportazione}>
                  {csvCaricamento ? "Importazione in corso..." : (senzaProblemi ? (csvModo === "cessati" ? "Disattiva" : "Importa") : (csvModo === "cessati" ? "Disattiva comunque" : "Importa comunque"))}
                </button>
              </>}>
              <p style={{ marginTop: 0 }}>
                {csvModo === "cessati"
                  ? <>Persone da disattivare: <strong>{anteprima.disattivati}</strong>. Perdono l'accesso e le loro iscrizioni aperte vengono annullate (lo storico resta).</>
                  : <>Persone da creare: <strong>{anteprima.creati}</strong>{conAvvisi.length > 0 && <> (di cui <strong>{conAvvisi.length}</strong> con qualche dato in meno)</>}.</>}
                {scartate.length > 0 && <> Righe scartate: <strong>{scartate.length}</strong>.</>}
                {senzaProblemi && daFare > 0 && <> Nessun problema trovato.</>}
              </p>
              {conAvvisi.length > 0 && <>
                <strong>Persone create con qualche dato in meno</strong>
                <ul>{conAvvisi.map((r) => <li key={r.riga}><strong>{r.nome || r.email}</strong> ({r.email}, riga {r.riga}): {r.avvisi.join("; ")}</li>)}</ul>
              </>}
              {scartate.length > 0 && <>
                <strong>Righe scartate</strong>
                <ul>{scartate.map((r) => <li key={r.riga}>Riga {r.riga}{r.email ? ` (${r.email})` : ""}: {r.messaggio}</li>)}</ul>
              </>}
              {ignorate.length > 0 && <>
                <strong>Ignorate</strong>
                <ul>{ignorate.map((r) => <li key={r.riga}>Riga {r.riga} ({r.email}): {r.messaggio}</li>)}</ul>
              </>}
              {csvModo !== "cessati" && conAvvisi.length > 0 && <p className="text-muted" style={{ fontSize: 13 }}>Se preferisci correggere il file, premi «Annulla»: finché non confermi non viene creato nulla. Se confermi, le persone nascono senza quei dati e le potrai sistemare dalla loro scheda (filtro «Senza ufficio» nell'elenco).</p>}
            </Finestra>
          );
        })()}
      </div>}
      {scheda === "elenco" && <>
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
                <option value="__nessuno__">Senza ufficio</option>
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
                <React.Fragment key={u.id}>
                <tr>
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
                {modifica?.id === u.id && (
                  <tr>
                    <td colSpan={9} style={{ background: "var(--bg3)" }}>
            <form id="u-form-modifica" onSubmit={salvaModifica}>
              <h4 style={{ margin: "8px 0" }}>Modifica {modifica.nome}</h4>
              <div className="row">
                <div className="field"><label>Nome</label><input required value={modifica.valori.nome} onChange={(e) => setModifica({ ...modifica, valori: { ...modifica.valori, nome: e.target.value } })} /></div>
                <div className="field"><label>Cognome</label><input required value={modifica.valori.cognome} onChange={(e) => setModifica({ ...modifica, valori: { ...modifica.valori, cognome: e.target.value } })} /></div>
              </div>
              <CampiPersona valori={modifica.valori} set={(v) => setModifica({ ...modifica, valori: v })} uffici={uffici} mansioni={mansioniAttive} orgs={orgs} />
              {erroreModifica && <div className="error-msg">{erroreModifica}</div>}
              <button type="submit">Salva</button>{" "}
              <button type="button" className="secondary" onClick={() => setModifica(null)}>Annulla</button>
            </form>
                    </td>
                  </tr>
                )}
                </React.Fragment>
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
