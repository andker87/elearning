import axios from "axios";

// Gli array diventano parametri ripetuti (?etichette=a&etichette=b), come si aspetta il backend.
const api = axios.create({ baseURL: "/api", paramsSerializer: { indexes: null } });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Un login sbagliato risponde 401: il messaggio va mostrato, non ricaricata la pagina.
    const url = (err.config && err.config.url) || "";
    if (err.response && err.response.status === 401 && !url.includes("/auth/login")) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Il profilo (permessi, ufficio...) si legge dal server a ogni avvio: dopo un aggiornamento della piattaforma o un
// cambio di permessi il menu resta giusto senza rifare l'accesso. Se fallisce si lavora col profilo gia' salvato.
export async function allineaProfilo() {
  if (!localStorage.getItem("token")) return;
  try {
    const r = await api.get("/auth/me", { timeout: 5000 });   // se il server non risponde, parte comunque la pagina
    localStorage.setItem("user", JSON.stringify(r.data));
  } catch (e) { /* offline o server in avvio: si resta con il profilo salvato */ }
}

// Le rotte di export (CSV/PDF) richiedono il Bearer token: un <a href> puro
// non lo manda, quindi si scarica come blob autenticato invece di navigare.
export async function downloadFile(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

// Per aprire un file protetto (PDF) in una nuova scheda: un link diretto non porta il token.
export async function apriFile(path) {
  const res = await api.get(path, { responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(res.data);
  window.open(blobUrl, "_blank", "noopener");
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
}

// Il testo da mostrare per un errore di una richiesta: il "detail" del server (stringa) oppure, per gli errori di
// validazione (array), i messaggi uniti; senza risposta (rete assente) un testo chiaro invece di niente.
export function erroreDi(err, predefinito = "Operazione non riuscita") {
  if (err && !err.response && err.request) return "Il server non risponde: controlla la connessione e riprova";
  const d = err && err.response && err.response.data && err.response.data.detail;
  if (typeof d === "string" && d) return d;
  if (Array.isArray(d) && d.length) return d.map((x) => (x && x.msg) || String(x)).join("; ");
  return predefinito;
}

export default api;
