import React from "react";

// Intestazione di colonna cliccabile: primo clic ordina, secondo inverte la direzione.
export function ThOrdina({ campo, ordine, onOrdina, children, primoVerso = "asc" }) {
  const attivo = ordine.campo === campo;
  return (
    <th className={`ordinabile ${attivo ? "attivo" : ""}`} aria-sort={attivo ? (ordine.verso === "asc" ? "ascending" : "descending") : "none"}
        onClick={() => onOrdina({ campo, verso: attivo ? (ordine.verso === "asc" ? "desc" : "asc") : primoVerso })}>
      {children}<span className="freccia">{attivo ? (ordine.verso === "asc" ? "▲" : "▼") : "↕"}</span>
    </th>
  );
}

// Ordinamento in locale per le tabelle piccole (le grandi si ordinano sul server).
export function ordinaLocale(righe, ordine, lettori) {
  const leggi = lettori[ordine.campo];
  if (!leggi) return righe;
  const dir = ordine.verso === "asc" ? 1 : -1;
  return [...righe].sort((a, b) => {
    const x = leggi(a), y = leggi(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (typeof x === "string" ? x.localeCompare(y, "it") : x - y) * dir;
  });
}
