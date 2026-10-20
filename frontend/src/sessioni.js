// Presentazione delle sessioni, condivisa dalle pagine Sessioni, Il mio team e Richieste di iscrizione.
export const MODALITA = { presenza: "Presenza", ibrida: "Ibrida", remoto: "Remoto", video: "Video", esterna: "Esterna" };
export const STATI = { bozza: ["gray", "Bozza"], pianificata: ["blue", "Pianificata"], in_corso: ["yellow", "In corso"], chiusa: ["green", "Chiusa"], annullata: ["red", "Annullata"] };
export const STATI_ISCRIZIONE = { iscritto: ["green", "iscritta/o"], in_lista_attesa: ["yellow", "in lista d'attesa"], completato: ["green", "completato"], non_completato: ["red", "non completato"], richiesta_in_attesa: ["yellow", "richiesta in attesa"] };

// «21/10/2026, 03:10 – 12:10» (stesso giorno) oppure «21/10/2026 03:10 → 22/10/2026 12:10»
export function quando(e) {
  if (e.sempre_aperta) return "Sempre disponibile";
  if (!e.data_inizio) return "—";
  const i = new Date(e.data_inizio), f = e.data_fine ? new Date(e.data_fine) : null;
  const giorno = (d) => d.toLocaleDateString("it-IT"), ora = (d) => d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  if (!f) return `${giorno(i)}, ${ora(i)}`;
  return giorno(i) === giorno(f) ? `${giorno(i)}, ${ora(i)} – ${ora(f)}` : `${giorno(i)} ${ora(i)} → ${giorno(f)} ${ora(f)}`;
}

export function dove(e) {
  if (e.modalita === "video") return "Video";
  if (e.modalita === "remoto") return "Online";
  if (e.modalita === "ibrida") return e.luogo ? `${e.luogo} + online` : "In sede + online";
  return e.luogo || (e.modalita === "esterna" && e.ente_erogatore) || "—";
}
