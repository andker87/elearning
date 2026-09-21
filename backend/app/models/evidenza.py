from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class FonteEvidenza(str, enum.Enum):
    checkin_discente = "checkin_discente"   # self checkin, in attesa/dopo validazione docente
    checkin_docente  = "checkin_docente"    # registro digitale compilato dal docente
    teams_auto       = "teams_auto"         # meetingAttendanceReport via Graph API
    teams_manuale    = "teams_manuale"      # report Teams caricato/incollato a mano
    video_player     = "video_player"       # eventi di riproduzione tracciati dal player
    upload_manuale   = "upload_manuale"     # corso esterno: attestato caricato dall'ufficio formazione

class Evidenza(Base):
    """Record unico di evidenza di partecipazione, qualunque sia la modalità di
    erogazione. Diventa definitiva solo quando 'attestata_da_id' è valorizzato."""
    __tablename__ = "evidenze"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iscrizione_id = Column(UUID(as_uuid=True), ForeignKey("iscrizioni.id"), nullable=False)
    fonte         = Column(SAEnum(FonteEvidenza), nullable=False)

    inizio_at = Column(DateTime(timezone=True), nullable=True)
    fine_at   = Column(DateTime(timezone=True), nullable=True)
    percentuale_completamento = Column(Float, nullable=True)  # 0-100, rilevante per video

    dati_extra = Column(JSON, default=dict)  # es. { "durata_minuti_teams": 42, "ip": "..." }
    file_allegato_path = Column(String, nullable=True)  # attestato esterno caricato

    # Attestazione finale: chi ha "chiuso" questa evidenza rendendola ufficiale
    # (docente, o ufficio formazione per i corsi esterni).
    attestata_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    attestata_at    = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    iscrizione = relationship("Iscrizione", back_populates="evidenze")
