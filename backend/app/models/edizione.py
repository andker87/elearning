from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class ModalitaErogazione(str, enum.Enum):
    presenza  = "presenza"
    ibrida    = "ibrida"
    remoto    = "remoto"
    video     = "video"
    esterna   = "esterna"   # formazione fatta da ente accreditato terzo, evidenza caricata manualmente

class ModalitaCheckin(str, enum.Enum):
    """Come si raccolgono le presenze per la componente 'in presenza' di
    un'edizione (presenza / parte in sede di un'ibrida)."""
    discente_validato = "discente_validato"  # il discente si segna, il docente valida/chiude
    docente            = "docente"            # il docente segna lui chi è presente

class ModalitaTeams(str, enum.Enum):
    """Come si aggancia la riunione Teams (componente remota di ibrida/remoto)."""
    auto     = "auto"      # la piattaforma crea la riunione via Graph API
    manuale  = "manuale"   # il docente incolla il link della riunione creata da lui

class StatoEdizione(str, enum.Enum):
    bozza       = "bozza"
    pianificata = "pianificata"
    in_corso    = "in_corso"
    chiusa      = "chiusa"      # attestata: evidenze definitive, certificati generabili
    annullata   = "annullata"

class Edizione(Base):
    __tablename__ = "edizioni"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corso_id    = Column(UUID(as_uuid=True), ForeignKey("corsi.id"), nullable=False)
    modalita    = Column(SAEnum(ModalitaErogazione), nullable=False)
    stato       = Column(SAEnum(StatoEdizione), nullable=False, default=StatoEdizione.bozza)

    data_inizio = Column(DateTime(timezone=True), nullable=True)
    data_fine   = Column(DateTime(timezone=True), nullable=True)
    luogo       = Column(String, nullable=True)  # per presenza/ibrida
    posti_max   = Column(Integer, nullable=True)
    # Se posti_max è superato, le nuove iscrizioni finiscono in lista d'attesa
    # invece di essere rifiutate (sezione N) - opzione per edizione, non fissa.
    lista_attesa_abilitata = Column(Boolean, nullable=False, default=False)

    # presenza / componente in sede di ibrida
    checkin_mode = Column(SAEnum(ModalitaCheckin), nullable=True, default=ModalitaCheckin.discente_validato)

    # ibrida / remoto: componente Teams
    teams_mode       = Column(SAEnum(ModalitaTeams), nullable=True)
    teams_meeting_id = Column(String, nullable=True)   # onlineMeeting id (Graph)
    teams_join_url   = Column(String, nullable=True)

    # video
    video_id = Column(UUID(as_uuid=True), ForeignKey("video_contenuti.id"), nullable=True)

    # esterna
    ente_erogatore   = Column(String, nullable=True)

    # Durata in minuti. Vuota = segue quella del corso; compilata = durata forzata da chi organizza la sessione
    # (e, alla chiusura, valore congelato). Vedi services/durata.py.
    durata_minuti = Column(Integer, nullable=True)

    # Sessione video «sempre aperta»: niente date, la segue chi vuole quando vuole; chi la completa riceve
    # l'attestato in automatico (services/completamento.py). Solo per la modalita' video.
    sempre_aperta = Column(Boolean, nullable=False, default=False, server_default="false")

    note = Column(Text, nullable=True)

    chiusa_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    chiusa_at    = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    docenti      = relationship("EdizioneDocente", cascade="all, delete-orphan", back_populates="edizione")
    iscrizioni   = relationship("Iscrizione", cascade="all, delete-orphan", back_populates="edizione")

class RuoloDocente(str, enum.Enum):
    titolare  = "titolare"
    co_docente = "co_docente"

class EdizioneDocente(Base):
    """N:N: un'edizione può avere più docenti, una persona può essere docente
    di alcune edizioni e discente di altre - nessun ruolo fisso sull'utente."""
    __tablename__ = "edizione_docenti"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edizione_id = Column(UUID(as_uuid=True), ForeignKey("edizioni.id"), nullable=False)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ruolo       = Column(SAEnum(RuoloDocente), nullable=False, default=RuoloDocente.titolare)
    edizione    = relationship("Edizione", back_populates="docenti")
