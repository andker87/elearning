from sqlalchemy.orm import Session
from ..models.group import Group, UserGroup
from ..models.user import User


def _ufficio_e_antenati(db: Session, gruppo: Group) -> list[Group]:
    """Un ufficio e, risalendo, i suoi uffici padre (fino alla radice)."""
    catena = [gruppo]
    corrente = gruppo
    visti = {gruppo.id}
    while corrente.parent_id and corrente.parent_id not in visti:  # anche con dati incoerenti non si gira in tondo
        corrente = db.query(Group).filter(Group.id == corrente.parent_id).first()
        if not corrente or not corrente.is_ufficio:
            break
        visti.add(corrente.id)
        catena.append(corrente)
    return catena


def responsabili_di(db: Session, user_id: str) -> list[User]:
    """Responsabile(i) di una persona, derivati dagli uffici (mai un campo
    salvato sulla persona - vedi models/group.py e models/user.py).

    Due casi, entrambi possono valere insieme (es. part-time su più uffici):
    - è membro di uno o più uffici -> il responsabile è quello del primo
      ufficio della catena (risalendo i padri) che ha un responsabile;
    - è lei stessa responsabile di un ufficio -> il suo responsabile è quello
      del primo ufficio padre (risalendo) che ha un responsabile.
    """
    trovati: dict[str, User] = {}

    membri = (
        db.query(Group)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .filter(UserGroup.user_id == user_id, Group.is_ufficio == True)
        .all()
    )
    for ufficio in membri:
        for tappa in _ufficio_e_antenati(db, ufficio):
            if tappa.responsabile_id and str(tappa.responsabile_id) != str(user_id):
                trovati[str(tappa.responsabile_id)] = tappa.responsabile
                break

    guidati = db.query(Group).filter(Group.responsabile_id == user_id, Group.is_ufficio == True).all()
    for ufficio in guidati:
        if not ufficio.parent_id:
            continue
        padre = db.query(Group).filter(Group.id == ufficio.parent_id).first()
        if not padre or not padre.is_ufficio:
            continue
        for tappa in _ufficio_e_antenati(db, padre):
            if tappa.responsabile_id and str(tappa.responsabile_id) != str(user_id):
                trovati[str(tappa.responsabile_id)] = tappa.responsabile
                break

    return list(trovati.values())


def sottoposti_di(db: Session, user_id: str) -> list[User]:
    """Tutte le persone sotto gli uffici guidati da questo responsabile,
    scendendo l'albero: membri diretti di ogni ufficio guidato, i
    responsabili dei suoi sotto-uffici (sottoposti diretti), e così via
    ricorsivamente nei sotto-uffici."""
    radici = db.query(Group).filter(Group.responsabile_id == user_id, Group.is_ufficio == True).all()
    trovati: dict[str, User] = {}

    frontiera = list(radici)
    visitati = {u.id for u in frontiera}
    while frontiera:
        prossima = []
        for ufficio in frontiera:
            membri = (
                db.query(User)
                .join(UserGroup, UserGroup.user_id == User.id)
                .filter(UserGroup.group_id == ufficio.id)
                .all()
            )
            for m in membri:
                if str(m.id) != str(user_id):
                    trovati[str(m.id)] = m
            figli = db.query(Group).filter(Group.parent_id == ufficio.id, Group.is_ufficio == True).all()
            for figlio in figli:
                if figlio.responsabile_id and str(figlio.responsabile_id) != str(user_id):
                    resp = figlio.responsabile
                    if resp:
                        trovati[str(figlio.responsabile_id)] = resp
                if figlio.id not in visitati:
                    visitati.add(figlio.id)
                    prossima.append(figlio)
        frontiera = prossima

    return list(trovati.values())


def e_responsabile(db: Session, user_id: str) -> bool:
    """È responsabile di almeno un ufficio - usato per autorizzare richiesta
    corso/fabbisogno spontaneo (sezione Q, flusso B)."""
    return db.query(Group).filter(Group.responsabile_id == user_id, Group.is_ufficio == True).first() is not None


def uffici_guidati_da(db: Session, user_id: str) -> list[Group]:
    return db.query(Group).filter(Group.responsabile_id == user_id, Group.is_ufficio == True).all()


def uffici_radice(db: Session) -> list[Group]:
    """Uffici di primo livello (nessun padre, o padre non marcato ufficio)."""
    radici = []
    for g in db.query(Group).filter(Group.is_ufficio == True).all():
        padre = db.query(Group).filter(Group.id == g.parent_id).first() if g.parent_id else None
        if not padre or not padre.is_ufficio:
            radici.append(g)
    return radici


def uffici_figli(db: Session, ufficio_id: str) -> list[Group]:
    return db.query(Group).filter(Group.parent_id == ufficio_id, Group.is_ufficio == True).all()


def ufficio_padre(db: Session, ufficio: Group) -> "Group | None":
    if not ufficio.parent_id:
        return None
    padre = db.query(Group).filter(Group.id == ufficio.parent_id).first()
    return padre if padre and padre.is_ufficio else None


def persone_ufficio_e_sottouffici(db: Session, ufficio_id: str) -> list[User]:
    """Tutti i membri di un ufficio e di ogni suo sotto-ufficio, scendendo
    l'albero - usato per i filtri "per reparto" (es. registro formazione,
    sezione A)."""
    trovati: dict[str, User] = {}
    frontiera = db.query(Group).filter(Group.id == ufficio_id, Group.is_ufficio == True).all()
    visitati = {u.id for u in frontiera}
    while frontiera:
        prossima = []
        for ufficio in frontiera:
            membri = (
                db.query(User)
                .join(UserGroup, UserGroup.user_id == User.id)
                .filter(UserGroup.group_id == ufficio.id)
                .all()
            )
            for m in membri:
                trovati[str(m.id)] = m
            prossima.extend(f for f in uffici_figli(db, ufficio.id) if f.id not in visitati)
        visitati.update(f.id for f in prossima)
        frontiera = prossima
    return list(trovati.values())
