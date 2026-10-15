from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class PasswordResetToken(Base):
    """Link di reset inviato per email: nel DB resta solo l'hash del token."""
    __tablename__ = "password_reset_tokens"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True)
    scade_at   = Column(DateTime(timezone=True), nullable=False)
    usato      = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RichiestaResetPassword(Base):
    """Richiesta gestita da un Admin tecnico quando l'invio email non e' configurato."""
    __tablename__ = "richieste_reset_password"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stato         = Column(String, nullable=False, default="in_attesa")  # in_attesa | completata
    gestita_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    gestita_at    = Column(DateTime(timezone=True), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
