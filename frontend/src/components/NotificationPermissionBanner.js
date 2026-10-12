import React, { useEffect, useState } from "react";
import { pushSupportato, statoPermesso, attivaPush } from "../push";

const DISMISS_KEY = "push_prompt_dismesso";

export default function NotificationPermissionBanner() {
  const [visibile, setVisibile] = useState(false);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState("");

  useEffect(() => {
    if (!pushSupportato()) return;
    try { if (localStorage.getItem(DISMISS_KEY)) return; } catch { /* ignore */ }
    setVisibile(statoPermesso() === "default");
  }, []);

  if (!visibile) return null;

  async function attiva() {
    setCaricamento(true);
    setErrore("");
    try {
      await attivaPush();
    } catch (err) {
      setErrore(err.message || "Errore nell'attivazione delle notifiche");
    } finally {
      setCaricamento(false);
      setVisibile(false);
    }
  }

  function chiudi() {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
    setVisibile(false);
  }

  return (
    <div className="mini-banner">
      <span className="mini-banner-icon">🔔</span>
      <span className="mini-banner-text">
        Attiva le notifiche per ricevere scadenze e solleciti anche ad app chiusa.
        {errore && <span style={{ color: "var(--red-text)" }}> {errore}</span>}
      </span>
      <button type="button" className="btn-sm" disabled={caricamento} onClick={attiva}>{caricamento ? "..." : "Attiva"}</button>
      <button type="button" className="mini-banner-close" onClick={chiudi} title="Chiudi">✕</button>
    </div>
  );
}
