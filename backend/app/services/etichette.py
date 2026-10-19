"""Etichette dei corsi: regole di scelta e filtri riusati da registro, matrice e pacchetto ispezione."""
from typing import Iterable, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.corso import Corso
from ..models.etichetta import CorsoEtichetta, Etichetta, EtichettaFamiglia

def _uuid_validi(ids) -> list:
    """Identificativi non UUID non devono arrivare al database (darebbero errore 500)."""
    risultato = []
    for i in ids or []:
        if not i:
            continue
        try:
            risultato.append(str(UUID(str(i))))
        except ValueError:
            raise HTTPException(400, "Identificativo di etichetta non valido")
    return risultato


def converti_categorie_in_tematica(db: Session):
    """Nessuna famiglia di etichette e' predefinita: ognuno definisce le sue (pagina Etichette dei corsi).
    Resta solo la conversione per chi arriva da una versione che aveva il vecchio campo Categoria: i corsi con una
    categoria ricevono un'etichetta con quel testo nella famiglia «Tematica» (che si crea se non c'e', senza toccare le
    altre famiglie; senza doppioni di grafia). Fatta la conversione il vecchio campo si svuota: non si ripete, e chi
    toglie poi l'etichetta da un corso non se la ritrova."""
    corsi = [c for c in db.query(Corso).filter(Corso.categoria.isnot(None)).all() if " ".join((c.categoria or "").split())]
    if not corsi:
        return
    tematica = db.query(EtichettaFamiglia).filter(func.lower(EtichettaFamiglia.nome) == "tematica").first()
    if tematica is None:
        tematica = EtichettaFamiglia(nome="Tematica", descrizione="Di che cosa parla il corso (dal vecchio campo Categoria).",
                                     scelta_multipla=True, ordine=db.query(EtichettaFamiglia).count())
        db.add(tematica)
        db.flush()
    esistenti = {e.nome.lower(): e for e in db.query(Etichetta).filter(Etichetta.famiglia_id == tematica.id).all()}
    for c in corsi:
        testo = " ".join((c.categoria or "").split())[:80]  # il nome dell'etichetta e' di 80 caratteri: si confronta il nome troncato
        e = esistenti.get(testo.lower())
        if not e:
            e = Etichetta(famiglia_id=tematica.id, nome=testo, ordine=len(esistenti))
            db.add(e)
            db.flush()
            esistenti[testo.lower()] = e
        mie = {x.id for x in etichette_del_corso(db, c.id) if x.famiglia_id == tematica.id}
        if e.id not in mie and (tematica.scelta_multipla or not mie):    # una famiglia a scelta singola che il corso ha gia' valorizzata non si tocca
            db.add(CorsoEtichetta(corso_id=c.id, etichetta_id=e.id))
        c.categoria = None
    db.commit()


def etichette_del_corso(db: Session, corso_id) -> list:
    return (db.query(Etichetta).join(CorsoEtichetta, CorsoEtichetta.etichetta_id == Etichetta.id)
            .filter(CorsoEtichetta.corso_id == corso_id).all())


def descrivi(db: Session, corso: Corso, famiglie: Optional[list] = None) -> dict:
    """Etichette del corso, famiglie obbligatorie ancora vuote e avvisi (es. Trasversale insieme a un cliente)."""
    famiglie = famiglie if famiglie is not None else db.query(EtichettaFamiglia).filter(EtichettaFamiglia.archiviata == False).all()  # noqa: E712
    per_famiglia = {f.id: f for f in famiglie}
    mie = etichette_del_corso(db, corso.id)
    presenti = {e.famiglia_id for e in mie}
    avvisi = []
    for f in famiglie:
        scelte = [e for e in mie if e.famiglia_id == f.id]
        esclusive = [e for e in scelte if e.esclusiva]
        if esclusive and len(scelte) > 1:
            altre = ", ".join(e.nome for e in scelte if not e.esclusiva)
            avvisi.append(f"{f.nome}: «{esclusive[0].nome}» insieme a {altre}")
    return {
        "etichette": [{"id": str(e.id), "nome": e.nome, "famiglia_id": str(e.famiglia_id),
                       "famiglia": per_famiglia[e.famiglia_id].nome if e.famiglia_id in per_famiglia else None, "archiviata": e.archiviata}
                      for e in sorted(mie, key=lambda e: (per_famiglia[e.famiglia_id].ordine if e.famiglia_id in per_famiglia else 99, e.ordine))],
        "etichette_mancanti": [f.nome for f in sorted(famiglie, key=lambda f: f.ordine) if f.obbligatoria and f.id not in presenti],
        "avvisi_etichette": avvisi,
    }


def imposta_etichette(db: Session, corso: Corso, ids: Iterable[str]):
    """Sostituisce le etichette del corso, rispettando le regole delle famiglie.
    Un'etichetta archiviata si puo' tenere se il corso l'aveva gia', non aggiungere."""
    ids = list(dict.fromkeys(_uuid_validi(ids)))
    scelte = db.query(Etichetta).filter(Etichetta.id.in_(ids)).all() if ids else []
    if len(scelte) != len(ids):
        raise ValueError("Una o più etichette non esistono")
    gia = {str(e.id) for e in etichette_del_corso(db, corso.id)}
    famiglie = {f.id: f for f in db.query(EtichettaFamiglia).all()}
    for e in scelte:
        if (e.archiviata or famiglie[e.famiglia_id].archiviata) and str(e.id) not in gia:
            raise ValueError(f"L'etichetta «{e.nome}» è archiviata: non si può più assegnare")
    for f in famiglie.values():
        nella = [e for e in scelte if e.famiglia_id == f.id]
        if not f.scelta_multipla and len(nella) > 1:
            raise ValueError(f"«{f.nome}» ammette una sola etichetta")
        if f.obbligatoria and not f.archiviata and not nella:
            raise ValueError(f"Indica almeno un'etichetta per «{f.nome}»")
    db.query(CorsoEtichetta).filter(CorsoEtichetta.corso_id == corso.id).delete()
    for e in scelte:
        db.add(CorsoEtichetta(corso_id=corso.id, etichetta_id=e.id))
    db.flush()


def corsi_con_etichette(db: Session, etichette_ids: Optional[list]) -> Optional[set]:
    """Corsi che hanno TUTTE le etichette indicate (None = nessun filtro).
    Tra etichette della stessa famiglia vale l'OR: 'Cliente1 o Cliente2'."""
    ids = _uuid_validi(etichette_ids)
    if not ids:
        return None
    scelte = db.query(Etichetta).filter(Etichetta.id.in_(ids)).all()
    per_famiglia = {}
    for e in scelte:
        per_famiglia.setdefault(e.famiglia_id, set()).add(e.id)
    risultato = None
    for gruppo in per_famiglia.values():
        corsi = {c for (c,) in db.query(CorsoEtichetta.corso_id).filter(CorsoEtichetta.etichetta_id.in_(gruppo)).all()}
        risultato = corsi if risultato is None else risultato & corsi
    return risultato or set()


def descrivi_filtro(db: Session, etichette_ids: Optional[list]) -> Optional[str]:
    ids = _uuid_validi(etichette_ids)
    if not ids:
        return None
    nomi = [f"{e.famiglia.nome}: {e.nome}" for e in db.query(Etichetta).filter(Etichetta.id.in_(ids)).all()]
    return "etichette " + ", ".join(sorted(nomi))
