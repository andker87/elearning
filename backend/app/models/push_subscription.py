from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class PushSubscription(Base):
    """Una sottoscrizione Web Push = un dispositivo/browser su cui l'utente ha
    attivato le notifiche (può averne più d'una: pc + cellulare). L'endpoint
    è unico per dispositivo: un nuovo login sullo stesso dispositivo aggiorna
    la riga invece di duplicarla."""
    __tablename__ = "push_subscriptions"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint   = Column(String, nullable=False, unique=True)
    p256dh     = Column(String, nullable=False)
    auth       = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
