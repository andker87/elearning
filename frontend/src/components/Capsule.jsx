import React from "react";

// Ruoli di una persona come capsule colorate: stesso colore e stesso nome ovunque (elenco, legenda, modulo di modifica).
// «Docente» e' la qualifica di chi puo' essere scelto come docente nelle edizioni (nel codice is_formatore: «is_docente»
// e' un'altra cosa, chi ha gia' un'edizione assegnata). Un esterno e' docente per definizione.
export const RUOLI = {
  admin: { label: "Admin", tip: "Configura la piattaforma; ha anche i poteri della Formazione" },
  formazione: { label: "Formazione", tip: "Gestisce corsi, edizioni, iscrizioni e attestati" },
  docente: { label: "Docente", tip: "Può essere scelto come docente nelle edizioni" },
  esterno: { label: "Esterno", tip: "Docente di una società terza: non segue corsi, non ha ufficio né mansioni" },
  utente: { label: "Utente", tip: "Segue i corsi: nessun permesso particolare" },
};
export const ORDINE_RUOLI = ["admin", "formazione", "docente", "esterno", "utente"];

export function ruoliDi(u) {
  const r = [];
  if (u.is_admin) r.push("admin");
  if (u.is_formazione) r.push("formazione");
  if (u.is_formatore || u.is_external) r.push("docente");
  if (u.is_external) r.push("esterno");
  return r.length ? r : ["utente"];
}

export function Capsula({ ruolo }) {
  const r = RUOLI[ruolo];
  return <span className={`capsula ${ruolo}`} title={r.tip}>{r.label}</span>;
}

export function Capsule({ utente }) {
  return <span className="capsule">{ruoliDi(utente).map((r) => <Capsula key={r} ruolo={r} />)}</span>;
}

export function LegendaRuoli() {
  return (
    <div className="legenda-ruoli" aria-label="Significato dei ruoli">
      {ORDINE_RUOLI.map((k) => <span key={k}><Capsula ruolo={k} /> {RUOLI[k].tip}</span>)}
    </div>
  );
}
