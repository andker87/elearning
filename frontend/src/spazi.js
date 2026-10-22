// Spazi di lavoro: «La mia formazione» per tutti, «Gestione» per la Formazione, «Amministrazione» per l'admin.
// Le pagine restano quelle di sempre; cambia solo il menu che le raccoglie.
export const SPAZI = {
  mia: { nome: "La mia formazione", icona: "learn", inizio: "/miei-corsi" },
  gestione: { nome: "Gestione", icona: "briefcase", inizio: "/da-gestire" },
  admin: { nome: "Amministrazione", icona: "gear", inizio: "/amministrazione" },
};

export function spaziDi(user) {
  const s = ["mia"];
  if (user?.poteri_formazione) s.push("gestione");
  if (user?.is_admin) s.push("admin");
  return s;
}

const PREFISSI = {
  gestione: ["/da-gestire", "/sessioni", "/percorsi", "/corsi", "/video", "/questionari", "/template-attestati", "/etichette", "/fabbisogno-admin",
    "/richieste-corso-admin", "/richieste-iscrizione", "/dashboard-formazione", "/dashboard-kpi", "/matrice-formativa", "/registro-formazione"],
  admin: ["/amministrazione", "/utenti", "/gruppi", "/mansioni", "/societa-formazione-esterne", "/reset-password-richieste", "/sincronizzazione-utenti",
    "/azienda", "/piattaforma", "/configurazione", "/informativa-privacy", "/stato-piattaforma", "/audit-log"],
  mia: ["/miei-corsi", "/catalogo", "/storico-corsi", "/mie-sessioni", "/risorse", "/fabbisogno", "/richiesta-corso"],
};

// A quale spazio appartiene una pagina (null = a nessuno in particolare, come le impostazioni personali).
export function spazioDelPercorso(pathname, search, spazi) {
  if (pathname.startsWith("/sessioni/")) {
    // la pagina di una sessione: chi la segue (?segui=1) o chi non gestisce la vede dalla sua formazione
    if (new URLSearchParams(search).get("segui") === "1" || !spazi.includes("gestione")) return "mia";
    return "gestione";
  }
  if (pathname.startsWith("/corsi/")) return spazi.includes("gestione") ? "gestione" : "mia";
  for (const s of ["gestione", "admin", "mia"]) {
    if (PREFISSI[s].some((p) => pathname === p || pathname.startsWith(p + "/"))) return spazi.includes(s) ? s : null;
  }
  return null;
}

const leggi = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const scrivi = (k, v) => { try { localStorage.setItem(k, v); } catch { /* preferenza non salvabile: vale solo ora */ } };

// Le preferenze sono per persona: sullo stesso browser chi entra dopo non eredita le pagine di chi c'era prima.
export function ultimoSpazio(userId) { return leggi(`spazio_ultimo_${userId}`); }
export function ultimaPagina(userId, spazio) { return leggi(`spazio_pagina_${userId}_${spazio}`); }
export function ricordaPagina(userId, spazio, percorso) { scrivi(`spazio_ultimo_${userId}`, spazio); scrivi(`spazio_pagina_${userId}_${spazio}`, percorso); }

// Dove si atterra dopo l'accesso: l'ultimo spazio usato; la prima volta «Gestione» per la Formazione, la Home per gli altri.
export function paginaIniziale(user) {
  const spazi = spaziDi(user);
  const ultimo = ultimoSpazio(user?.id);
  const spazio = ultimo && spazi.includes(ultimo) ? ultimo : (spazi.includes("gestione") ? "gestione" : "mia");
  return ultimaPagina(user?.id, spazio) || SPAZI[spazio].inizio;
}
