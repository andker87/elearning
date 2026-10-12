// Cattura l'evento beforeinstallprompt non appena il browser lo emette (prima
// che qualunque componente sia montato), così resta disponibile per il banner
// di installazione senza il rischio di perderlo se arriva prima del render.
// Il browser lo emette solo in contesto sicuro (HTTPS o localhost) e solo se
// manifest + service worker soddisfano i criteri di installabilità.

let deferredPrompt = null;
let installata = false;
const listeners = new Set();

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
  listeners.forEach((fn) => fn());
});

window.addEventListener("appinstalled", () => {
  deferredPrompt = null;
  installata = true;
  listeners.forEach((fn) => fn());
});

export function statoInstallazione() {
  return { disponibile: !!deferredPrompt, installata };
}

export function sottoscriviInstallazione(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function installaApp() {
  if (!deferredPrompt) return null;
  deferredPrompt.prompt();
  const scelta = await deferredPrompt.userChoice;
  deferredPrompt = null;
  listeners.forEach((fn) => fn());
  return scelta.outcome; // "accepted" | "dismissed"
}
