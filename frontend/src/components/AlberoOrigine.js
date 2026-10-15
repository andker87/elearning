import React, { useEffect, useState } from "react";
import api from "../api";

const periodoDi = (n) => n.riferimento_periodo || n.periodo || null;
const dataIt = (d) => new Date(d).toLocaleDateString("it-IT");

function Nodo({ n }) {
  const dettagli = [n.numero_persone_stimate != null && `${n.numero_persone_stimate} ${n.numero_persone_stimate === 1 ? "persona" : "persone"}`, periodoDi(n)].filter(Boolean).join(" · ");
  return (
    <li>
      <div>
        <strong>{n.ufficio_nome}</strong> <span className="text-muted">— {n.creata_da_nome}, {dataIt(n.created_at)}</span>
        {n.e_unione && <span className="badge blue" style={{ marginLeft: 6 }}>unione</span>}
      </div>
      <div>«{n.argomento}»{dettagli && <span className="text-muted"> · {dettagli}</span>}</div>
      {n.note && <div className="text-muted" style={{ fontSize: 12 }}>Nota: {n.note}</div>}
      {n.figli.length > 0 && <ul className="albero-origine">{n.figli.map((f) => <Nodo key={f.id} n={f} />)}</ul>}
    </li>
  );
}

// Da dove viene una richiesta: l'unione, le richieste che contiene, e cosi' via fino alle originali.
export default function AlberoOrigine({ id }) {
  const [albero, setAlbero] = useState(null);
  const [errore, setErrore] = useState(null);
  useEffect(() => {
    api.get(`/fabbisogno/richieste/${id}/origine`).then((r) => setAlbero(r.data)).catch((e) => setErrore(e.response?.data?.detail || "Provenienza non disponibile"));
  }, [id]);
  if (errore) return <p className="text-muted" style={{ fontSize: 13 }}>{errore}</p>;
  if (!albero) return <p className="text-muted" style={{ fontSize: 13 }}>Carico la provenienza...</p>;
  return <ul className="albero-origine radice">{<Nodo n={albero} />}</ul>;
}
