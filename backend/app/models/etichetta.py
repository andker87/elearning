from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base

class EtichettaFamiglia(Base):
    """Una dimensione con cui classificare i corsi (Tematica, Riferimento normativo,
    Ambito, Obbligo...). La definisce l'Ufficio Formazione: scelta singola o multipla,
    obbligatoria o no. Le famiglie rendono affidabili i filtri: ogni etichetta sta in
    una dimensione precisa e si sceglie da un elenco, mai digitata."""
    __tablename__ = "etichette_famiglie"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome            = Column(String, nullable=False, unique=True)
    descrizione     = Column(Text, nullable=True)
    scelta_multipla = Column(Boolean, nullable=False, default=True)
    obbligatoria    = Column(Boolean, nullable=False, default=False)
    ordine          = Column(Integer, nullable=False, default=0)
    archiviata      = Column(Boolean, nullable=False, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    etichette       = relationship("Etichetta", back_populates="famiglia", order_by="Etichetta.ordine")

class Etichetta(Base):
    """Un valore di una famiglia. Si archivia invece di cancellarla quando e' in uso,
    cosi' le estrazioni passate restano leggibili. 'esclusiva' (es. Trasversale) fa
    comparire un avviso se scelta insieme ad altre della stessa famiglia."""
    __tablename__ = "etichette"
    __table_args__ = (UniqueConstraint("famiglia_id", "nome", name="uq_etichetta_famiglia_nome"),)
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    famiglia_id = Column(UUID(as_uuid=True), ForeignKey("etichette_famiglie.id"), nullable=False, index=True)
    nome        = Column(String, nullable=False)
    ordine      = Column(Integer, nullable=False, default=0)
    esclusiva   = Column(Boolean, nullable=False, default=False)
    archiviata  = Column(Boolean, nullable=False, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    famiglia    = relationship("EtichettaFamiglia", back_populates="etichette")

class CorsoEtichetta(Base):
    __tablename__ = "corsi_etichette"
    __table_args__ = (UniqueConstraint("corso_id", "etichetta_id", name="uq_corso_etichetta"),)
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corso_id     = Column(UUID(as_uuid=True), ForeignKey("corsi.id"), nullable=False, index=True)
    etichetta_id = Column(UUID(as_uuid=True), ForeignKey("etichette.id"), nullable=False, index=True)
