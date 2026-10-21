"""Questionari di gradimento personalizzabili dalla Formazione.

Le domande fisse (voto complessivo, commento, voto ai docenti) restano per tutti i corsi; qui ci sono quelle aggiuntive,
raggruppate in questionari con un nome. Uno e' il «predefinito» e vale per i corsi che non ne scelgono un altro."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base

TIPI_DOMANDA = ("stelle", "testo", "si_no", "scelta")


class QuestionarioGradimento(Base):
    __tablename__ = "questionari_gradimento"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome       = Column(String, nullable=False, unique=True)
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    domande = relationship("DomandaGradimento", cascade="all, delete-orphan", order_by="DomandaGradimento.ordine", back_populates="questionario")


class DomandaGradimento(Base):
    __tablename__ = "domande_gradimento"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionario_id = Column(UUID(as_uuid=True), ForeignKey("questionari_gradimento.id", ondelete="CASCADE"), nullable=False, index=True)
    testo           = Column(String, nullable=False)
    tipo            = Column(String, nullable=False)          # stelle | testo | si_no | scelta
    opzioni         = Column(JSON, nullable=True)             # solo per «scelta»
    obbligatoria    = Column(Boolean, nullable=False, default=False, server_default="false")
    ordine          = Column(Integer, nullable=False, default=0)

    questionario = relationship("QuestionarioGradimento", back_populates="domande")
