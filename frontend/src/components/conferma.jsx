import React from "react";
import { createRoot } from "react-dom/client";
import Finestra from "./Finestra";

// Conferma nella finestra della piattaforma (al posto di window.confirm, che e' grigia, diversa per ogni browser e non dice
// cosa succede). Uso: if (!(await conferma("Cosa succede", { titolo: "Eliminare…?", etichetta: "Elimina", pericolo: true }))) return;
function Dialogo({ testo, titolo, etichetta, pericolo, onFine }) {
  return (
    <Finestra titolo={titolo} onChiudi={() => onFine(false)}
      azioni={<>
        <button type="button" className="secondary" onClick={() => onFine(false)}>Indietro</button>
        <button type="button" className={pericolo ? "danger" : ""} onClick={() => onFine(true)}>{etichetta}</button>
      </>}>
      {testo && <p style={{ margin: 0 }}>{testo}</p>}
    </Finestra>
  );
}

export function conferma(testo, { titolo = "Confermi?", etichetta = "Conferma", pericolo = false } = {}) {
  return new Promise((resolve) => {
    const nodo = document.createElement("div");
    document.body.appendChild(nodo);
    const radice = createRoot(nodo);
    const fine = (ok) => { radice.unmount(); nodo.remove(); resolve(ok); };
    radice.render(<Dialogo testo={testo} titolo={titolo} etichetta={etichetta} pericolo={pericolo} onFine={fine} />);
  });
}
