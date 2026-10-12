// Service worker minimo: serve solo a rendere l'app installabile (PWA) e a
// ricevere le notifiche push. Nessuna cache/offline volutamente - l'app
// richiede sempre una connessione per funzionare.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

// Passthrough di rete: nessuna intercettazione, serve solo a soddisfare il
// criterio di installabilità di alcuni browser (service worker attivo con
// un gestore "fetch", anche vuoto).
self.addEventListener("fetch", () => {});

self.addEventListener("push", (event) => {
  let dati = {};
  try {
    dati = event.data ? event.data.json() : {};
  } catch (e) {
    dati = { title: "Formazione", body: event.data ? event.data.text() : "" };
  }
  const titolo = dati.title || "Formazione";
  const opzioni = {
    body: dati.body || "",
    icon: "/api/azienda/icona?size=192",
    badge: "/api/azienda/icona?size=192",
    data: { url: dati.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(titolo, opzioni));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          if ("navigate" in client) client.navigate(url);
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
