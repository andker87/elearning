import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { erroreDi } from "../api";
import Icona from "../components/Icona";
import { STATO_PASSO } from "../components/PersonePercorso";
import { MODALITA } from "../sessioni";

function addMonths(date, months) {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}
const MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
const ora = (d) => new Date(d).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });

// La Home di chi segue i corsi: in cima la prossima cosa da fare, poi appuntamenti, percorsi e scadenze.
export default function MieCorsi() {
  const [iscrizioni, setIscrizioni] = useState(null);
  const [percorsi, setPercorsi] = useState([]);
  const [errore, setErrore] = useState(null);
  const user = (() => { try { return JSON.parse(localStorage.getItem("user") || "null"); } catch { return null; } })();

  useEffect(() => {
    api.get("/edizioni/mie/iscrizioni").then((r) => setIscrizioni(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare i tuoi corsi")));
    api.get("/percorsi/mie").then((r) => setPercorsi(r.data)).catch(() => {});
  }, []);

  if (errore) return <div className="error-msg" role="alert">{errore}</div>;
  if (!iscrizioni) return <p className="text-muted">Caricamento...</p>;

  const now = new Date();
  const aperte = iscrizioni.filter((i) => (i.stato === "iscritto" || i.stato === "in_lista_attesa") && i.edizione_stato !== "chiusa" && i.edizione_stato !== "annullata");
  const prossime = aperte.filter((i) => i.edizione_data_inizio && !i.edizione_sempre_aperta && new Date(i.edizione_data_fine || i.edizione_data_inizio) >= now)
    .sort((a, b) => new Date(a.edizione_data_inizio) - new Date(b.edizione_data_inizio));
  // video da seguire adesso: prima quelli iniziati (dal piu' avanti), poi quelli non ancora aperti
  const daSeguire = aperte.filter((i) => i.stato === "iscritto" && i.video_pct != null && i.video_disponibile && i.video_pct < 100)
    .sort((a, b) => (b.video_pct || 0) - (a.video_pct || 0));
  const continua = daSeguire[0];
  const altri = daSeguire.slice(1);
  const percorsiInCorso = percorsi.filter((p) => !p.completato);
  const inScadenza = iscrizioni
    .filter((i) => i.stato === "completato" && i.completato_at && i.corso_validita_mesi)
    .map((i) => ({ ...i, scadenza: addMonths(i.completato_at, i.corso_validita_mesi) }))
    .filter((i) => (i.scadenza - now) / (1000 * 3600 * 24) <= 30);
  const daRipetere = iscrizioni.filter((i) => i.ripeti_entro);
  const nome = (user?.full_name || "").split(" ")[0];
  const riassunto = [
    daSeguire.length ? `${daSeguire.length} ${daSeguire.length === 1 ? "corso da continuare" : "corsi da continuare"}` : null,
    prossime.length ? `${prossime.length} ${prossime.length === 1 ? "appuntamento in programma" : "appuntamenti in programma"}` : null,
  ].filter(Boolean).join(" e ");

  return (
    <div>
      <div className="page-header"><div><h2>{nome ? `Ciao ${nome}` : "Home"}</h2><p>{riassunto ? `Hai ${riassunto}.` : "Niente in programma per ora: trovi i corsi aperti a tutti nel Catalogo."}</p></div>
        <Link to="/catalogo" className="btn-link">Catalogo →</Link></div>

      {continua && (
        <div className="card continua">
          <div className="continua-anteprima" aria-hidden="true"><Icona nome="play" /></div>
          <div style={{ display: "grid", gap: ".45rem", minWidth: 0 }}>
            <span className="sopratitolo">{continua.video_pct > 0 ? "Continua da dove eri" : "Da iniziare"}</span>
            <h3 style={{ margin: 0 }}>{continua.corso_titolo}</h3>
            <div className="barra-avanzamento" role="progressbar" aria-valuenow={Math.round(continua.video_pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Avanzamento del video"><i style={{ width: `${continua.video_pct}%` }} /></div>
            <div className="flex-between" style={{ gap: ".6rem", flexWrap: "wrap" }}>
              <span className="text-muted" style={{ fontSize: ".85rem" }}>{Math.round(continua.video_pct)}% visto{continua.edizione_sempre_aperta ? " · sempre disponibile" : ""}</span>
              <Link to={`/sessioni/${continua.edizione_id}?segui=1`}><button type="button">{continua.video_pct > 0 ? "Riprendi il video" : "Inizia"}</button></Link>
            </div>
          </div>
        </div>
      )}

      <div className="due-colonne">
        <div className="card">
          <h3>Prossimi appuntamenti</h3>
          {prossime.length === 0 && <p className="empty-state" style={{ margin: 0 }}>Nessun appuntamento in programma.</p>}
          {prossime.slice(0, 6).map((i) => {
            const d = new Date(i.edizione_data_inizio);
            return (
              <div className="appuntamento" key={i.id}>
                <div className="data-blocco"><span>{MESI[d.getMonth()]}</span><b>{String(d.getDate()).padStart(2, "0")}</b></div>
                <div style={{ minWidth: 0 }}><Link to={`/sessioni/${i.edizione_id}?segui=1`}><strong>{i.corso_titolo}</strong></Link>
                  <div className="text-muted piccolo">{ora(d)} · {MODALITA[i.edizione_modalita] || i.edizione_modalita}{i.edizione_luogo ? ` · ${i.edizione_luogo}` : ""}</div></div>
                <span className={`badge ${i.stato === "in_lista_attesa" ? "yellow" : "green"}`}>{i.stato === "in_lista_attesa" ? "lista d'attesa" : "iscritto"}</span>
              </div>
            );
          })}
        </div>

        <div style={{ display: "grid", gap: "1rem" }}>
          {percorsiInCorso.length > 0 && (
            <div className="card">
              <h3>I tuoi percorsi</h3>
              {percorsiInCorso.map((p) => {
                const fatti = p.steps.filter((s) => s.completato).length;
                const prossimo = p.steps.find((s) => !s.completato && s.stato !== "bloccato");
                return (
                  <div key={p.assegnazione_id} style={{ padding: ".4rem 0" }}>
                    <div className="flex-between"><strong>{p.nome}</strong><span className="text-muted piccolo">{fatti} di {p.steps.length}</span></div>
                    <div className="tappe" aria-label={`${fatti} corsi completati su ${p.steps.length}`}>
                      {p.steps.map((s) => <i key={s.step_id} className={s.completato ? "fatta" : s === prossimo ? "ora" : ""} title={`${s.corso_titolo}: ${(STATO_PASSO[s.stato] || [, s.stato])[1]}`} />)}
                    </div>
                    {prossimo && (
                      <div className="text-muted piccolo" style={{ marginTop: ".3rem" }}>
                        Prossimo: {prossimo.edizione_id ? <Link to={`/sessioni/${prossimo.edizione_id}?segui=1`}>{prossimo.corso_titolo}</Link> : prossimo.corso_titolo}
                        {" — "}{(STATO_PASSO[prossimo.stato] || [, prossimo.stato])[1]}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {(inScadenza.length > 0 || daRipetere.length > 0) && (
            <div className="card" style={{ borderColor: "var(--yellow)", background: "var(--yellow-bg)" }}>
              <h3>Da tenere d'occhio</h3>
              {inScadenza.map((i) => (
                <p key={i.id} style={{ margin: ".25rem 0", color: "var(--text)" }}><strong>{i.corso_titolo}</strong> {i.scadenza < now ? "è scaduto" : `scade il ${i.scadenza.toLocaleDateString("it-IT")}`}: è previsto un rinnovo.</p>
              ))}
              {daRipetere.map((i) => (
                <p key={i.id} style={{ margin: ".25rem 0", color: "var(--text)" }}><strong>{i.corso_titolo}</strong> va ripetuto entro il {new Date(i.ripeti_entro).toLocaleDateString("it-IT")} (test non superato).</p>
              ))}
            </div>
          )}
          {altri.length > 0 && (
            <div className="card">
              <h3>Altri corsi da continuare</h3>
              {altri.map((i) => (
                <div key={i.id} className="flex-between" style={{ padding: ".4rem 0", gap: ".6rem" }}>
                  <div style={{ minWidth: 0, flex: 1 }}><strong>{i.corso_titolo}</strong><div className="barra-avanzamento" style={{ marginTop: ".3rem" }}><i style={{ width: `${i.video_pct}%` }} /></div></div>
                  <Link to={`/sessioni/${i.edizione_id}?segui=1`}>{i.video_pct > 0 ? "Continua" : "Inizia"}</Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <p style={{ marginTop: "1rem" }}><Link to="/storico-corsi">Storico e attestati →</Link></p>
    </div>
  );
}
