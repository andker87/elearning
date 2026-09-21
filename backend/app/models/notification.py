from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Notification(Base):
    __tablename__ = "notifications"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tipo       = Column(String, nullable=False)  # es. "scadenza_corso", "nuova_iscrizione"
    testo      = Column(Text, nullable=False)
    link       = Column(String, nullable=True)
    letta      = Column(Boolean, default=False)
    # Chiave di deduplica (es. "scadenza_corso:<corso_id>:<2026-09>") per evitare
    # di rigenerare la stessa notifica ad ogni esecuzione dello scheduler.
    dedup_key  = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
