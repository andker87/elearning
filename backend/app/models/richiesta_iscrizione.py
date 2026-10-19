from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

STATI_RICHIESTA = ("in_attesa", "approvata", "rifiutata")


class RichiestaIscrizione(Base):
    """Un responsabile chiede alla Formazione di iscrivere una persona del suo team a una sessione di un corso
    «su richiesta». L'iscrizione vera si crea solo all'approvazione. Una sola richiesta in attesa per persona e sessione."""
    __tablename__ = "richieste_iscrizione"
    __table_args__ = (Index("uq_richiesta_iscrizione_in_attesa", "edizione_id", "user_id", unique=True, postgresql_where=text("stato = 'in_attesa'")),)
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edizione_id    = Column(UUID(as_uuid=True), ForeignKey("edizioni.id"), nullable=False)
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)       # la persona da iscrivere
    richiedente_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)       # il responsabile che chiede
    stato          = Column(String, nullable=False, default="in_attesa", server_default="in_attesa")
    motivo_rifiuto = Column(Text, nullable=True)
    valutata_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    valutata_at    = Column(DateTime(timezone=True), nullable=True)
