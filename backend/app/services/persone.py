"""Permessi e qualifiche di una persona, in parole."""


def permessi_testo(u) -> str:
    """Es. «Admin; Formatore». Vuoto = utente semplice (un esterno e' «Formatore» per definizione)."""
    voci = []
    if u.is_admin: voci.append("Admin")
    if u.is_formazione: voci.append("Formazione")
    if u.is_formatore or u.is_external: voci.append("Formatore")
    return "; ".join(voci)
