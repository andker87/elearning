from sqlalchemy import Column, DateTime, Index, Integer, ForeignKey, Enum as SAEnum, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class StatoIscrizione(str, enum.Enum):
    iscritto        = "iscritto"
    in_lista_attesa = "in_lista_attesa"  # posti esauriti, promossa quando si libera un posto (sezione N)
    completato      = "completato"
    non_completato  = "non_completato"
    annullato       = "annullato"

class Iscrizione(Base):
    __tablename__ = "iscrizioni"
    # Una persona ha una sola iscrizione "viva" per sessione (le annullate restano come storico).
    __table_args__ = (Index("uq_iscrizione_viva", "edizione_id", "user_id", unique=True,
                            postgresql_where=text("stato <> 'annullato'")),)
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edizione_id = Column(UUID(as_uuid=True), ForeignKey("edizioni.id"), nullable=False)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stato       = Column(SAEnum(StatoIscrizione), nullable=False, default=StatoIscrizione.iscritto)
    # Valorizzato quando il Corso ha azione_test_non_superato=concludi_scadenza_breve:
    # il corso è considerato completato ma va ripetuto entro questa data.
    ripeti_entro = Column(DateTime(timezone=True), nullable=True)
    completato_at = Column(DateTime(timezone=True), nullable=True)
    # Snapshot di Corso.versione al momento del completamento - permette di
    # confrontare con Corso.versione_minima_valida/versione senza dover
    # ricostruire la storia (vedi models/corso.py).
    versione_corso = Column(Integer, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    edizione    = relationship("Edizione", back_populates="iscrizioni")
    evidenze    = relationship("Evidenza", cascade="all, delete-orphan", back_populates="iscrizione")
