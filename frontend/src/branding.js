import { useEffect, useState } from "react";
import api from "./api";

const PREDEFINITO = { nome_piattaforma: "E-Learning", nome_azienda: null, logo_url: null };
let cache = null;
let inflight = null;
const ascoltatori = new Set();

function applica(dati) {
  cache = dati;
  document.title = dati.nome_piattaforma;
  ascoltatori.forEach((f) => f(dati));
}

export function caricaBranding() {
  if (!inflight) {
    inflight = api.get("/azienda/pubblica").then((r) => applica(r.data)).catch(() => { inflight = null; });
  }
  return inflight;
}

export function aggiornaBranding() {
  inflight = null;
  return caricaBranding();
}

export function useBranding() {
  const [dati, setDati] = useState(cache || PREDEFINITO);
  useEffect(() => {
    ascoltatori.add(setDati);
    caricaBranding();
    return () => ascoltatori.delete(setDati);
  }, []);
  return dati;
}
