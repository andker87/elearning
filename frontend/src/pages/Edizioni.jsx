import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api, { erroreDi } from "../api";
import EliminaSessione from "../components/EliminaSessione";
import { FiltroEtichette, ChipEtichette } from "../components/Etichette";
import CampoDurata from "../components/CampoDurata";
import { formattaDurata } from "../durata";
import { MODALITA, STATI, quando, dove } from "../sessioni";

const SCHEDE = [{ id: "elenco", label: "Elenco sessioni" }, { id: "nuova", label: "Nuova sessione" }];
const PER_PAGINA = [25, 50, 100];
const VUOTO = { corso_id: "", modalita: "presenza", checkin_mode: "discente_validato", luogo: "", ente_erogatore: "", posti_max: "", lista_attesa_abilitata: false,
  data_inizio: "", data_fine: "", video_id: "", durata_minuti: null, sempre_aperta: false, pubblica_subito: false };

const toLocalInput = (d) => { const p = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; };

export default function Edizioni() {
  const navigate = useNavigate();
  const [scheda, setScheda] = useState("elenco");
  const [list, setList] = useState([]);
  const [corsi, setCorsi] = useState([]);
  const [video, setVideo] = useState([]);
  const [filtroEtichette, setFiltroEtichette] = useState([]);
  const [filtro, setFiltro] = useState({ testo: "", stato: "", modalita: "", corso: "", da: "", a: "" });
  const [ordine, setOrdine] = useState({ col: "quando", verso: -1 });
  const [pagina, setPagina] = useState(0);
  const [perPagina, setPerPagina] = useState(25);
  const [form, setForm] = useState(VUOTO);
  const [durataToccata, setDurataToccata] = useState(false);
  const [errore, setErrore] = useState(null);

  function load() { api.get("/edizioni", { params: filtroEtichette.length ? { etichette: filtroEtichette } : {} }).then((r) => setList(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare le sessioni"))); }
  useEffect(() => { load(); }, [filtroEtichette]); // eslint-disable-line
  useEffect(() => { api.get("/corsi").then((r) => setCorsi(r.data)); api.get("/video").then((r) => setVideo(r.data.filter((v) => v.stato === "pronto"))); }, []);

  const corsoScelto = corsi.find((c) => c.id === form.corso_id);
  // La durata parte da quella del corso, finche' chi organizza non la cambia
  // Da «Da gestire»: «Crea una sessione» per un corso che ha persone in attesa apre il modulo con quel corso gia' scelto.
  const corsoDaCreare = new URLSearchParams(useLocation().search).get("nuova");
  const [precompilato, setPrecompilato] = useState(false);
  useEffect(() => {
    if (corsoDaCreare && !precompilato && corsi.some((c) => c.id === corsoDaCreare)) { setScheda("nuova"); scegliCorso(corsoDaCreare); setPrecompilato(true); }
  }, [corsi, corsoDaCreare]); // eslint-disable-line

  function scegliCorso(id) {
    const c = corsi.find((x) => x.id === id);
    setForm({ ...form, corso_id: id, durata_minuti: durataToccata ? form.durata_minuti : (c?.durata_minuti ?? null) });
  }
  function fineSuggerita() {
    if (!form.data_inizio || !form.durata_minuti || form.durata_minuti >= 24 * 60) return;
    setForm({ ...form, data_fine: toLocalInput(new Date(new Date(form.data_inizio).getTime() + form.durata_minuti * 60000)) });
  }

  async function submit(e) {
    e.preventDefault();
    setErrore(null);
    const libera = form.modalita === "video" && form.sempre_aperta;       // sempre disponibile: niente date né posti
    const payload = { ...form, sempre_aperta: libera, posti_max: form.posti_max && !libera ? parseInt(form.posti_max, 10) : null,
      data_inizio: !libera && form.data_inizio ? form.data_inizio : null, data_fine: !libera && form.data_fine ? form.data_fine : null,
      ente_erogatore: form.modalita === "esterna" ? (form.ente_erogatore || null) : null, luogo: form.modalita === "video" || form.modalita === "remoto" ? "" : form.luogo,
      durata_minuti: form.durata_minuti || null };
    delete payload.pubblica_subito;
    let r;
    try { r = await api.post("/edizioni", payload); }
    catch (err) { setErrore(erroreDi(err, "Impossibile creare la sessione")); return; }
    setForm(VUOTO); setDurataToccata(false);
    if (form.pubblica_subito) {        // la sessione esiste gia': se la pubblicazione fallisce non se ne crea una seconda
      try { await api.post(`/edizioni/${r.data.id}/pianifica`); }
      catch (err) { window.alert(`Sessione creata in bozza, ma non pubblicata: ${erroreDi(err, "pubblicazione non riuscita")}. Puoi pubblicarla dalla sua pagina.`); }
    }
    load(); navigate(`/sessioni/${r.data.id}`);
  }

  const [daEliminare, setDaEliminare] = useState(null);

  async function pubblica(id) {
    try { await api.post(`/edizioni/${id}/pianifica`); load(); } catch (err) { setErrore(erroreDi(err, "Impossibile pubblicare la sessione")); }
  }

  async function duplica(id) {
    try { await api.post(`/edizioni/${id}/duplica`); load(); } catch (err) { setErrore(erroreDi(err, "Impossibile duplicare la sessione")); }
  }

  function cambiaFiltro(campo, valore) { setFiltro({ ...filtro, [campo]: valore }); setPagina(0); }
  function ordinaPer(col) { setOrdine(ordine.col === col ? { col, verso: -ordine.verso } : { col, verso: 1 }); }

  const COLONNE = [
    { id: "corso", label: "Corso", valore: (e) => (e.corso_titolo || "").toLowerCase() },
    { id: "modalita", label: "Modalità", valore: (e) => MODALITA[e.modalita] || e.modalita },
    { id: "quando", label: "Quando", valore: (e) => e.data_inizio || "" },
    { id: "durata", label: "Durata", valore: (e) => e.durata_effettiva_minuti || 0 },
    { id: "luogo", label: "Luogo", valore: (e) => dove(e).toLowerCase() },
    { id: "docenti", label: "Docenti", valore: (e) => (e.docenti || []).map((d) => d.nome).join(", ").toLowerCase() },
    { id: "iscritti", label: "Iscritti", valore: (e) => e.n_iscritti || 0 },
    { id: "stato", label: "Stato", valore: (e) => e.stato },
  ];
  const cerca = filtro.testo.trim().toLowerCase();
  const colOrdine = COLONNE.find((c) => c.id === ordine.col) || COLONNE[2];
  const visibili = list
    .filter((e) => (!cerca || `${e.corso_titolo} ${e.luogo || ""} ${(e.docenti || []).map((d) => d.nome).join(" ")} ${e.ente_erogatore || ""}`.toLowerCase().includes(cerca))
      && (!filtro.stato || e.stato === filtro.stato) && (!filtro.modalita || e.modalita === filtro.modalita) && (!filtro.corso || e.corso_id === filtro.corso)
      && (!filtro.da || (e.data_inizio && e.data_inizio.slice(0, 10) >= filtro.da)) && (!filtro.a || (e.data_inizio && e.data_inizio.slice(0, 10) <= filtro.a)))
    .sort((a, b) => {
      const x = colOrdine.valore(a), y = colOrdine.valore(b);
      if (x === y) return 0;
      if (colOrdine.id === "quando" && (!x || !y)) return !x ? 1 : -1;      // le sessioni senza data stanno in fondo
      return ordine.verso * (typeof x === "number" ? x - y : String(x).localeCompare(String(y), "it", { numeric: true, sensitivity: "base" }));
    });
  const pagineTotali = Math.max(1, Math.ceil(visibili.length / perPagina));
  const paginaCorrente = Math.min(pagina, pagineTotali - 1);
  const inPagina = visibili.slice(paginaCorrente * perPagina, (paginaCorrente + 1) * perPagina);

  return (
    <div>
      {daEliminare && <EliminaSessione sessioneId={daEliminare.id} nome={daEliminare.corso_titolo || "questo corso"} onChiudi={() => setDaEliminare(null)} onEliminata={() => { setDaEliminare(null); load(); }} />}
      <div className="page-header"><div><h2>Sessioni</h2><p>Le singole sessioni di un corso: quando, dove, chi insegna e chi partecipa.</p></div></div>
      <div className="tabs">
        {SCHEDE.map((x) => <button type="button" aria-pressed={scheda === x.id} key={x.id} className={`tab ${scheda === x.id ? "active" : ""}`} onClick={() => setScheda(x.id)}>{x.label}</button>)}
      </div>
      {errore && <div className="error-msg">{errore}</div>}

      {scheda === "nuova" && (
        <div className="card">
          <h3>Nuova sessione</h3>
          <form onSubmit={submit}>
            <div className="row">
              <div className="field">
                <label>Corso</label>
                <select required value={form.corso_id} onChange={(e) => scegliCorso(e.target.value)}>
                  <option value="">-- seleziona --</option>
                  {corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Modalità</label>
                <select value={form.modalita} onChange={(e) => setForm({ ...form, modalita: e.target.value })}>
                  <option value="presenza">Presenza</option>
                  <option value="ibrida">Ibrida</option>
                  <option value="remoto">Full-remote</option>
                  <option value="video">Video</option>
                  <option value="esterna">Esterna (ente accreditato)</option>
                </select>
              </div>
            </div>
            <div className="row">
              <CampoDurata valore={form.durata_minuti} id="sessione-durata" onChange={(d) => { setDurataToccata(true); setForm({ ...form, durata_minuti: d }); }}
                suggerimento={corsoScelto?.durata_minuti
                  ? (form.durata_minuti === corsoScelto.durata_minuti ? `Dal corso: ${formattaDurata(corsoScelto.durata_minuti)}.` : `Il corso prevede ${formattaDurata(corsoScelto.durata_minuti)}: stai forzando la durata di questa sessione.`)
                  : (form.corso_id ? "Il corso non ha una durata: scrivila qui (vale solo per questa sessione) o aggiungila al corso." : "")} />
              {corsoScelto?.durata_minuti && form.durata_minuti !== corsoScelto.durata_minuti && (
                <div className="field" style={{ alignSelf: "flex-end" }}><button type="button" className="secondary btn-sm" onClick={() => { setDurataToccata(false); setForm({ ...form, durata_minuti: corsoScelto.durata_minuti }); }}>Ripristina la durata del corso</button></div>
              )}
            </div>
            {(form.modalita === "presenza" || form.modalita === "ibrida") && (
              <div className="row">
                <div className="field">
                  <label>Modalità check-in (parte in sede)</label>
                  <select value={form.checkin_mode} onChange={(e) => setForm({ ...form, checkin_mode: e.target.value })}>
                    <option value="discente_validato">Check-in discente + validazione docente</option>
                    <option value="docente">Check-in docente (registro digitale)</option>
                  </select>
                </div>
                <div className="field"><label>Luogo</label><input value={form.luogo} onChange={(e) => setForm({ ...form, luogo: e.target.value })} /></div>
              </div>
            )}
            {form.modalita === "esterna" && (
              <div className="row">
                <div className="field"><label>Ente erogatore</label><input value={form.ente_erogatore} onChange={(e) => setForm({ ...form, ente_erogatore: e.target.value })} /></div>
                <div className="field"><label>Luogo (facoltativo)</label><input value={form.luogo} onChange={(e) => setForm({ ...form, luogo: e.target.value })} /></div>
              </div>
            )}
            {!(form.modalita === "video" && form.sempre_aperta) && <div className="row">
              <div className="field"><label>Posti massimi (vuoto = illimitati)</label><input type="number" min="1" value={form.posti_max} onChange={(e) => setForm({ ...form, posti_max: e.target.value })} /></div>
              {form.posti_max && (
                <div className="field">
                  <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input type="checkbox" style={{ width: "auto" }} checked={form.lista_attesa_abilitata} onChange={(e) => setForm({ ...form, lista_attesa_abilitata: e.target.checked })} />
                    Abilita lista d'attesa
                  </label>
                </div>
              )}
            </div>}
            {form.modalita === "video" && (
              <div className="field">
                <label>Contenuto video</label>
                <select required value={form.video_id} onChange={(e) => setForm({ ...form, video_id: e.target.value })}>
                  <option value="">-- seleziona --</option>
                  {video.map((v) => <option key={v.id} value={v.id}>{v.titolo}</option>)}
                </select>
                {video.length === 0 && <p className="text-muted" style={{ fontSize: 12 }}>Nessun video pronto — caricane uno nella sezione Video.</p>}
              </div>
            )}
            {form.modalita === "video" && (
              <div className="field">
                <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input type="checkbox" style={{ width: "auto" }} checked={form.sempre_aperta} onChange={(e) => setForm({ ...form, sempre_aperta: e.target.checked })} />
                  Sempre disponibile (senza date)
                </label>
                <p className="text-muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                  {form.sempre_aperta
                    ? "Chi vuole la guarda quando preferisce, dal Catalogo, anche se il corso non ha l'auto-iscrizione."
                    : "Senza questa scelta il video si apre dall'ora che indichi (e fino alla data di fine, se la indichi; altrimenti resta disponibile finché la Formazione non chiude la sessione)."}
                  {" "}Chi lo completa (e supera il test finale, se c'è) riceve l'attestato in automatico.
                </p>
              </div>
            )}
            {!(form.modalita === "video" && form.sempre_aperta) && <div className="row">
              <div className="field"><label>{form.modalita === "video" ? "Disponibile dal (data e ora)" : "Data/ora inizio"}</label><input type="datetime-local" value={form.data_inizio} onChange={(e) => setForm({ ...form, data_inizio: e.target.value })} /></div>
              <div className="field">
                <label>{form.modalita === "video" ? "Disponibile fino al (facoltativo)" : "Data/ora fine"}</label>
                <input type="datetime-local" value={form.data_fine} onChange={(e) => setForm({ ...form, data_fine: e.target.value })} />
                {form.data_inizio && form.durata_minuti > 0 && form.durata_minuti < 24 * 60 && <button type="button" className="secondary btn-sm" style={{ marginTop: 4 }} onClick={fineSuggerita}>Imposta la fine in base alla durata</button>}
              </div>
            </div>}
            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" style={{ width: "auto" }} checked={form.pubblica_subito} onChange={(e) => setForm({ ...form, pubblica_subito: e.target.checked })} />
                Pubblica subito
              </label>
              <p className="text-muted" style={{ fontSize: 12, margin: "4px 0 0" }}>Se non la pubblichi resta in bozza: la prepari con calma e la pubblichi quando è pronta. Finché è in bozza nessuno la vede né può iscriversi.</p>
            </div>
            <button type="submit">Crea sessione</button>
          </form>
        </div>
      )}

      {scheda === "elenco" && <>
        <div className="card">
          <div className="row">
            <div className="field"><label htmlFor="s-cerca">Cerca</label><input id="s-cerca" placeholder="corso, luogo, docente" value={filtro.testo} onChange={(e) => cambiaFiltro("testo", e.target.value)} /></div>
            <div className="field"><label htmlFor="s-stato">Stato</label>
              <select id="s-stato" value={filtro.stato} onChange={(e) => cambiaFiltro("stato", e.target.value)}><option value="">Tutti</option>{Object.entries(STATI).map(([k, [, l]]) => <option key={k} value={k}>{l}</option>)}</select></div>
            <div className="field"><label htmlFor="s-mod">Modalità</label>
              <select id="s-mod" value={filtro.modalita} onChange={(e) => cambiaFiltro("modalita", e.target.value)}><option value="">Tutte</option>{Object.entries(MODALITA).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
            <div className="field"><label htmlFor="s-corso">Corso</label>
              <select id="s-corso" value={filtro.corso} onChange={(e) => cambiaFiltro("corso", e.target.value)}><option value="">Tutti</option>{corsi.map((c) => <option key={c.id} value={c.id}>{c.titolo}</option>)}</select></div>
            <div className="field"><label htmlFor="s-da">Dal</label><input id="s-da" type="date" value={filtro.da} onChange={(e) => cambiaFiltro("da", e.target.value)} /></div>
            <div className="field"><label htmlFor="s-a">Al</label><input id="s-a" type="date" value={filtro.a} onChange={(e) => cambiaFiltro("a", e.target.value)} /></div>
          </div>
          <div style={{ maxWidth: 420 }}><FiltroEtichette valore={filtroEtichette} onChange={setFiltroEtichette} /></div>
          <span aria-live="polite" className="text-muted" style={{ fontSize: 13 }}>{visibili.length} sessioni{visibili.length !== list.length ? ` su ${list.length}` : ""}</span>
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
              {inPagina.map((e) => {
                const [classeStato, etichettaStato] = STATI[e.stato] || ["gray", e.stato];
                return (
                  <tr key={e.id}>
                    <td>{e.corso_titolo}{e.corso_etichette?.length > 0 && <div style={{ marginTop: 4 }}><ChipEtichette etichette={e.corso_etichette} /></div>}</td>
                    <td><span className="badge gray">{MODALITA[e.modalita] || e.modalita}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>{quando(e)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {e.durata_effettiva_minuti ? formattaDurata(e.durata_effettiva_minuti) : <span className="text-muted">—</span>}
                      {e.durata_modificata && <span className="badge yellow" style={{ marginLeft: 6 }} title={`Il corso prevede ${formattaDurata(e.durata_corso_minuti)}`}>modificata</span>}
                    </td>
                    <td>{dove(e)}</td>
                    <td>{e.docenti?.length ? e.docenti.map((d) => d.nome).join(", ") : <span className="text-muted">—</span>}</td>
                    <td>{e.n_iscritti}{e.posti_max ? `/${e.posti_max}` : ""}{e.n_lista_attesa > 0 && <div className="text-muted" style={{ fontSize: 11 }}>{e.n_lista_attesa} in attesa</div>}</td>
                    <td><span className={`badge ${classeStato}`}>{etichettaStato}</span>{e.da_chiudere && <span className="badge yellow" style={{ marginLeft: 6 }} title="La fine è passata: va chiusa dalla Formazione">da chiudere</span>}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", whiteSpace: "nowrap" }}>
                        <button type="button" className="btn-sm" onClick={() => navigate(`/sessioni/${e.id}`)}>Apri</button>
                        {e.stato === "bozza" && <button type="button" className="btn-sm" onClick={() => pubblica(e.id)}>Pubblica</button>}
                        <button type="button" className="secondary btn-sm" onClick={() => duplica(e.id)}>Duplica</button>
                        {e.stato !== "chiusa" && <button type="button" className="danger btn-sm" onClick={() => setDaEliminare(e)}>Elimina</button>}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {inPagina.length === 0 && <tr><td colSpan={9} className="text-muted">{list.length === 0 ? "Nessuna sessione ancora: creane una dalla scheda «Nuova sessione»." : "Nessuna sessione corrisponde ai filtri."}</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="flex-between" style={{ marginTop: 12 }}>
          <span>
            <label htmlFor="s-pp" className="text-muted" style={{ fontSize: 13, marginRight: 6 }}>Per pagina</label>
            <select id="s-pp" style={{ width: "auto" }} value={perPagina} onChange={(e) => { setPerPagina(Number(e.target.value)); setPagina(0); }}>{PER_PAGINA.map((n) => <option key={n} value={n}>{n}</option>)}</select>
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
