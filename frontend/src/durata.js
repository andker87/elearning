// Durata in minuti -> testo breve («4 h 30», «45 min», «2 h»); vuoto se non c'e'.
export function formattaDurata(minuti) {
  if (!minuti) return "";
  const h = Math.floor(minuti / 60), m = minuti % 60;
  return [h ? `${h} h` : "", m ? `${m} min` : ""].filter(Boolean).join(" ");
}
