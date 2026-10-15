from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, Date, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_created_at", "created_at"), Index("ix_audit_log_action_created_at", "action", "created_at"))
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user_email  = Column(String, nullable=True)
    action      = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id   = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)
    detail      = Column(Text, nullable=True)
    ip_address  = Column(String, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class AuditEsportazione(Base):
    """Giorni del registro gia' esportati: tiene il conto indipendentemente dai file, che un
    collettore di log puo' spostare o cancellare dopo averli prelevati."""
    __tablename__ = "audit_esportazioni"
    giorno      = Column(Date, primary_key=True)
    righe       = Column(Integer, nullable=False, default=0)
    esportato_at = Column(DateTime(timezone=True), server_default=func.now())
