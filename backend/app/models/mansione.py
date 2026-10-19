from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base


class Mansione(Base):
    """Etichetta trasversale (es. preposto, addetto antincendio): piatta, senza responsabile.
    Una persona puo' averne quante vuole. Serve ad assegnare percorsi in blocco e a filtrare
    gli elenchi; non da' permessi. La struttura organizzativa vive negli uffici (Group)."""
    __tablename__ = "mansioni"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color       = Column(String, default="#5a6b8a")
    is_active   = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class UserMansione(Base):
    __tablename__ = "user_mansioni"
    __table_args__ = (UniqueConstraint("user_id", "mansione_id", name="uq_user_mansioni"),)
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    mansione_id = Column(UUID(as_uuid=True), ForeignKey("mansioni.id"), nullable=False)
