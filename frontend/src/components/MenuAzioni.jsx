import React, { useEffect, useRef, useState } from "react";
import Icona from "./Icona";

// Un pulsante che apre un piccolo menu di azioni (per esempio «Esporta ▾»). Si chiude con Esc, cliccando fuori o scegliendo.
export default function MenuAzioni({ etichetta, icona, voci, className = "secondary" }) {
  const [aperto, setAperto] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!aperto) return undefined;
    const fuori = (e) => { if (ref.current && !ref.current.contains(e.target)) setAperto(false); };
    const tasto = (e) => { if (e.key === "Escape") setAperto(false); };
    document.addEventListener("mousedown", fuori); document.addEventListener("keydown", tasto);
    return () => { document.removeEventListener("mousedown", fuori); document.removeEventListener("keydown", tasto); };
  }, [aperto]);
  return (
    <div className="menu-azioni" ref={ref}>
      <button type="button" className={className} aria-haspopup="menu" aria-expanded={aperto} onClick={() => setAperto(!aperto)}>
        {icona && <Icona nome={icona} size={16} />}{etichetta}<Icona nome="chevron-down" size={14} />
      </button>
      {aperto && (
        <div className="menu-azioni-elenco" role="menu">
          {voci.map((v) => (
            <button key={v.etichetta} type="button" role="menuitem" className={v.pericolo ? "pericolo" : ""} onClick={() => { setAperto(false); v.azione(); }}>{v.etichetta}</button>
          ))}
        </div>
      )}
    </div>
  );
}
