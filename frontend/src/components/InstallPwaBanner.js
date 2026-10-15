import React, { useEffect, useState } from "react";
import { statoInstallazione, sottoscriviInstallazione, installaApp } from "../pwaInstall";

const DISMISS_KEY = "pwa_install_dismesso";

function standalone() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}
function iOS() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

export default function InstallPwaBanner() {
  const [errore, setErrore] = useState("");
  const [stato, setStato] = useState(statoInstallazione());
  const [chiuso, setChiuso] = useState(() => {
    try { return !!localStorage.getItem(DISMISS_KEY); } catch { return false; }
  });

  useEffect(() => sottoscriviInstallazione(() => setStato(statoInstallazione())), []);

  if (chiuso || standalone() || stato.installata) return null;
  const mostraIos = iOS() && !stato.disponibile;
  if (!stato.disponibile && !mostraIos) return null;

  function chiudi() {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
    setChiuso(true);
  }

  async function installa() {
    setErrore("");
    try {
      const esito = await installaApp();
      if (esito === "accepted") chiudi();  // se l'utente rinuncia, il banner resta per un'altra volta
    } catch { setErrore("Installazione non riuscita"); }
  }

  return (
    <div className="mini-banner mini-banner-primary">
      <span className="mini-banner-icon">📲</span>
      <span className="mini-banner-text">
        {mostraIos
          ? <>Tocca <strong>Condividi</strong> → <strong>"Aggiungi a schermata Home"</strong> per installare l'app.</>
          : "Installa l'app sulla schermata Home per un accesso più rapido."}
        {errore && <span style={{ color: "var(--red-text)" }}> {errore}</span>}
      </span>
      {stato.disponibile && (
        <button type="button" className="btn-sm" onClick={installa}>Installa</button>
      )}
      <button type="button" className="mini-banner-close" onClick={chiudi} title="Chiudi">✕</button>
    </div>
  );
}
