"""Completamento automatico delle sessioni «sempre aperte» (video senza date).

Una sessione normale si chiude a mano e solo allora si decide chi ha completato; una sessione sempre aperta non si chiude:
chi raggiunge la soglia di visione del video (e supera il test finale, se il corso ne ha uno) risulta completato subito
e riceve l'attestato. Si controlla a ogni avanzamento del video e a ogni tentativo del test finale."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models.certificato import Certificato
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.evidenza import Evidenza, FonteEvidenza
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.test import Test, TentativoTest, MomentoTest
from ..models.user import User
from . import audit as audit_svc
from . import certificati as cert_svc


def _video_visto(db: Session, iscrizione: Iscrizione) -> bool:
    from ..api.evidenze import SOGLIA_COMPLETAMENTO_VIDEO_PCT
    ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == iscrizione.id, Evidenza.fonte == FonteEvidenza.video_player).first()
    return bool(ev and ev.percentuale_completamento is not None and ev.percentuale_completamento >= SOGLIA_COMPLETAMENTO_VIDEO_PCT)


def _test_a_posto(db: Session, iscrizione: Iscrizione, corso: Corso) -> bool:
    """Senza test finale e' a posto. Con il test serve almeno un tentativo: superato, oppure non superato ma con una
    regola del corso che conclude comunque (concludi_comunque / scadenza breve)."""
    test = db.query(Test).filter(Test.corso_id == corso.id, Test.momento == MomentoTest.finale).first()
    if not test:
        return True
    ultimo = (db.query(TentativoTest).filter(TentativoTest.test_id == test.id, TentativoTest.iscrizione_id == iscrizione.id)
              .order_by(TentativoTest.completato_at.desc()).first())
    if not ultimo:
        return False
    return bool(ultimo.superato) or corso.azione_test_non_superato.value in ("concludi_comunque", "concludi_scadenza_breve")


def completa_se_dovuto(db: Session, request, iscrizione: Iscrizione) -> Optional[Certificato]:
    """Se la sessione e' sempre aperta e la persona ha fatto tutto, la completa e crea l'attestato; altrimenti non fa nulla."""
    e = db.query(Edizione).filter(Edizione.id == iscrizione.edizione_id).first()
    if not e or not e.sempre_aperta or e.stato not in (StatoEdizione.pianificata, StatoEdizione.in_corso):
        return None
    if iscrizione.stato != StatoIscrizione.iscritto:
        return None
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    if not corso or not _video_visto(db, iscrizione) or not _test_a_posto(db, iscrizione, corso):
        return None
    iscrizione.stato = StatoIscrizione.completato
    iscrizione.completato_at = datetime.now(timezone.utc)
    iscrizione.versione_corso = corso.versione
    u = db.query(User).filter(User.id == iscrizione.user_id).first()
    azienda_nome, logo_path = cert_svc.azienda_info(db)
    cert = cert_svc.crea_certificato(db, iscrizione, corso, u.full_name if u else "", azienda_nome, logo_path, e)
    audit_svc.log_from_request(db, request, u, "COMPLETE_AUTO", entity_type="edizione", entity_id=str(e.id),
                                entity_name=audit_svc.nome_edizione(db, e), detail="completata in automatico (sessione sempre aperta)")
    return cert
