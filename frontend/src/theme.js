import { useState } from "react";

const CHIAVE = "tema";

export function temaIniziale() {
  try {
    const salvato = localStorage.getItem(CHIAVE);
    if (salvato === "dark" || salvato === "light") return salvato;
  } catch { /* localStorage non disponibile */ }
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applicaTema(tema) {
  document.documentElement.setAttribute("data-theme", tema);
}

export function useTema() {
  const [tema, setTema] = useState(() => document.documentElement.getAttribute("data-theme") || temaIniziale());
  function alterna() {
    const nuovo = tema === "dark" ? "light" : "dark";
    applicaTema(nuovo);
    try { localStorage.setItem(CHIAVE, nuovo); } catch { /* ignore */ }
    setTema(nuovo);
  }
  return [tema, alterna];
}
