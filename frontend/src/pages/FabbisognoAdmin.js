import React, { useCallback, useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import ExportButton from "../components/ExportButton";
import AlberoOrigine from "../components/AlberoOrigine";
import { ThOrdina, ordinaLocale } from "../components/Ordinabile";

const STATO_LABEL = { in_revisione: "In revisione", approvata_hr: "Ricevuta", rifiutata: "Rifiutata dai responsabili", fusa: "Unita ad altre" };
const STATO_BADGE = { in_revisione: "gray", approvata_hr: "blue", rifiutata: "red" };
const SCHEDE = [{ id: "nuova", label: "Nuova campagna" }, { id: "campagne", label: "Campagne" }, { id: "richieste", label: "Richieste formative" }];
const data = (d) => (d ? new Date(d).toLocaleDateString("it-IT") : "—");
const periodo = (r) => r.riferimento_periodo || r.periodo || "—";

// ---- Nuova campagna ---------------------------------------------------------------------
function NuovaCampagna({ onCreata }) {
  const [form, setForm] = useState({ titolo: "", descrizione: "", scadenza: "" });
  const [errore, setErrore] = useState(null);
  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    try {
      await api.post("/fabbisogno/campagne", { ...form, scadenza: form.scadenza || null });
      setForm({ titolo: "", descrizione: "", scadenza: "" });
      onCreata();
    } catch (err) { setErrore(erroreDi(err, "Impossibile creare la campagna")); }
  }
  return (
    <div className="card">
      <h3>Nuova campagna</h3>
      <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>Invita i responsabili degli uffici di primo livello a indicare le esigenze di formazione. Chi ha sotto-uffici può rispondere o girare l'invito ai loro responsabili.</p>
      <form onSubmit={submit}>
        <div className="row">
          <div className="field"><label>Titolo</label><input required value={form.titolo} onChange={(e) => setForm({ ...form, titolo: e.target.value })} /></div>
          <div className="field"><label>Scadenza (opzionale)</label><input type="datetime-local" value={form.scadenza} onChange={(e) => setForm({ ...form, scadenza: e.target.value })} /></div>
        </div>
        <div className="field"><label>Descrizione</label><input value={form.descrizione} onChange={(e) => setForm({ ...form, descrizione: e.target.value })} /></div>
        {errore && <div className="error-msg">{errore}</div>}
        <button type="submit">Avvia campagna</button>
      </form>
    </div>
  );
}

// ---- Campagne ----------------------------------------------------------------------------
const LETTORI_CAMPAGNE = {
  titolo: (c) => c.titolo.toLowerCase(), creata: (c) => c.created_at, scadenza: (c) => c.scadenza, stato: (c) => c.stato,
  risposte: (c) => c.inviti_risposti, richieste: (c) => c.richieste,
};

function Campagne({ campagne, onChiudi, onApriRichieste }) {
  const [filtro, setFiltro] = useState({ q: "", stato: "" });
  const [ordine, setOrdine] = useState({ campo: "creata", verso: "desc" });
  const visibili = ordinaLocale(campagne.filter((c) => (!filtro.stato || c.stato === filtro.stato)
    && (!filtro.q || c.titolo.toLowerCase().includes(filtro.q.toLowerCase()))), ordine, LETTORI_CAMPAGNE);
  return (
    <div className="card">
      <h3>Campagne</h3>
      <div className="filtri-barra">
        <div className="field largo"><label>Cerca nel titolo</label><input value={filtro.q} onChange={(e) => setFiltro({ ...filtro, q: e.target.value })} /></div>
        <div className="field"><label>Stato</label>
          <select value={filtro.stato} onChange={(e) => setFiltro({ ...filtro, stato: e.target.value })}>
            <option value="">Tutte</option><option value="aperta">Aperte</option><option value="chiusa">Chiuse</option>
          </select>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr>
            <ThOrdina campo="titolo" ordine={ordine} onOrdina={setOrdine}>Titolo</ThOrdina>
            <ThOrdina campo="creata" ordine={ordine} onOrdina={setOrdine} primoVerso="desc">Avviata il</ThOrdina>
            <ThOrdina campo="scadenza" ordine={ordine} onOrdina={setOrdine}>Scadenza</ThOrdina>
            <ThOrdina campo="risposte" ordine={ordine} onOrdina={setOrdine} primoVerso="desc">Uffici che hanno risposto</ThOrdina>
            <ThOrdina campo="richieste" ordine={ordine} onOrdina={setOrdine} primoVerso="desc">Richieste</ThOrdina>
            <ThOrdina campo="stato" ordine={ordine} onOrdina={setOrdine}>Stato</ThOrdina>
            <th></th>
          </tr></thead>
          <tbody>
            {visibili.map((c) => {
              const totale = c.inviti_risposti + c.inviti_delegati + c.inviti_da_decidere;
              return (
                <tr key={c.id}>
                  <td>{c.titolo}{c.descrizione && <><br /><span className="text-muted" style={{ fontSize: 12 }}>{c.descrizione}</span></>}</td>
                  <td>{data(c.created_at)}</td>
                  <td>{c.scadenza ? new Date(c.scadenza).toLocaleString("it-IT") : "—"}</td>
                  <td>{c.inviti_risposti} su {totale}{c.inviti_delegati > 0 && <span className="text-muted" style={{ fontSize: 12 }}> ({c.inviti_delegati} girati ai sotto-uffici)</span>}</td>
                  <td>{c.richieste > 0 ? <button type="button" className="secondary btn-sm" onClick={() => onApriRichieste(c.id)}>{c.richieste} {c.richieste === 1 ? "richiesta" : "richieste"}</button> : "0"}</td>
                  <td><span className={`badge ${c.stato === "aperta" ? "green" : "gray"}`}>{c.stato === "aperta" ? "aperta" : "chiusa"}</span></td>
                  <td>{c.stato === "aperta" && <button className="danger btn-sm" onClick={() => onChiudi(c.id)}>Chiudi</button>}</td>
                </tr>
              );
            })}
            {visibili.length === 0 && <tr><td colSpan={7} className="empty-state">{campagne.length ? "Nessuna campagna per i filtri scelti." : "Nessuna campagna ancora avviata."}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---- Richieste formative -------------------------------------------------------------------
const PER_PAGINA = 25;
const FILTRI_VUOTI = { stato: "arrivate", campagna_id: "", ufficio_id: "", periodo: "", q: "" };

function RichiesteFormative({ campagne, campagnaIniziale }) {
  const [vista, setVista] = useState("argomento");
  const [filtri, setFiltri] = useState({ ...FILTRI_VUOTI, campagna_id: campagnaIniziale || "" });
  const [ordine, setOrdine] = useState({ campo: "persone", verso: "desc" });
  const [pagina, setPagina] = useState(1);
  const [dati, setDati] = useState(null);
  const [uffici, setUffici] = useState([]);
  const [aperto, setAperto] = useState(null);       // chiave del gruppo espanso
  const [dettaglio, setDettaglio] = useState([]);
  const [origineAperta, setOrigineAperta] = useState(null);
  const [errore, setErrore] = useState(null);

  useEffect(() => { api.get("/groups").then((r) => setUffici(r.data.filter((g) => g.is_ufficio))).catch((e) => setErrore(erroreDi(e, "Impossibile caricare gli uffici"))); }, []);
  const parametri = useCallback(() => {
    const p = { vista, pagina, per_pagina: PER_PAGINA, ordine: ordine.campo, direzione: ordine.verso };
    Object.entries(filtri).forEach(([k, v]) => { if (v) p[k] = v; });
    return p;
  }, [vista, pagina, ordine, filtri]);
  useEffect(() => {
    let attuale = true;  // una risposta arrivata in ritardo non deve sovrascrivere la vista corrente
    api.get("/fabbisogno/richieste-formative", { params: parametri() }).then((r) => { if (attuale) { setDati(r.data); setErrore(null); } })
      .catch((e) => { if (attuale) setErrore(erroreDi(e, "Impossibile caricare le richieste")); });
    return () => { attuale = false; };
  }, [parametri]);

  function cambiaVista(v) {
    setDati(null); setVista(v); setPagina(1); setAperto(null);
    setOrdine(v === "elenco" ? { campo: "data", verso: "desc" } : { campo: "persone", verso: "desc" });
  }
  const imposta = (k) => (e) => { setFiltri({ ...filtri, [k]: e.target.value }); setPagina(1); setAperto(null); };
  const ordina = (o) => { setOrdine(o); setPagina(1); };
  async function espandi(g) {
    if (aperto === g.chiave) { setAperto(null); return; }
    const p = { vista: "elenco", argomento: g.argomento, per_pagina: 200, ordine: "ufficio", direzione: "asc" };
    Object.entries(filtri).forEach(([k, v]) => { if (v) p[k] = v; });
    try {
      setDettaglio((await api.get("/fabbisogno/richieste-formative", { params: p })).data.items);
      setAperto(g.chiave);
    } catch (err) { setErrore(erroreDi(err, "Impossibile caricare il dettaglio")); }
  }
  function percorsoExport() {
    const p = new URLSearchParams({ ordine: vista === "elenco" ? ordine.campo : "data", direzione: vista === "elenco" ? ordine.verso : "desc" });
    Object.entries(filtri).forEach(([k, v]) => { if (v) p.set(k, v); });
    return `/fabbisogno/richieste-formative/export?${p.toString()}`;
  }

  // I dati valgono solo se arrivati per la vista che si sta guardando (i due formati sono diversi).
  if (dati && dati.vista !== vista) setDati(null);
  const pagine = dati ? Math.max(1, Math.ceil(dati.totale / PER_PAGINA)) : 1;
  const r = dati?.riepilogo;
  return (
    <div className="card">
      <div className="flex-between" style={{ alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div><h3 style={{ marginBottom: 2 }}>Richieste formative</h3><p className="text-muted" style={{ margin: 0, fontSize: 13 }}>Esigenze di formazione approvate dai responsabili</p></div>
        <ExportButton path={percorsoExport()} filename="richieste_formative" />
      </div>

      <div className="filtri-barra" style={{ marginTop: "1rem" }}>
        <div className="field largo"><label>Cerca (argomento, note, riferimento)</label><input value={filtri.q} onChange={imposta("q")} /></div>
        <div className="field"><label>Campagna</label>
          <select value={filtri.campagna_id} onChange={imposta("campagna_id")}>
            <option value="">Tutte</option><option value="spontanee">Solo richieste spontanee</option>
            {campagne.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
          </select>
        </div>
        <div className="field"><label>Ufficio (con i sotto-uffici)</label>
          <select value={filtri.ufficio_id} onChange={imposta("ufficio_id")}>
            <option value="">Tutti</option>{uffici.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Periodo</label>
          <select value={filtri.periodo} onChange={imposta("periodo")}>
            <option value="">Tutti</option><option value="mese">Mese</option><option value="trimestre">Trimestre</option><option value="semestre">Semestre</option><option value="anno">Anno</option>
          </select>
        </div>
        <div className="field"><label>Stato</label>
          <select value={filtri.stato} onChange={imposta("stato")}>
            <option value="arrivate">Ricevute</option><option value="in_revisione">In revisione</option><option value="rifiutate">Rifiutate dai responsabili</option><option value="tutte">Tutte</option>
          </select>
        </div>
        <div className="field stretto"><button type="button" className="secondary" onClick={() => { setFiltri({ ...FILTRI_VUOTI, campagna_id: campagnaIniziale || "" }); setPagina(1); }}>Azzera</button></div>
      </div>

      {errore && <div className="error-msg">{errore}</div>}
      {r && (
        <div className="riepilogo-numeri">
          <div><strong>{r.richieste}</strong><span>richieste</span></div>
          <div><strong>{r.argomenti}</strong><span>argomenti</span></div>
          <div><strong>{r.uffici}</strong><span>uffici</span></div>
          <div><strong>{r.persone}</strong><span>persone indicate</span></div>
        </div>
      )}

      <div className="segmenti" style={{ marginBottom: ".8rem" }}>
        <button type="button" className={vista === "argomento" ? "attivo" : ""} onClick={() => cambiaVista("argomento")}>Per argomento</button>
        <button type="button" className={vista === "elenco" ? "attivo" : ""} onClick={() => cambiaVista("elenco")}>Elenco dettagliato</button>
      </div>

      <div className="table-wrap">
        {vista === "argomento" ? (
          <table>
            <thead><tr>
              <ThOrdina campo="argomento" ordine={ordine} onOrdina={ordina}>Argomento</ThOrdina>
              <ThOrdina campo="persone" ordine={ordine} onOrdina={ordina} primoVerso="desc">Persone</ThOrdina>
              <ThOrdina campo="uffici" ordine={ordine} onOrdina={ordina} primoVerso="desc">Uffici</ThOrdina>
              <ThOrdina campo="richieste" ordine={ordine} onOrdina={ordina} primoVerso="desc">Richieste</ThOrdina>
              <th>Periodi indicati</th><th>Origine</th>
              <ThOrdina campo="ultima" ordine={ordine} onOrdina={ordina} primoVerso="desc">Ultima</ThOrdina>
            </tr></thead>
            <tbody>
              {dati?.vista === "argomento" && dati.items.map((g) => (
                <React.Fragment key={g.chiave}>
                  <tr onClick={() => espandi(g)} style={{ cursor: "pointer" }}>
                    <td><strong>{aperto === g.chiave ? "▾ " : "▸ "}{g.argomento}</strong></td>
                    <td>{g.persone}</td>
                    <td title={g.uffici.join(", ")}>{g.n_uffici}<span className="text-muted" style={{ fontSize: 12 }}> {g.uffici.slice(0, 2).join(", ")}{g.uffici.length > 2 ? "…" : ""}</span></td>
                    <td>{g.richieste}{g.richieste_originali !== g.richieste && <span className="text-muted" style={{ fontSize: 12 }}> (da {g.richieste_originali} originali)</span>}</td>
                    <td>{g.periodi.join(", ") || "—"}</td>
                    <td>{g.campagne.join(", ")}</td>
                    <td>{data(g.ultima)}</td>
                  </tr>
                  {aperto === g.chiave && Object.keys(g.per_campagna).length > 1 && (
                    <tr className="dettaglio-gruppo"><td colSpan={7}><strong>Persone per campagna:</strong> {Object.entries(g.per_campagna).map(([c, n]) => `${c}: ${n}`).join(" · ")}</td></tr>
                  )}
                  {aperto === g.chiave && dettaglio.map((d) => (
                    <tr key={d.id} className="dettaglio-gruppo">
                      <td colSpan={2}>{d.ufficio_origine_nome} <span className="text-muted">— {d.creata_da_nome}</span></td>
                      <td>{d.numero_persone_stimate == null ? "—" : `${d.numero_persone_stimate} ${d.numero_persone_stimate === 1 ? "persona" : "persone"}`}</td>
                      <td>{periodo(d)}</td>
                      <td colSpan={3}>{d.note || <span className="text-muted">nessuna nota</span>}</td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
              {dati && dati.items.length === 0 && <tr><td colSpan={7} className="empty-state">Nessuna richiesta per i filtri scelti.</td></tr>}
            </tbody>
          </table>
        ) : (
          <table>
            <thead><tr>
              <ThOrdina campo="ufficio" ordine={ordine} onOrdina={ordina}>Ufficio</ThOrdina>
              <ThOrdina campo="argomento" ordine={ordine} onOrdina={ordina}>Argomento</ThOrdina>
              <ThOrdina campo="periodo" ordine={ordine} onOrdina={ordina}>Periodo</ThOrdina>
              <ThOrdina campo="persone" ordine={ordine} onOrdina={ordina} primoVerso="desc">Persone</ThOrdina>
              <th>Note</th>
              <ThOrdina campo="campagna" ordine={ordine} onOrdina={ordina}>Origine</ThOrdina>
              <ThOrdina campo="stato" ordine={ordine} onOrdina={ordina}>Stato</ThOrdina>
              <ThOrdina campo="data" ordine={ordine} onOrdina={ordina} primoVerso="desc">Inviata il</ThOrdina>
            </tr></thead>
            <tbody>
              {dati?.vista === "elenco" && dati.items.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.e_unione ? d.uffici_origine.join(", ") : d.ufficio_origine_nome}<br />
                    {d.e_unione ? <><span className="badge blue">unione di {d.n_origini}</span> <button type="button" className="secondary btn-sm" onClick={() => setOrigineAperta(origineAperta === d.id ? null : d.id)}>{origineAperta === d.id ? "Nascondi" : "Provenienza"}</button></>
                      : <span className="text-muted" style={{ fontSize: 12 }}>{d.creata_da_nome}</span>}
                    {origineAperta === d.id && <AlberoOrigine id={d.id} />}
                  </td>
                  <td>{d.argomento}</td><td>{periodo(d)}</td><td>{d.numero_persone_stimate ?? "—"}</td><td>{d.note || "—"}</td>
                  <td>{d.campagna_titolo || "Spontanea"}</td>
                  <td><span className={`badge ${STATO_BADGE[d.stato]}`}>{STATO_LABEL[d.stato]}</span></td>
                  <td>{data(d.created_at)}</td>
                </tr>
              ))}
              {dati && dati.items.length === 0 && <tr><td colSpan={8} className="empty-state">Nessuna richiesta per i filtri scelti.</td></tr>}
            </tbody>
          </table>
        )}
      </div>

      {dati && dati.totale > PER_PAGINA && (
        <div className="paginazione">
          <button type="button" className="secondary btn-sm" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>← Precedente</button>
          <span className="text-muted" style={{ fontSize: 13 }}>Pagina {pagina} di {pagine} — {dati.totale} {vista === "argomento" ? "argomenti" : "richieste"}</span>
          <button type="button" className="secondary btn-sm" disabled={pagina >= pagine} onClick={() => setPagina(pagina + 1)}>Successiva →</button>
        </div>
      )}
    </div>
  );
}

export default function FabbisognoAdmin() {
  const [scheda, setScheda] = useState("campagne");
  const [campagne, setCampagne] = useState([]);
  const [campagnaFiltro, setCampagnaFiltro] = useState("");
  const [errore, setErrore] = useState(null);
  const carica = () => api.get("/fabbisogno/campagne").then((r) => setCampagne(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le campagne")));
  useEffect(() => { carica(); }, []);

  async function chiudi(id) {
    if (!window.confirm("Chiudere la campagna? I responsabili non potranno più rispondere agli inviti ancora aperti.")) return;
    setErrore(null);
    try { await api.put(`/fabbisogno/campagne/${id}/chiudi`); } catch (e) { setErrore(erroreDi(e, "Impossibile chiudere la campagna")); }
    carica();
  }

  return (
    <div>
      <div className="page-header"><div><h2>Fabbisogno formativo</h2><p>Avvia una campagna presso i responsabili e consulta le esigenze di formazione che arrivano.</p></div></div>
      <div className="tabs" role="tablist">
        {SCHEDE.map((x) => <button type="button" role="tab" aria-selected={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
      </div>
      {errore && <div className="error-msg">{errore}</div>}
      {scheda === "nuova" && <NuovaCampagna onCreata={() => { carica(); setScheda("campagne"); }} />}
      {scheda === "campagne" && <Campagne campagne={campagne} onChiudi={chiudi} onApriRichieste={(id) => { setCampagnaFiltro(id); setScheda("richieste"); }} />}
      {scheda === "richieste" && <RichiesteFormative key={campagnaFiltro} campagne={campagne} campagnaIniziale={campagnaFiltro} />}
    </div>
  );
}
