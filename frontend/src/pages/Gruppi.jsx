import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import { elencoUffici } from "../uffici";
import SelettoreColore from "../components/SelettoreColore";
import { conferma } from "../components/conferma";

// Gli uffici sono la struttura organizzativa: albero di uffici e sottouffici, ciascuno con un responsabile.
// Le categorie trasversali (preposto, addetto antincendio...) sono le Mansioni.
const VUOTO = { name: "", description: "", color: "#5a6b8a", parent_id: "", responsabile_id: "" };

export default function Gruppi() {
  const [list, setList] = useState([]);
  const [utenti, setUtenti] = useState([]);
  const [form, setForm] = useState(VUOTO);
  const [modifica, setModifica] = useState(null);     // {id, valori}
  const [errore, setErrore] = useState(null);
  const [erroreModifica, setErroreModifica] = useState(null);

  function load() { api.get("/groups").then((r) => setList(r.data)); }
  useEffect(load, []);
  useEffect(() => { if (modifica?.id) document.getElementById("g-form-modifica")?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [modifica?.id]);
  useEffect(() => { api.get("/auth/users/simple").then((r) => setUtenti(r.data.filter((u) => !u.is_external))); }, []);

  const albero = elencoUffici(list);                // in ordine alfabetico a ogni livello, con il percorso intero

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try {
      await api.post("/groups", { ...form, parent_id: form.parent_id || null, responsabile_id: form.responsabile_id || null });
    } catch (err) { setErrore(erroreDi(err, "Impossibile creare l'ufficio")); return; }
    setForm(VUOTO);
    load();
  }

  async function remove(g) {
    if (!(await conferma("I sottouffici diventeranno di primo livello.", { titolo: `Eliminare l'ufficio «${g.etichetta}»?`, etichetta: "Elimina l'ufficio", pericolo: true }))) return;
    setErrore(null);
    try { await api.delete(`/groups/${g.id}`); } catch (err) { setErrore(erroreDi(err, "Impossibile eliminare l'ufficio")); return; }
    if (modifica?.id === g.id) setModifica(null);
    load();
  }

  function apriModifica(g) {
    setErroreModifica(null);
    setModifica({ id: g.id, etichetta: g.etichetta, valori: { name: g.name, description: g.description || "", color: g.color || "#5a6b8a",
      parent_id: g.parent_id || "", responsabile_id: g.responsabile_id || "", is_active: g.is_active !== false } });
  }

  async function salvaModifica(e) {
    e.preventDefault();
    setErroreModifica(null);
    const v = modifica.valori;
    try {
      // parent_id e responsabile_id vuoti tolgono il collegamento (l'ufficio torna di primo livello / senza responsabile)
      await api.put(`/groups/${modifica.id}`, { name: v.name, description: v.description, color: v.color,
        parent_id: v.parent_id || "", responsabile_id: v.responsabile_id || "", is_active: v.is_active });
    } catch (err) { setErroreModifica(erroreDi(err, "Impossibile salvare l'ufficio")); return; }
    setModifica(null);
    load();
  }

  const imposta = (campo) => (e) => setModifica({ ...modifica, valori: { ...modifica.valori, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value } });
  const impostaColore = (c) => setModifica((m) => ({ ...m, valori: { ...m.valori, color: c } }));
  const opzioniPadre = modifica ? elencoUffici(list, modifica.id) : [];   // senza l'ufficio stesso e il suo ramo

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Uffici</h2>
          <p>La struttura dell'organizzazione: uffici e sottouffici, ciascuno con il suo responsabile. Ogni persona interna sta in un solo ufficio (si sceglie dalla sua scheda in Utenti). Un percorso può essere assegnato a un ufficio e ai suoi sottouffici. Per le categorie trasversali (preposto, addetto antincendio...) usa le Mansioni.</p>
        </div>
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      <div className="card">
        <h3>Nuovo ufficio</h3>
        <form onSubmit={submit}>
          <div className="row">
            <div className="field"><label>Nome</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label>Colore</label><SelettoreColore valore={form.color} anteprima={form.name} onChange={(c) => setForm({ ...form, color: c })} /></div>
          </div>
          <div className="row">
            <div className="field"><label>Descrizione</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div className="field">
              <label>Sottoufficio di</label>
              <select value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value })}>
                <option value="">-- nessuno (primo livello) --</option>
                {albero.map((g) => <option key={g.id} value={g.id}>{g.etichetta}</option>)}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Responsabile</label>
            <select value={form.responsabile_id} onChange={(e) => setForm({ ...form, responsabile_id: e.target.value })}>
              <option value="">-- nessuno --</option>
              {utenti.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </select>
          </div>
          <button type="submit">Crea</button>
        </form>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Ufficio</th><th>Descrizione</th><th>Responsabile</th><th>Stato</th><th></th></tr></thead>
          <tbody>
            {albero.map((g) => (
              <React.Fragment key={g.id}>
              <tr>
                <td style={{ paddingLeft: 16 + g.livello * 24 }}>
                  {g.livello > 0 && <span className="text-muted" aria-hidden="true">└ </span>}
                  <span className="badge" style={{ background: g.color, color: "#fff" }}>{g.name}</span>
                </td>
                <td>{g.description}</td>
                <td>{g.responsabile_nome || "—"}</td>
                <td>{g.is_active === false ? <span className="badge gray">non attivo</span> : <span className="badge green">attivo</span>}</td>
                <td>
                  <button className="btn-sm" onClick={() => apriModifica(g)}>Modifica</button>{" "}
                  <button className="danger btn-sm" onClick={() => remove(g)}>Elimina</button>
                </td>
              </tr>
              {modifica?.id === g.id && (
                <tr>
                  <td colSpan={5} style={{ background: "var(--bg3)", paddingLeft: 16 + g.livello * 24 }}>
                    <form id="g-form-modifica" onSubmit={salvaModifica}>
                      <h4 style={{ margin: "8px 0" }}>Modifica «{modifica.etichetta}»</h4>
                      <div className="row">
                        <div className="field"><label htmlFor="g-nome">Nome</label><input id="g-nome" required autoFocus value={modifica.valori.name} onChange={imposta("name")} /></div>
                        <div className="field"><label htmlFor="g-colore">Colore</label><SelettoreColore id="g-colore" valore={modifica.valori.color} anteprima={modifica.valori.name} onChange={impostaColore} /></div>
                      </div>
                      <div className="field"><label htmlFor="g-descr">Descrizione</label><input id="g-descr" value={modifica.valori.description} onChange={imposta("description")} /></div>
                      <div className="row">
                        <div className="field">
                          <label htmlFor="g-padre">Sottoufficio di</label>
                          <select id="g-padre" value={modifica.valori.parent_id} onChange={imposta("parent_id")}>
                            <option value="">-- nessuno (primo livello) --</option>
                            {opzioniPadre.map((u) => <option key={u.id} value={u.id}>{u.etichetta}</option>)}
                          </select>
                          <span className="text-muted" style={{ fontSize: 12 }}>Scegli «nessuno» per togliere l'ufficio dalla gerarchia: diventa di primo livello. Non si può scegliere un suo sottoufficio.</span>
                        </div>
                        <div className="field">
                          <label htmlFor="g-resp">Responsabile</label>
                          <select id="g-resp" value={modifica.valori.responsabile_id} onChange={imposta("responsabile_id")}>
                            <option value="">-- nessuno --</option>
                            {utenti.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                          </select>
                        </div>
                      </div>
                      <div className="field">
                        <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={modifica.valori.is_active} onChange={imposta("is_active")} />Attivo</label>
                      </div>
                      {erroreModifica && <div className="error-msg">{erroreModifica}</div>}
                      <button type="submit">Salva</button>{" "}
                      <button type="button" className="secondary" onClick={() => setModifica(null)}>Annulla</button>
                    </form>
                  </td>
                </tr>
              )}
              </React.Fragment>
            ))}
            {albero.length === 0 && <tr><td colSpan={5} className="empty-state">Nessun ufficio ancora creato.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
