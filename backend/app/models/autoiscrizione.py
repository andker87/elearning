from sqlalchemy import Column, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class StatoAutoIscrizione(str, enum.Enum):
    in_attesa = "in_attesa"
    approvata = "approvata"
    rifiutata = "rifiutata"

class AutoIscrizioneRichiesta(Base):
    """Auto-iscrizione con 'richiedi_approvazione_responsabile' attivo
    (sezione P): la Iscrizione vera viene creata solo all'approvazione, non
    qui - evita di aggiungere stati di limbo al motore Iscrizione."""
    __tablename__ = "autoiscrizione_richieste"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edizione_id = Column(UUID(as_uuid=True), ForeignKey("edizioni.id"), nullable=False)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stato       = Column(SAEnum(StatoAutoIscrizione), nullable=False, default=StatoAutoIscrizione.in_attesa)
    valutata_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    valutata_at = Column(DateTime(timezone=True), nullable=True)
