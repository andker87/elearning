from sqlalchemy.orm import Session

from ..models.edizione import Edizione, EdizioneDocente, StatoEdizione
from ..models.group import Group
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.push_subscription import PushSubscription
from .iscrizioni import promuovi_da_lista_attesa

CHIUSE = (StatoEdizione.chiusa, StatoEdizione.annullata)


def avvisi_disattivazione(db: Session, u) -> list:
    """Cio' che resta scoperto quando questa persona esce: non impedisce la
    disattivazione (un account di chi ha lasciato l'azienda va chiuso comunque)
    ma va riassegnato a mano."""
    avvisi = []
    aperte = (db.query(Edizione).join(EdizioneDocente, EdizioneDocente.edizione_id == Edizione.id)
              .filter(EdizioneDocente.user_id == u.id, ~Edizione.stato.in_(CHIUSE)).count())
    if aperte:
        avvisi.append(f"docente di {aperte} sessione/i non ancora chiuse: da riassegnare")
    uffici = [g.name for g in db.query(Group).filter(Group.responsabile_id == u.id).all()]
    if uffici:
        avvisi.append(f"responsabile di {', '.join(uffici)}: da assegnare a un altro responsabile")
    return avvisi


def disattiva_utente(db: Session, u) -> dict:
    """Chiude l'account di chi ha lasciato l'azienda, tenendo intatto lo storico
    formativo: disattiva, chiude le sessioni aperte, libera i posti ancora
    prenotati (promuovendo chi era in lista d'attesa) e toglie i dispositivi push.
    Ritorna {"avvisi": [...], "posti_liberati": n, "promossi": [Iscrizione]}."""
    avvisi = avvisi_disattivazione(db, u)
    liberati, promossi = 0, []
    aperte = (db.query(Iscrizione, Edizione).join(Edizione, Edizione.id == Iscrizione.edizione_id)
              .filter(Iscrizione.user_id == u.id,
                      Iscrizione.stato.in_([StatoIscrizione.iscritto, StatoIscrizione.in_lista_attesa]),
                      ~Edizione.stato.in_(CHIUSE)).all())
    for iscr, ed in aperte:
        occupava_posto = iscr.stato == StatoIscrizione.iscritto
        iscr.stato = StatoIscrizione.annullato
        db.flush()  # il posto deve risultare libero prima di promuovere chi aspetta
        if occupava_posto:
            liberati += 1
        if occupava_posto and ed.lista_attesa_abilitata:
            p = promuovi_da_lista_attesa(db, ed.id)
            if p:
                promossi.append(p)
    db.query(PushSubscription).filter(PushSubscription.user_id == u.id).delete()
    u.is_active = False
    u.calendar_token_hash = None  # il feed del calendario smette di funzionare
    u.token_version = (u.token_version or 0) + 1  # le sessioni aperte smettono di valere
    db.flush()
    return {"avvisi": avvisi, "posti_liberati": liberati, "promossi": promossi}


def invita_promossi(db: Session, promossi: list):
    """Dopo il commit: chi e' salito dalla lista d'attesa riceve l'invito calendario, come quando
    qualcuno annulla a mano."""
    from .notifiche import invia_invito_calendario
    for p in promossi:
        ed = db.query(Edizione).filter(Edizione.id == p.edizione_id).first()
        if ed and ed.data_inizio:
            invia_invito_calendario(db, ed, p.user_id)
