"""Etichette dei corsi: famiglie predefinite, regole di scelta e filtri riusati da
registro, matrice e pacchetto ispezione."""
from typing import Iterable, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.corso import Corso
from ..models.etichetta import CorsoEtichetta, Etichetta, EtichettaFamiglia

# Punto di partenza alla prima installazione: la Formazione rinomina, aggiunge, archivia.
FAMIGLIE_INIZIALI = [
    ("Tematica", "Di che cosa parla il corso.", True, [
        ("Sicurezza sul lavoro", False), ("Cybersecurity", False), ("Privacy e protezione dei dati", False), ("Qualità", False)]),
    ("Riferimento normativo", "La norma o lo standard che il corso soddisfa: è il filtro che serve negli audit.", True, [
        ("D.Lgs 81/08", False), ("GDPR", False), ("ISO 9001", False), ("ISO 27001", False), ("ISO 45001", False)]),
    ("Ambito", "Per chi vale il corso: trasversale a tutta l'azienda o specifico per un cliente.", True, [("Trasversale", True)]),
    ("Obbligo", "Perché il corso va fatto.", False, [
        ("Obbligo di legge", False), ("Richiesto da un cliente", False), ("Policy interna", False), ("Facoltativo", False)]),
]


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


def crea_famiglie_iniziali(db: Session):
    """Solo se non esiste ancora nessuna famiglia. I vecchi testi del campo Categoria
    diventano etichette della Tematica, assegnate ai rispettivi corsi."""
    if db.query(EtichettaFamiglia).count():
        return
    tematica = None
    for n, (nome, descr, multipla, valori) in enumerate(FAMIGLIE_INIZIALI):
        f = EtichettaFamiglia(nome=nome, descrizione=descr, scelta_multipla=multipla, ordine=n)
        db.add(f)
        db.flush()
        for m, (valore, esclusiva) in enumerate(valori):
            db.add(Etichetta(famiglia_id=f.id, nome=valore, ordine=m, esclusiva=esclusiva))
        if nome == "Tematica":
            tematica = f
    db.flush()
    esistenti = {e.nome.lower(): e for e in db.query(Etichetta).filter(Etichetta.famiglia_id == tematica.id).all()}
    for c in db.query(Corso).filter(Corso.categoria.isnot(None)).all():
        testo = " ".join((c.categoria or "").split())[:80]  # il nome dell'etichetta e' di 80 caratteri: si confronta il nome troncato
        if not testo:
            continue
        e = esistenti.get(testo.lower())
        if not e:
            e = Etichetta(famiglia_id=tematica.id, nome=testo, ordine=len(esistenti))
            db.add(e)
            db.flush()
            esistenti[testo.lower()] = e
        db.add(CorsoEtichetta(corso_id=c.id, etichetta_id=e.id))
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
