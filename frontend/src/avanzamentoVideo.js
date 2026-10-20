// Anti-salto del player: si puo' andare avanti solo guardando. `raggiunto` e' il punto piu' lontano toccato con la
// riproduzione normale (all'inizio quello che il server ricorda); un salto oltre `tolleranza` secondi viene annullato.
// Il bug della 2.7.1: il limite si confrontava con l'ultimo avanzamento CONFERMATO dal server (ogni 4 secondi), quindi
// guardando normalmente si superava il limite dopo 2-3 secondi e il video tornava all'inizio, in ciclo.
export const TOLLERANZA_SALTO = 2;

// Dato il punto `t` (secondi interi) e il `raggiunto` locale, dice dove stare: { raggiunto, riporta }.
export function controllaPunto(t, raggiunto, tolleranza = TOLLERANZA_SALTO) {
  if (t > raggiunto + tolleranza) return { raggiunto, riporta: true };      // salto in avanti: si torna al punto raggiunto
  return { raggiunto: Math.max(raggiunto, t), riporta: false };           // riproduzione normale: il traguardo avanza
}
