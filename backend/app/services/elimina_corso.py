"""Eliminazione definitiva di un corso, per l'errore di chi lo ha creato per sbaglio.

Di regola un corso si disattiva (resta lo storico). Si puo' eliminare solo se non ha lasciato tracce di formazione:
nessuna iscrizione attiva o conclusa, nessun attestato, non e' in un percorso ne' in una richiesta di corso. Le sessioni
ancora vuote (e le iscrizioni annullate, senza esiti) vanno via insieme al corso."""
from sqlalchemy.orm import Session

from ..models.autoiscrizione import AutoIscrizioneRichiesta
from ..models.certificato import Certificato
from ..models.comunicazione_edizione import ComunicazioneEdizione
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.etichetta import CorsoEtichetta
from ..models.evidenza import Evidenza
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.percorso import PercorsoStep
from ..models.richiesta_corso import RichiestaCorso
from ..models.richiesta_iscrizione import RichiestaIscrizione
from ..models.test import Gradimento, TentativoTest, Test
from ..models.video import VideoProgresso


def _ids(db: Session, modello, colonna, valori):
    return [r[0] for r in db.query(modello.id).filter(colonna.in_(valori)).all()] if valori else []


def esame(db: Session, corso: Corso) -> dict:
    """Cosa impedisce l'eliminazione e cosa verrebbe eliminato."""
    sessioni = _ids(db, Edizione, Edizione.corso_id, [corso.id])
    iscrizioni = db.query(Iscrizione).filter(Iscrizione.edizione_id.in_(sessioni)).all() if sessioni else []
    vive = [i for i in iscrizioni if i.stato != StatoIscrizione.annullato]
    motivi = []
    if vive:
        motivi.append(f"{len(vive)} {'iscrizione attiva o conclusa' if len(vive) == 1 else 'iscrizioni attive o concluse'}")
    attestati = db.query(Certificato).filter(Certificato.iscrizione_id.in_([i.id for i in iscrizioni])).count() if iscrizioni else 0
    if attestati:
        motivi.append(f"{attestati} {'attestato emesso' if attestati == 1 else 'attestati emessi'}")
    percorsi = db.query(PercorsoStep).filter(PercorsoStep.corso_id == corso.id).count()
    if percorsi:
        motivi.append(f"è in {percorsi} {'passo di un percorso formativo' if percorsi == 1 else 'passi di percorsi formativi'}")
    richieste = db.query(RichiestaCorso).filter(RichiestaCorso.corso_id == corso.id).count()
    if richieste:
        motivi.append(f"{richieste} {'richiesta di corso lo riguarda' if richieste == 1 else 'richieste di corso lo riguardano'}")
    return {"eliminabile": not motivi, "motivi": motivi, "sessioni": len(sessioni),
            "iscrizioni_annullate": len(iscrizioni) - len(vive), "test": db.query(Test).filter(Test.corso_id == corso.id).count()}


def elimina_sessioni(db: Session, sessioni: list) -> None:
    """Toglie le sessioni indicate con tutto cio' che le riguarda (iscrizioni, esiti, richieste, comunicazioni, docenti).
    Chi chiama ha gia' controllato che non ci siano attestati ne' sessioni chiuse."""
    iscrizioni = _ids(db, Iscrizione, Iscrizione.edizione_id, sessioni)
    if iscrizioni:
        for gr in db.query(Gradimento).filter(Gradimento.iscrizione_id.in_(iscrizioni)).all():
            db.delete(gr)                                   # cascata sui voti ai docenti
        db.query(TentativoTest).filter(TentativoTest.iscrizione_id.in_(iscrizioni)).delete(synchronize_session=False)
        db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id.in_(iscrizioni)).delete(synchronize_session=False)
        db.query(Evidenza).filter(Evidenza.iscrizione_id.in_(iscrizioni)).delete(synchronize_session=False)
        db.query(Iscrizione).filter(Iscrizione.id.in_(iscrizioni)).delete(synchronize_session=False)
    if sessioni:
        db.query(AutoIscrizioneRichiesta).filter(AutoIscrizioneRichiesta.edizione_id.in_(sessioni)).delete(synchronize_session=False)
        db.query(RichiestaIscrizione).filter(RichiestaIscrizione.edizione_id.in_(sessioni)).delete(synchronize_session=False)
        db.query(ComunicazioneEdizione).filter(ComunicazioneEdizione.edizione_id.in_(sessioni)).delete(synchronize_session=False)
        db.expire_all()
        for e in db.query(Edizione).filter(Edizione.id.in_(sessioni)).all():
            db.delete(e)                                    # cascata sui docenti
        db.flush()


def esame_sessione(db: Session, e: Edizione) -> dict:
    """Cosa impedisce l'eliminazione di una sessione e cosa verrebbe tolto."""
    iscrizioni = db.query(Iscrizione).filter(Iscrizione.edizione_id == e.id).all()
    vive = [i for i in iscrizioni if i.stato != StatoIscrizione.annullato]
    motivi = []
    if e.stato == StatoEdizione.chiusa:
        motivi.append("la sessione è chiusa: fa parte dello storico")
    attestati = db.query(Certificato).filter(Certificato.iscrizione_id.in_([i.id for i in iscrizioni])).count() if iscrizioni else 0
    if attestati:
        motivi.append(f"{attestati} {'attestato emesso' if attestati == 1 else 'attestati emessi'}")
    return {"eliminabile": not motivi, "motivi": motivi, "iscrizioni_vive": len(vive), "iscrizioni_annullate": len(iscrizioni) - len(vive)}


def elimina_sessione(db: Session, e: Edizione) -> None:
    elimina_sessioni(db, [e.id])


def elimina(db: Session, corso: Corso) -> None:
    elimina_sessioni(db, _ids(db, Edizione, Edizione.corso_id, [corso.id]))      # l'esame ha garantito: solo iscrizioni annullate
    for t in db.query(Test).filter(Test.corso_id == corso.id).all():
        db.delete(t)                                        # cascata su domande e opzioni
    db.query(CorsoEtichetta).filter(CorsoEtichetta.corso_id == corso.id).delete(synchronize_session=False)
    db.flush()
    db.delete(corso)
