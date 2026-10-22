// Formattazione di date e ore per l'interfaccia (italiano). Un solo punto da cambiare per tutta l'app.
export const dataIt = (d, vuoto = "—") => (d ? new Date(d).toLocaleDateString("it-IT") : vuoto);
export const dataOraIt = (d, vuoto = "—") => (d ? new Date(d).toLocaleString("it-IT") : vuoto);
