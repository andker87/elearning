from sqlalchemy import Column, String, Text, Integer, Boolean, Float, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class MomentoTest(str, enum.Enum):
    iniziale   = "iniziale"
    intermedio = "intermedio"   # agganciato a un capitolo video, es.
    finale     = "finale"

class Test(Base):
    __tablename__ = "test"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corso_id    = Column(UUID(as_uuid=True), ForeignKey("corsi.id"), nullable=False)
    titolo      = Column(String, nullable=False)
    momento     = Column(SAEnum(MomentoTest), nullable=False, default=MomentoTest.finale)
    soglia_superamento_pct = Column(Float, nullable=False, default=60.0)
    tentativi_max = Column(Integer, nullable=True)  # null = illimitati
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    domande = relationship("Domanda", cascade="all, delete-orphan", back_populates="test",
                            order_by="Domanda.ordine")

class Domanda(Base):
    __tablename__ = "domande"
    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("test.id"), nullable=False)
    testo   = Column(Text, nullable=False)
    ordine  = Column(Integer, nullable=False, default=0)
    test    = relationship("Test", back_populates="domande")
    opzioni = relationship("OpzioneRisposta", cascade="all, delete-orphan", back_populates="domanda")

class OpzioneRisposta(Base):
    __tablename__ = "opzioni_risposta"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domanda_id = Column(UUID(as_uuid=True), ForeignKey("domande.id"), nullable=False)
    testo      = Column(Text, nullable=False)
    corretta   = Column(Boolean, default=False)
    domanda    = relationship("Domanda", back_populates="opzioni")

class TentativoTest(Base):
    __tablename__ = "tentativi_test"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id       = Column(UUID(as_uuid=True), ForeignKey("test.id"), nullable=False)
    iscrizione_id = Column(UUID(as_uuid=True), ForeignKey("iscrizioni.id"), nullable=False)
    risposte      = Column(JSON, default=dict)  # { domanda_id: opzione_id }
    punteggio_pct = Column(Float, nullable=True)
    superato      = Column(Boolean, nullable=True)
    completato_at = Column(DateTime(timezone=True), server_default=func.now())

class Gradimento(Base):
    """Valutazione di gradimento del discente su un'edizione conclusa."""
    __tablename__ = "gradimenti"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iscrizione_id = Column(UUID(as_uuid=True), ForeignKey("iscrizioni.id"), nullable=False)
    voto          = Column(Integer, nullable=False)  # 1-5
    commento      = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
