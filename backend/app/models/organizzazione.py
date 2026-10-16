from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base
from .tipi import TestoCifrato

class Organizzazione(Base):
    """Registro di enti/aziende esterne a cui appartengono utenti esterni
    (docenti esterni, collaboratori). Tipo lasciato libero (testo), non enum
    chiuso, per non irrigidire casistiche non ancora note."""
    __tablename__ = "organizzazioni"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ragione_sociale  = Column(String, nullable=False)
    tipo             = Column(String, nullable=True)  # es. "ente accreditato", "azienda cliente", "libero professionista"
    partita_iva      = Column(String, nullable=True)
    accreditamento   = Column(String, nullable=True)  # numero/riferimento accreditamento se applicabile
    referente        = Column(TestoCifrato, nullable=True)   # dati personali: cifrati nel database
    email            = Column(TestoCifrato, nullable=True)
    telefono         = Column(TestoCifrato, nullable=True)
    note             = Column(Text, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
