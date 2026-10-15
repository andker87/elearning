// Stessa regola del backend (services/password_policy.py).
export const REQUISITI_PASSWORD = "almeno 14 caratteri, con almeno una lettera maiuscola, un numero e un carattere speciale";

export function passwordValida(p) {
  return typeof p === "string" && p.length >= 14 && /[A-Z]/.test(p) && /[0-9]/.test(p) && /[^A-Za-z0-9]/.test(p);
}
