// Gli uffici in ordine alfabetico a ogni livello, ciascuno con il percorso intero («Produzione / Linea 2»):
// negli elenchi a tendina la gerarchia si legge dal nome. `escludi` toglie un ufficio e tutto il suo ramo
// (per scegliere il «sottoufficio di» senza metterlo sotto se stesso).
export function elencoUffici(gruppi, escludi = null) {
  const ids = new Set(gruppi.map((g) => g.id));
  const figli = {};
  for (const g of gruppi) {
    const chiave = g.parent_id && ids.has(g.parent_id) ? g.parent_id : "radice";
    (figli[chiave] = figli[chiave] || []).push(g);
  }
  const ordina = (a, b) => a.name.localeCompare(b.name, "it", { sensitivity: "base", numeric: true });
  const out = [];
  const visita = (chiave, nomi, livello, visti) => {
    for (const g of (figli[chiave] || []).sort(ordina)) {
      if (visti.has(g.id) || g.id === escludi) continue;
      const percorso = [...nomi, g.name];
      out.push({ ...g, etichetta: percorso.join(" / "), livello });
      visita(g.id, percorso, livello + 1, new Set([...visti, g.id]));
    }
  };
  visita("radice", [], 0, new Set());
  return out;
}
