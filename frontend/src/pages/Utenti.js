import React, { useEffect, useState } from "react";
import api from "../api";
import ExportButton from "../components/ExportButton";
import { REQUISITI_PASSWORD } from "../passwordPolicy";

export default function Utenti() {
  const [list, setList] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "user", is_external: false, organizzazione_id: "", group_ids: [], origine_credenziali: "locale" });
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
  }, []);

  async function submit(e) {
    e.preventDefault();
    const payload = { ...form, organizzazione_id: form.is_external ? form.organizzazione_id : null };
    setCreato(null); setErroreCrea(null);
    try { setCreato((await api.post("/auth/users", payload)).data); }
    catch (err) { setErroreCrea(err.response?.data?.detail || "Errore nella creazione"); return; }
    setForm({ full_name: "", email: "", password: "", role: "user", is_external: false, organizzazione_id: "", group_ids: [], origine_credenziali: "locale" });
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
      setCsvRisultato({ errore: err.response?.data?.detail || "Errore durante l'import" });
    } finally {
      setCsvCaricamento(false);
    }
  }

  return (
    <div>
      <div className="page-header"><div><h2>Utenti</h2></div><ExportButton path="/auth/users/export" filename="utenti" /></div>
      <div className="card">
        <h3>Nuovo utente</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome e cognome</label><input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
            <div className="field"><label>Email</label><input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Password iniziale (facoltativa)</label><input type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /><span className="text-muted" style={{ fontSize: 12 }}>Lasciala vuota: se l'invio email è attivo la persona riceve un link per scegliere la sua password, altrimenti te ne genero una temporanea. Se la scrivi tu: {REQUISITI_PASSWORD}; dovrà comunque cambiarla al primo accesso.</span></div>
            <div className="field">
              <label>Ruolo funzionale</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="user">Utente (discente / eventuale docente)</option>
                <option value="training_admin">Ufficio Formazione</option>
                <option value="admin_tecnico">Admin tecnico</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={form.is_external} onChange={(e) => setForm({ ...form, is_external: e.target.checked })} /> Utente esterno (docente/collaboratore di un ente terzo)</label>
          </div>
          {form.is_external && (
            <div className="field">
              <label>Organizzazione di riferimento</label>
              <select required value={form.organizzazione_id} onChange={(e) => setForm({ ...form, organizzazione_id: e.target.value })}>
                <option value="">-- seleziona --</option>
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.ragione_sociale}</option>)}
              </select>
            </div>
          )}
          <div className="field">
            <label>Credenziali</label>
            <select value={form.origine_credenziali} onChange={(e) => setForm({ ...form, origine_credenziali: e.target.value })}>
              <option value="locale">Gestite qui (l'utente può cambiare la password)</option>
              <option value="dominio">Gestite dal dominio aziendale (nessun cambio password qui)</option>
            </select>
          </div>
          <div className="field">
            <label>Gruppi</label>
            <select multiple value={form.group_ids} onChange={(e) => setForm({ ...form, group_ids: Array.from(e.target.selectedOptions, (o) => o.value) })} style={{ height: 80 }}>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>
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
      </div>
      <div className="card">
        <h3>Import massivo da CSV</h3>
        <p className="text-muted" style={{ fontSize: 13 }}>
          Colonne attese (intestazione, maiuscole/minuscole indifferenti): <code>email</code>, <code>full_name</code> (o <code>nome</code>),
          e opzionalmente <code>password</code>, <code>role</code> (user/training_admin/admin_tecnico), <code>is_external</code>,
          <code>organizzazione</code> (ragione sociale esatta), <code>gruppi</code> (nomi separati da <code>;</code> o <code>|</code>), <code>data_ingresso</code> (AAAA-MM-GG).
          Se non indicata, la password viene generata automaticamente; se l'invio email è configurato (pagina Azienda) viene mandata all'utente, altrimenti compare nel risultato qui sotto.
          <br />Per <strong>disattivare</strong> utenti in blocco (es. cessati) scegli «Disattiva cessati»: basta la colonna <code>email</code> e ogni riga disattiva l'account corrispondente, senza toccarne lo storico formativo. Gli Admin tecnici non si disattivano da qui.
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
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Email</th><th>Ruolo</th><th>Tipo</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {list.map((u) => (
              <tr key={u.id}>
                <td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td>
                <td>{u.is_external ? "esterno" : "interno"}</td>
                <td>{u.is_active ? <span className="badge green">attivo</span> : <span className="badge red">disabilitato</span>}</td>
                <td><button className="secondary" onClick={() => toggleActive(u)}>{u.is_active ? "Disabilita" : "Riattiva"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
