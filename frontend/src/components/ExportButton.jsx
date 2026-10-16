import React, { useState, useRef, useEffect } from "react";
import { downloadFile } from "../api";

const FORMATI = [
  { value: "csv", formato: "csv", label: "CSV" },
  { value: "xlsx", formato: "xlsx", label: "Excel" },
  { value: "pdf-A4", formato: "pdf", pagina: "A4", label: "PDF (A4)" },
  { value: "pdf-A3", formato: "pdf", pagina: "A3", label: "PDF (A3)" },
];

// Bottone riusabile per ogni esportazione della piattaforma: stesso set di
// formati (CSV/Excel/PDF A4/A3) ovunque, path e filename passati dal chiamante.
export default function ExportButton({ path, filename, label = "Esporta" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onClick(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function scegli(opt) {
    setOpen(false);
    const sep = path.includes("?") ? "&" : "?";
    const url = `${path}${sep}formato=${opt.formato}${opt.pagina ? `&pagina=${opt.pagina}` : ""}`;
    downloadFile(url, `${filename}.${opt.formato}`);
  }

  return (
    <div style={{ position: "relative", display: "inline-block" }} ref={ref}>
      <button type="button" className="secondary" onClick={() => setOpen(!open)}>{label} ▾</button>
      {open && (
        <div className="export-menu">
          {FORMATI.map((f) => (
            <div key={f.value} className="export-menu-item" onClick={() => scegli(f)}>{f.label}</div>
          ))}
        </div>
      )}
    </div>
  );
}
