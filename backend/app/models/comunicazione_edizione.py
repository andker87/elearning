from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class ComunicazioneEdizione(Base):
    """Storico degli annunci manuali inviati agli iscritti di una sessione
    (docente titolare o Ufficio Training) - a differenza delle notifiche
    automatiche dello scheduler, non è deduplicato: ogni invio è un'azione
    esplicita e va tracciato una volta per volta."""
    __tablename__ = "comunicazioni_edizione"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edizione_id   = Column(UUID(as_uuid=True), ForeignKey("edizioni.id"), nullable=False)
    mittente_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    oggetto       = Column(String, nullable=False)
    messaggio     = Column(Text, nullable=False)
    n_destinatari = Column(Integer, nullable=False, default=0)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
