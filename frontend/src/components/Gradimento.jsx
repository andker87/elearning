import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";
import Finestra from "./Finestra";

// Cinque pulsanti: si scelgono con il mouse e da tastiera (Tab e Invio/Spazio), e lo schermo li legge come "N stelle su 5".
function Stelle({ value, onChange, etichetta }) {
  return (
    <div role="group" aria-label={etichetta} style={{ display: "flex", gap: 6 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" onClick={() => onChange(n)} aria-pressed={n === value} aria-label={`${n} ${n === 1 ? "stella" : "stelle"} su 5`}
                style={{ cursor: "pointer", fontSize: 22, opacity: n <= value ? 1 : 0.3, background: "none", border: 0, padding: 0, color: "inherit", lineHeight: 1 }}>★</button>
      ))}
    </div>
  );
}

// In fondo alla pagina del corso: un link che apre il modulo in una finestra. Le domande aggiuntive le decide la Formazione.
export default function Gradimento({ iscrizioneId }) {
  const [modulo, setModulo] = useState(null);       // { gia_inviato, docenti, domande }
  const [aperto, setAperto] = useState(false);
  const [votoCorso, setVotoCorso] = useState(0);
  const [commento, setCommento] = useState("");
  const [votiDocenti, setVotiDocenti] = useState({});
  const [risposte, setRisposte] = useState({});
  const [inviato, setInviato] = useState(false);
  const [errore, setErrore] = useState(null);
  const [invio, setInvio] = useState(false);

  useEffect(() => {
    api.get(`/iscrizioni/${iscrizioneId}/gradimento/modulo`).then((r) => setModulo(r.data)).catch((e) => setErrore(erroreDi(e, "Impossibile caricare il modulo")));
  }, [iscrizioneId]);

  if (!modulo) return errore ? <p className="error-msg" role="alert">{errore}</p> : null;
  if (modulo.gia_inviato || inviato) return <p className="text-muted">Grazie per il tuo parere sul corso: è anonimo.</p>;

  const imposta = (id, v) => setRisposte((r) => ({ ...r, [id]: v }));
  const manca = votoCorso === 0 || modulo.docenti.some((d) => !votiDocenti[d.id])
    || modulo.domande.some((d) => d.obbligatoria && (risposte[d.id] === undefined || risposte[d.id] === "" || risposte[d.id] === null));

  async function invia(e) {
    e.preventDefault(); setErrore(null); setInvio(true);
    const compilate = Object.fromEntries(Object.entries(risposte).filter(([, v]) => v !== "" && v !== undefined && v !== null));
    try {
      await api.post(`/iscrizioni/${iscrizioneId}/gradimento`, { voto_corso: votoCorso, commento_corso: commento, voti_docenti: votiDocenti, risposte: compilate });
      setInviato(true); setAperto(false);
    } catch (err) { setErrore(erroreDi(err, "Invio non riuscito")); }
    setInvio(false);
  }

  return (
    <>
      <p style={{ margin: "1.2rem 0" }}>
        <button type="button" className="link" onClick={() => setAperto(true)} style={{ background: "none", border: 0, padding: 0, color: "var(--primary)", cursor: "pointer", textDecoration: "underline", font: "inherit" }}>Compila il test di gradimento</button>
        <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>Anonimo: la Formazione vede solo medie e commenti, non chi li ha scritti.</span>
      </p>
      {aperto && (
        <Finestra titolo="Il tuo parere sul corso" onChiudi={() => setAperto(false)}
          azioni={<>
            <button type="button" className="secondary" onClick={() => setAperto(false)}>Più tardi</button>
            <button type="submit" form="form-gradimento" disabled={manca || invio}>{invio ? "Invio..." : "Invia"}</button>
          </>}>
          <form id="form-gradimento" onSubmit={invia}>
            <div className="field"><label>Il corso nel complesso</label><Stelle value={votoCorso} onChange={setVotoCorso} etichetta="Voto del corso" /></div>
            <div className="field"><label htmlFor="g-commento">Commento sul corso (facoltativo)</label><textarea id="g-commento" rows={2} value={commento} onChange={(e) => setCommento(e.target.value)} /></div>
            {modulo.docenti.map((d) => (
              <div className="field" key={d.id}><label>Docente: {d.nome}</label>
                <Stelle value={votiDocenti[d.id] || 0} onChange={(n) => setVotiDocenti((v) => ({ ...v, [d.id]: n }))} etichetta={`Voto del docente ${d.nome}`} /></div>
            ))}
            {modulo.domande.map((d) => (
              <div className="field" key={d.id}>
                <label htmlFor={`g-${d.id}`}>{d.testo}{d.obbligatoria ? " *" : ""}</label>
                {d.tipo === "stelle" && <Stelle value={risposte[d.id] || 0} onChange={(n) => imposta(d.id, n)} etichetta={d.testo} />}
                {d.tipo === "si_no" && (
                  <div role="group" aria-label={d.testo} style={{ display: "flex", gap: 16 }}>
                    {[["si", "Sì"], ["no", "No"]].map(([v, et]) => (
                      <label key={v} style={{ display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
                        <input type="radio" style={{ width: "auto" }} name={`g-${d.id}`} checked={risposte[d.id] === v} onChange={() => imposta(d.id, v)} /> {et}</label>
                    ))}
                  </div>
                )}
                {d.tipo === "scelta" && (
                  <select id={`g-${d.id}`} value={risposte[d.id] || ""} onChange={(e) => imposta(d.id, e.target.value)}>
                    <option value="">-- scegli --</option>{d.opzioni.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                )}
                {d.tipo === "testo" && <textarea id={`g-${d.id}`} rows={2} maxLength={2000} value={risposte[d.id] || ""} onChange={(e) => imposta(d.id, e.target.value)} />}
              </div>
            ))}
            {errore && <div className="error-msg" role="alert">{errore}</div>}
          </form>
        </Finestra>
      )}
    </>
  );
}
