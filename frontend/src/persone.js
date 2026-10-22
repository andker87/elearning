import { useEffect, useState } from "react";
import api from "./api";

// Elenco semplice delle persone (id, nome, ufficio...), usato da molte pagine: una sola richiesta ogni 30 secondi,
// condivisa tra le pagine che lo chiedono insieme. Un errore non resta in cache.
let cache = null, quando = 0, tokenCache = null;
function leggiPersone() {
  const token = localStorage.getItem("token");          // chi entra dopo non deve vedere l'elenco chiesto da chi c'era prima
  if (!cache || token !== tokenCache || Date.now() - quando > 30000) {
    quando = Date.now(); tokenCache = token;
    cache = api.get("/auth/users/simple").then((r) => r.data).catch((e) => { cache = null; throw e; });
  }
  return cache;
}

export function usePersone(allaFalla) {
  const [persone, setPersone] = useState([]);
  useEffect(() => {
    let vivo = true;
    leggiPersone().then((d) => vivo && setPersone(d)).catch((e) => allaFalla && allaFalla(e));
    return () => { vivo = false; };
  }, []); // eslint-disable-line
  return persone;
}
