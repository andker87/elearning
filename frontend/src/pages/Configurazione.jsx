import React, { useRef, useState } from "react";
import api, { downloadFile, erroreDi } from "../api";
import ExportButton from "../components/ExportButton";
import { conferma } from "../components/conferma";

const NOMI = { azienda: "Dati aziendali", gruppi: "Gruppi e uffici", organizzazioni: "Società di formazione", corsi: "Corsi", percorsi: "Percorsi formativi" };
const ELENCHI = [
  { titolo: "Utenti", path: "/auth/users/export", file: "utenti" },
  { titolo: "Gruppi e uffici", path: "/admin/gruppi-export", file: "gruppi" },
  { titolo: "Società di formazione", path: "/organizzazioni-export/elenco", file: "societa_formazione" },
  { titolo: "Catalogo corsi", path: "/corsi-export/elenco", file: "corsi" },
  { titolo: "Percorsi formativi", path: "/corsi-export/percorsi", file: "percorsi" },
];

function Riepilogo({ r }) {
  return (
    <>
      <p style={{ margin: "0 0 .6rem" }}>
        <strong>{r.totali.creati}</strong> da creare · <strong>{r.totali.aggiornati}</strong> da aggiornare. Niente viene cancellato.
      </p>
      {Object.entries(NOMI).map(([k, nome]) => {
        const s = r.sezioni[k];
        if (!s) return null;  // il file di un'altra versione puo' non avere questa sezione
        if (!s.creati.length && !s.aggiornati.length) return <p key={k} className="text-muted" style={{ fontSize: 13, margin: "2px 0" }}>{nome}: nessuna differenza{s.invariati ? ` (${s.invariati} già uguali)` : ""}</p>;
        return (
          <div key={k} style={{ margin: ".6rem 0" }}>
            <strong>{nome}</strong> <span className="text-muted" style={{ fontSize: 12 }}>({s.invariati} già uguali)</span>
            <ul style={{ margin: ".2rem 0", paddingLeft: "1.2rem", fontSize: 13 }}>
              {s.creati.map((n) => <li key={"c" + n}><span className="badge green">nuovo</span> {n}</li>)}
              {s.aggiornati.map((a) => <li key={"a" + a.nome}><span className="badge blue">aggiorna</span> {a.nome} <span className="text-muted">— {a.campi.join(", ")}</span></li>)}
            </ul>
          </div>
        );
      })}
      {r.avvisi.length > 0 && (
        <div className="card card-muted">
          <strong>Da sapere</strong>
          <ul style={{ margin: ".3rem 0 0", paddingLeft: "1.2rem", fontSize: 13 }}>{r.avvisi.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
    </>
  );
}

export default function Configurazione() {
  const [file, setFile] = useState(null);       // { nome, contenuto }
  const [anteprima, setAnteprima] = useState(null);
  const [esito, setEsito] = useState(null);
  const [errore, setErrore] = useState(null);
  const [lavoro, setLavoro] = useState(false);
  const input = useRef(null);

  async function scegli(e) {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    setErrore(null); setEsito(null); setAnteprima(null);
    let contenuto;
    try { contenuto = JSON.parse(await f.text()); } catch { setErrore("Il file non è un JSON valido."); return; }
    setLavoro(true);
    try {
      const r = await api.post("/admin/configurazione/import", { contenuto, applica: false });
      setFile({ nome: f.name, contenuto }); setAnteprima(r.data);
    } catch (err) { setFile(null); setErrore(erroreDi(err, "Importazione non riuscita")); }
    finally { setLavoro(false); }
  }

  async function applica() {
    if (!(await conferma("Vengono aggiunti e aggiornati elementi; non si cancella nulla.", { titolo: "Applicare le modifiche mostrate?", etichetta: "Applica le modifiche" }))) return;
    setLavoro(true); setErrore(null);
    try {
      const r = await api.post("/admin/configurazione/import", { contenuto: file.contenuto, applica: true });
      setEsito(r.data); setAnteprima(null); setFile(null);
    } catch (err) { setErrore(erroreDi(err, "Importazione non riuscita")); }
    finally { setLavoro(false); }
  }

  const niente = anteprima && anteprima.totali.creati === 0 && anteprima.totali.aggiornati === 0;
  return (
    <div>
      <div className="page-header"><div><h2>Configurazione</h2><p>Porta le impostazioni da un ambiente all'altro, o ricostruiscile dopo un errore. Non è un backup: persone, iscrizioni ed esiti restano nel backup dell'infrastruttura.</p></div></div>

      <div className="card">
        <h3>Esporta la configurazione</h3>
        <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
          Un file con dati aziendali e impostazioni della piattaforma (con il testo dell'informativa privacy), gruppi e uffici con la gerarchia e i responsabili, società di formazione, catalogo corsi e percorsi formativi.
        </p>
        <p className="text-muted" style={{ fontSize: 13 }}>
          <strong>Non incluso, per ora:</strong> utenti, iscrizioni ed esiti; video, immagini e loghi; template degli attestati; test e domande; credenziali e chiavi (SMTP, accesso aziendale e Graph restano nell'ambiente).
        </p>
        <button type="button" onClick={() => downloadFile("/admin/configurazione/export", `configurazione-${new Date().toISOString().slice(0, 10)}.json`)}>Scarica la configurazione</button>
      </div>

      <div className="card">
        <h3>Importa una configurazione</h3>
        <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
          Scegli un file esportato da questa piattaforma: prima vedi cosa verrebbe creato e aggiornato, poi decidi se applicare. Chi è già presente viene riconosciuto per nome (corsi, percorsi, gruppi, società) e aggiornato; non si cancella mai nulla.
        </p>
        <input ref={input} type="file" accept="application/json,.json" onChange={scegli} style={{ display: "none" }} />
        <button type="button" className="secondary" onClick={() => input.current.click()} disabled={lavoro}>{lavoro && !anteprima ? "Leggo il file..." : "Scegli il file e guarda l'anteprima"}</button>
        {errore && <div className="error-msg">{errore}</div>}
      </div>

      {anteprima && (
        <div className="card">
          <h3>Anteprima di «{file.nome}»</h3>
          <Riepilogo r={anteprima} />
          {niente ? <p>La configurazione è già allineata a questo file: niente da fare.</p>
            : <button type="button" onClick={applica} disabled={lavoro}>Applica queste modifiche</button>}{" "}
          <button type="button" className="secondary" onClick={() => { setAnteprima(null); setFile(null); }}>Annulla</button>
        </div>
      )}
      {esito && (
        <div className="card">
          <h3>Configurazione importata</h3>
          <Riepilogo r={esito} />
        </div>
      )}

      <div className="card">
        <h3>Elenchi in tabella</h3>
        <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>Gli stessi elenchi sono anche nelle rispettive pagine. Per leggerli, non per importarli.</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
          {ELENCHI.map((e) => <div key={e.file}><div style={{ fontSize: 13, marginBottom: 4 }}>{e.titolo}</div><ExportButton path={e.path} filename={e.file} /></div>)}
        </div>
      </div>
    </div>
  );
}
