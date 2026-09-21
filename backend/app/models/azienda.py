from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Azienda(Base):
    """Singleton: l'azienda proprietaria di questa istanza della piattaforma."""
    __tablename__ = "azienda"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ragione_sociale = Column(String, nullable=True)
    partita_iva     = Column(String, nullable=True)
    codice_fiscale  = Column(String, nullable=True)
    indirizzo       = Column(String, nullable=True)
    cap             = Column(String, nullable=True)
    citta           = Column(String, nullable=True)
    provincia       = Column(String, nullable=True)
    nazione         = Column(String, default="IT")
    email           = Column(String, nullable=True)
    pec             = Column(String, nullable=True)
    logo_path       = Column(String, nullable=True)
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
