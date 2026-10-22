import React from "react";
import Icona from "./Icona";

// Copertina di un corso: l'immagine caricata dalla Formazione; se non c'e', un fondo colorato scelto dal titolo con l'icona del tipo
// di corso, cosi' ogni corso ha un aspetto suo e quelli senza immagine non sembrano incompleti.
const TINTE = [["#0E7C66", "#08493c"], ["#2D5DA8", "#1c3a6b"], ["#9A5B12", "#5e370a"], ["#7B3F8F", "#4b2358"],
  ["#3F5C6B", "#26394a"], ["#A8324F", "#6a1d31"], ["#5C7A1E", "#394d10"], ["#4553B8", "#2b3477"]];
const ICONE = { video: "play", presenza: "board", ibrida: "users", remoto: "board", esterna: "award" };

function tintaDi(titolo) {
  let h = 0;
  for (const c of titolo || "") h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return TINTE[h % TINTE.length];
}

export default function Copertina({ url, titolo, modalita, className = "", style }) {
  const [da, a] = tintaDi(titolo);
  const [rotta, setRotta] = React.useState(false);
  React.useEffect(() => { setRotta(false); }, [url]);
  return (
    <div className={`copertina ${className}`} style={style} aria-hidden="true">
      {url && !rotta
        ? <img src={url} alt="" loading="lazy" onError={() => setRotta(true)} />
        : <div className="copertina-generata" style={{ background: `linear-gradient(135deg, ${da}, ${a})` }}><Icona nome={ICONE[modalita] || "book"} size={28} /></div>}
    </div>
  );
}
