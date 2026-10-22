"""Due richieste che arrivano nello stesso istante non devono produrre due attestati ne' due completamenti."""
import threading
from datetime import timedelta

from app.database import SessionLocal
from app.models.certificato import Certificato
from app.models.edizione import ModalitaErogazione as M, StatoEdizione as SE
from app.models.evidenza import Evidenza, FonteEvidenza
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.video import StatoVideo, VideoContenuto
from app.services.completamento import completa_se_dovuto

from conftest import adesso


def test_due_completamenti_contemporanei_creano_un_solo_attestato(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    v = VideoContenuto(titolo="Sicurezza", stato=StatoVideo.pronto, durata_secondi=100)
    db.add(v); db.commit()
    e = crea_edizione(crea_corso("Corso"), stato=SE.in_corso, modalita=M.video, video_id=v.id, data_inizio=adesso() - timedelta(hours=1))
    i = crea_iscrizione(e, utente)
    db.add(Evidenza(iscrizione_id=i.id, fonte=FonteEvidenza.video_player, percentuale_completamento=100.0)); db.commit()

    via = threading.Barrier(2)
    esiti, errori = [], []

    def completa():
        s = SessionLocal()
        try:
            iscr = s.get(Iscrizione, i.id)
            via.wait(timeout=10)                       # le due richieste partono insieme
            cert = completa_se_dovuto(s, None, iscr)
            s.commit()
            esiti.append(cert is not None)
        except Exception as ex:                        # pragma: no cover - se succede il test lo mostra
            errori.append(repr(ex)); s.rollback()
        finally:
            s.close()

    fili = [threading.Thread(target=completa) for _ in range(2)]
    for f in fili: f.start()
    for f in fili: f.join(timeout=30)

    assert not errori, errori
    assert sorted(esiti) == [False, True]              # uno completa, l'altro trova gia' tutto fatto
    db.expire_all()
    assert db.get(Iscrizione, i.id).stato == S.completato
    assert db.query(Certificato).filter(Certificato.iscrizione_id == i.id).count() == 1
