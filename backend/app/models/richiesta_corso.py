from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class StatoRichiestaCorso(str, enum.Enum):
    in_attesa = "in_attesa"
    approvata = "approvata"
    rifiutata = "rifiutata"

class RichiestaCorso(Base):
    """Un responsabile chiede all'Ufficio Formazione di organizzare una sessione
    su un argomento (corso già a catalogo o nuovo), con pre-iscrizione di chi è
    potenzialmente interessato - serve a valutare la richiesta anche in base al
    numero di persone coinvolte. Single-hop: va diretta a HR, non risale la
    catena di approvazione come il fabbisogno formativo (sezione Q)."""
    __tablename__ = "richieste_corso"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    richiedente_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    corso_id    = Column(UUID(as_uuid=True), ForeignKey("corsi.id"), nullable=True)  # None = argomento non a catalogo
    argomento   = Column(String, nullable=True)  # obbligatorio se corso_id è None
    note        = Column(Text, nullable=True)
    stato       = Column(SAEnum(StatoRichiestaCorso), nullable=False, default=StatoRichiestaCorso.in_attesa)
    valutata_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    nota_valutazione = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    valutata_at = Column(DateTime(timezone=True), nullable=True)

    persone     = relationship("RichiestaCorsoPersona", cascade="all, delete-orphan", back_populates="richiesta")

class RichiestaCorsoPersona(Base):
    """Pre-iscrizione: persone che il responsabile segnala come interessate."""
    __tablename__ = "richieste_corso_persone"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    richiesta_id = Column(UUID(as_uuid=True), ForeignKey("richieste_corso.id"), nullable=False)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    richiesta   = relationship("RichiestaCorso", back_populates="persone")
    utente      = relationship("User")
