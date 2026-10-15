import React, { useEffect, useState } from "react";
import api, { erroreDi } from "../api";

const data = (d) => (d ? new Date(d).toLocaleString("it-IT") : "-");

function Elenco({ titolo, voci, colonne, vuoto }) {
  if (!voci.length) return <p className="text-muted" style={{ fontSize: 13 }}>{titolo}: {vuoto}</p>;
  return (
    <div style={{ marginBottom: 16 }}>
      <h4 style={{ margin: "8px 0" }}>{titolo} ({voci.length})</h4>
      <div className="table-wrap">
        <table>
          <thead><tr>{colonne.map((c) => <th key={c.titolo}>{c.titolo}</th>)}</tr></thead>
          <tbody>{voci.map((v, i) => <tr key={i}>{colonne.map((c) => <td key={c.titolo}>{c.valore(v)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

export default function SincronizzazioneUtenti() {
  const [stato, setStato] = useState(null);
  const [piano, setPiano] = useState(null);
  const [esito, setEsito] = useState(null);
  const [errore, setErrore] = useState(null);
  const [lavoro, setLavoro] = useState(false);
  const [riattiva, setRiattiva] = useState(false);

  const carica = () => api.get("/admin/entra/stato").then((r) => setStato(r.data));
  useEffect(() => { carica(); }, []);

  async function anteprima() {
    setLavoro(true); setErrore(null); setEsito(null);
    try { setPiano((await api.post("/admin/entra/anteprima")).data); }
    catch (err) { setPiano(null); setErrore(erroreDi(err, "Errore")); }
    finally { setLavoro(false); }
  }

  async function applica(forza) {
    if (!window.confirm("Applicare le modifiche mostrate? Chi viene disattivato perde l'accesso e le sue iscrizioni aperte vengono annullate (lo storico resta).")) return;
    setLavoro(true); setErrore(null);
    try {
      const r = await api.post("/admin/entra/applica", null, { params: { riattiva, forza, impronta: piano?.impronta } });
      setEsito(r.data); setPiano(null); carica();
    } catch (err) {
      setErrore(erroreDi(err, "Errore"));
      if (err.response?.status === 412) setPiano(null);
      if (err.response?.status === 409) setPiano((p) => ({ ...p, richiediForza: true }));
    } finally { setLavoro(false); }
  }

  if (!stato) return <p className="text-muted">Caricamento...</p>;
  const nulla = piano && !piano.crea.length && !piano.aggiorna.length && !piano.disattiva.length && !piano.riattiva.length;

  return (
    <div>
      <div className="page-header"><div><h2>Sincronizzazione utenti</h2>
        <p>Allinea gli utenti al gruppo Entra ID dell'azienda: chi entra viene creato, chi esce viene disattivato (lo storico formativo resta).</p></div></div>

      {!stato.configurato ? (
        <div className="card">
          <h3>Non configurata</h3>
          <p className="text-muted" style={{ fontSize: 13 }}>
            Si attiva dall'ambiente, non da qui: servono le credenziali Graph (<code>GRAPH_*</code>, con i permessi applicativi
            <code> User.Read.All</code> e <code>GroupMember.Read.All</code>) e l'id del gruppo Entra in <code>ENTRA_SYNC_GRUPPO_ID</code>.
            Con <code>ENTRA_SYNC_AUTO=true</code> il giro gira da solo ogni notte.
          </p>
        </div>
      ) : (
        <>
          <div className="card">
            <p style={{ marginTop: 0 }}>
              Giro notturno automatico: {stato.automatico ? <span className="badge green">attivo</span> : <span className="badge gray">spento (si lancia a mano da qui)</span>}
            </p>
            {stato.ultime.length > 0 && (
              <p className="text-muted" style={{ fontSize: 13 }}>
                Ultimo giro automatico: {data(stato.ultime[0].started_at)} — {stato.ultime[0].esito === "ok" ? stato.ultime[0].dettaglio : `errore (${(stato.ultime[0].errore || "").split("\n").filter(Boolean).pop()})`}
              </p>
            )}
            <button type="button" onClick={anteprima} disabled={lavoro}>{lavoro && !piano ? "Leggo da Entra..." : "Anteprima delle modifiche"}</button>
          </div>

          {errore && <div className="error-msg">{errore}</div>}

          {esito && (
            <div className="card">
              <h3>Sincronizzazione eseguita</h3>
              <p>Creati {esito.creati} · aggiornati {esito.aggiornati} · disattivati {esito.disattivati}{esito.riattivati ? ` · riattivati ${esito.riattivati}` : ""} · iscrizioni aperte annullate {esito.posti_liberati}</p>
              {esito.avvisi.length > 0 && (<><strong>Da sistemare a mano</strong><ul>{esito.avvisi.map((a, i) => <li key={i}>{a}</li>)}</ul></>)}
            </div>
          )}

          {piano && (
            <div className="card">
              <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
                Gruppo Entra: {piano.membri_entra} persone (domini {piano.domini.join(", ") || "-"}). Gli utenti esterni, quelli di altri domini e gli Admin tecnici non vengono mai toccati.
              </p>
              {piano.freno && <div className="error-msg">Piano sospetto: {piano.freno}.</div>}
              {nulla && <p>Gli utenti sono già allineati: niente da fare.</p>}
              <Elenco titolo="Da creare" voci={piano.crea} vuoto="nessuno"
                colonne={[{ titolo: "Email", valore: (v) => v.email }, { titolo: "Nome", valore: (v) => v.nome }, { titolo: "Data ingresso", valore: (v) => (v.data_ingresso ? new Date(v.data_ingresso).toLocaleDateString("it-IT") : "-") }]} />
              <Elenco titolo="Nome da aggiornare" voci={piano.aggiorna} vuoto="nessuno"
                colonne={[{ titolo: "Email", valore: (v) => v.email }, { titolo: "Ora", valore: (v) => v.da }, { titolo: "Diventa", valore: (v) => v.a }]} />
              <Elenco titolo="Da disattivare" voci={piano.disattiva} vuoto="nessuno"
                colonne={[{ titolo: "Persona", valore: (v) => <>{v.nome}<br /><span className="text-muted" style={{ fontSize: 12 }}>{v.email}</span></> }, { titolo: "Motivo", valore: (v) => v.motivo },
                          { titolo: "Attenzione", valore: (v) => (v.avvisi.length ? v.avvisi.join("; ") : "-") }]} />
              <Elenco titolo="Da riattivare (tornati nel gruppo)" voci={piano.riattiva} vuoto="nessuno"
                colonne={[{ titolo: "Email", valore: (v) => v.email }, { titolo: "Nome", valore: (v) => v.nome }]} />
              <Elenco titolo="Esclusi" voci={piano.esclusi} vuoto="nessuno"
                colonne={[{ titolo: "Email", valore: (v) => v.email }, { titolo: "Motivo", valore: (v) => v.motivo }]} />
              {!nulla && (
                <div>
                  {piano.riattiva.length > 0 && (
                    <label style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
                      <input type="checkbox" checked={riattiva} onChange={(e) => setRiattiva(e.target.checked)} /> Riattiva anche chi è tornato nel gruppo
                    </label>
                  )}
                  <button type="button" onClick={() => applica(false)} disabled={lavoro}>Applica le modifiche</button>{" "}
                  {piano.richiediForza && <button type="button" className="secondary" onClick={() => applica(true)} disabled={lavoro}>Applica comunque</button>}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
