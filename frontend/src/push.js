import api from "./api";

function base64UrlToUint8Array(base64Url) {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export function pushSupportato() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function statoPermesso() {
  if (!pushSupportato()) return "unsupported";
  return Notification.permission; // "default" | "granted" | "denied"
}

export async function registraServiceWorker() {
  if (!("serviceWorker" in navigator)) return null;
  return navigator.serviceWorker.register("/service-worker.js");
}

export async function statoSottoscrizione() {
  if (!pushSupportato()) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

export async function attivaPush() {
  if (!pushSupportato()) throw new Error("Le notifiche push non sono supportate su questo browser/dispositivo.");
  const permesso = await Notification.requestPermission();
  if (permesso !== "granted") throw new Error("Permesso per le notifiche negato.");
  const reg = await navigator.serviceWorker.ready;
  const { data } = await api.get("/push/public-key");
  if (!data.public_key) throw new Error("Chiave VAPID non disponibile sul server.");
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: base64UrlToUint8Array(data.public_key),
  });
  const json = sub.toJSON();
  try {
    await api.post("/push/subscribe", { endpoint: json.endpoint, keys: json.keys });
  } catch (err) {
    // il server non l'ha salvata: si annulla anche nel browser, altrimenti il pulsante direbbe "attive" senza che arrivi nulla
    try { await sub.unsubscribe(); } catch { /* ignore */ }
    throw err;
  }
  return sub;
}

export async function disattivaPush() {
  const sub = await statoSottoscrizione();
  if (!sub) return;
  const endpoint = sub.endpoint;
  await api.post("/push/unsubscribe", { endpoint });  // prima il server: se fallisce, il browser resta sottoscritto e coerente
  await sub.unsubscribe();
}
