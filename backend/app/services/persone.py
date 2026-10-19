"""Permessi e qualifiche di una persona, in parole."""


def permessi_testo(u) -> str:
    """Es. «Admin; Formatore». Vuoto = utente semplice (un esterno e' «Formatore» per definizione)."""
    voci = []
    if u.is_admin: voci.append("Admin")
    if u.is_formazione: voci.append("Formazione")
    if u.is_formatore or u.is_external: voci.append("Formatore")
    return "; ".join(voci)


def dividi_nome(testo) -> tuple:
    """(nome, cognome) da un nome intero scritto «Nome Cognome»: la prima parola e' il nome, il resto il cognome.
    Non c'e' una regola esatta (Maria Grazia Rossi, Mario De Luca): serve solo dove arriva un nome intero
    (accesso aziendale senza nome e cognome separati, conversione dei dati esistenti); la persona si corregge dalla sua scheda."""
    parole = (testo or "").split()
    if not parole:
        return "", ""
    return parole[0], " ".join(parole[1:])
