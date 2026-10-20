"""Catalogo: le sessioni a cui chiunque puo' iscriversi da solo (corsi con auto-iscrizione), comprese quelle
sempre aperte (video senza date). Chi non e' abilitato a iscriversi da solo non le vede qui."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.autoiscrizione import AutoIscrizioneRichiesta, StatoAutoIscrizione
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User
from ..services.durata import durata_effettiva
from ..services.etichette import etichette_del_corso
from ..services.gerarchia import responsabili_di
from ..services.iscrizioni import posti_occupati, sessione_finita
from .deps import get_current_user

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])


@router.get("")
def catalogo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    righe = (db.query(Edizione, Corso).join(Corso, Corso.id == Edizione.corso_id)
             .filter(Edizione.stato.in_((StatoEdizione.pianificata, StatoEdizione.in_corso)), Corso.is_active == True,  # noqa: E712
                     Corso.permetti_autoiscrizione == True).all())  # noqa: E712
    righe = [(e, c) for e, c in righe if not sessione_finita(e)]
    ids = [e.id for e, _ in righe]
    mie = {}
    attesa = set()
    if ids:
        for i in db.query(Iscrizione).filter(Iscrizione.user_id == user.id, Iscrizione.edizione_id.in_(ids), Iscrizione.stato != StatoIscrizione.annullato).all():
            mie[i.edizione_id] = i.stato.value
        attesa = {r.edizione_id for r in db.query(AutoIscrizioneRichiesta).filter(
            AutoIscrizioneRichiesta.user_id == user.id, AutoIscrizioneRichiesta.edizione_id.in_(ids),
            AutoIscrizioneRichiesta.stato == StatoAutoIscrizione.in_attesa).all()}
    ho_responsabili = bool(responsabili_di(db, user.id))
    out = []
    for e, c in righe:
        stato = mie.get(e.id) or ("richiesta_in_attesa" if e.id in attesa else None)
        out.append({
            "id": str(e.id), "corso_titolo": c.titolo, "corso_descrizione": c.descrizione,
            "etichette": [{"id": str(x.id), "nome": x.nome, "famiglia": x.famiglia.nome} for x in etichette_del_corso(db, c.id)],
            "modalita": e.modalita, "sempre_aperta": bool(e.sempre_aperta), "data_inizio": e.data_inizio, "data_fine": e.data_fine,
            "luogo": e.luogo, "durata_effettiva_minuti": durata_effettiva(e, c),
            "posti_liberi": (max(0, e.posti_max - posti_occupati(db, e.id)) if e.posti_max else None),
            "lista_attesa": bool(e.lista_attesa_abilitata),
            "richiede_approvazione": bool(c.richiedi_approvazione_responsabile and ho_responsabili),
            "mio_stato": stato,
        })
    out.sort(key=lambda r: (not r["sempre_aperta"], r["data_inizio"] is None, r["data_inizio"].timestamp() if r["data_inizio"] else 0, r["corso_titolo"].lower()))
    return out
