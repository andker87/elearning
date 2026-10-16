"""Tipo di colonna per i dati personali: cifrati nel database, in chiaro nel programma."""
from sqlalchemy import Text
from sqlalchemy.sql import operators
from sqlalchemy.types import TypeDecorator

from ..services import cifratura

_CONFRONTI_AMMESSI = (operators.is_, operators.is_not, operators.isnot)


class TestoCifrato(TypeDecorator):
    """Scrive il testo cifrato (se c'e' la chiave) e lo restituisce in chiaro.
    Ogni cifratura usa un valore casuale diverso: due cifrature dello stesso testo non coincidono, quindi nel
    database non si puo' confrontare, ordinare o cercare. Per cercare per valore esatto serve l'impronta
    (services/impronte.py); l'ordinamento e la ricerca parziale si fanno nel programma.
    Un confronto scritto per sbaglio contro la colonna cifrata fallirebbe in silenzio (nessun risultato):
    qui fa invece un errore."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return cifratura.cifra_testo(value)

    def process_result_value(self, value, dialect):
        return cifratura.decifra_testo(value)

    class comparator_factory(TypeDecorator.Comparator):
        def operate(self, op, *altri, **kw):
            if op not in _CONFRONTI_AMMESSI:
                raise TypeError("Colonna cifrata: confronti e ricerche nel database non sono possibili, usa l'impronta (services/impronte.py)")
            return super().operate(op, *altri, **kw)

        reverse_operate = operate
