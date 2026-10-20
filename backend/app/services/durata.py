"""Durata di un corso e di una sessione (in minuti).

Il corso dichiara la durata; la sessione la eredita, ma chi la organizza puo' «forzarla» (durata propria).
`Edizione.durata_minuti` vuota = segue il corso. Alla chiusura della sessione la durata si congela (si scrive il
valore effettivo): un attestato gia' emesso e i report passati non cambiano se poi si modifica il corso."""
from typing import Optional

from ..models.edizione import StatoEdizione


def durata_effettiva(edizione, corso) -> Optional[int]:
    if edizione is not None and edizione.durata_minuti:
        return edizione.durata_minuti
    if edizione is not None and getattr(edizione, "stato", None) == StatoEdizione.chiusa:
        return None   # chiusa senza durata: resta senza, anche se il corso ne riceve una dopo (lo storico non cambia)
    return corso.durata_minuti if corso is not None and corso.durata_minuti else None


def durata_in_parole(minuti) -> str:
    """«4 ore e 30 minuti», «1 ora», «45 minuti»; vuoto se la durata non c'e'."""
    if not minuti:
        return ""
    h, m = divmod(int(minuti), 60)
    parti = []
    if h:
        parti.append(f"{h} {'ora' if h == 1 else 'ore'}")
    if m:
        parti.append(f"{m} {'minuto' if m == 1 else 'minuti'}")
    return " e ".join(parti)


def ore_testo(minuti) -> str:
    """Ore con la virgola, senza zeri inutili: 8 -> «8», 90 minuti -> «1,5»."""
    if not minuti:
        return ""
    return f"{round(int(minuti) / 60, 2):g}".replace(".", ",")


def congela(edizione, corso) -> None:
    """Alla chiusura: la durata effettiva diventa quella della sessione."""
    if edizione.durata_minuti is None:
        edizione.durata_minuti = durata_effettiva(edizione, corso)
