import React, { useEffect, useRef } from "react";

// Finestra di dialogo accessibile: si chiude con Esc (se `onChiudi` c'e'), il focus entra nella finestra e vi resta
// finche' e' aperta, poi torna dov'era.
export default function Finestra({ titolo, onChiudi, children, azioni }) {
  const ref = useRef(null);
  useEffect(() => {
    const prima = document.activeElement;
    ref.current && ref.current.focus();
    function tasto(e) {
      if (e.key === "Escape" && onChiudi) { e.stopPropagation(); onChiudi(); }
      if (e.key === "Tab" && ref.current) {
        const f = ref.current.querySelectorAll("button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
        if (!f.length) return;
        const primo = f[0], ultimo = f[f.length - 1];
        if (e.shiftKey && (document.activeElement === primo || document.activeElement === ref.current)) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primo.focus(); }
      }
    }
    document.addEventListener("keydown", tasto);
    return () => { document.removeEventListener("keydown", tasto); prima && prima.focus && prima.focus(); };
  }, []); // eslint-disable-line
  return (
    <div className="finestra-sfondo" onMouseDown={(e) => { if (e.target === e.currentTarget && onChiudi) onChiudi(); }}>
      <div className="finestra" role="dialog" aria-modal="true" aria-labelledby="finestra-titolo" tabIndex={-1} ref={ref}>
        <h3 id="finestra-titolo" style={{ marginTop: 0 }}>{titolo}</h3>
        <div className="finestra-corpo">{children}</div>
        {azioni && <div className="finestra-azioni">{azioni}</div>}
      </div>
    </div>
  );
}
