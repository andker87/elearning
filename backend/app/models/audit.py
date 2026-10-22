from sqlalchemy import event, Column, String, DateTime, ForeignKey, Index, Date, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base
from .tipi import TestoCifrato

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_created_at", "created_at"), Index("ix_audit_log_action_created_at", "action", "created_at"))
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user_email  = Column(TestoCifrato, nullable=True)     # cifrati: l'IP e l'email si filtrano per valore esatto con le impronte
    user_email_idx = Column(String, nullable=True, index=True)
    action      = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id   = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)
    detail      = Column(TestoCifrato, nullable=True)
    ip_address  = Column(TestoCifrato, nullable=True)
    ip_idx      = Column(String, nullable=True, index=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


@event.listens_for(AuditLog, "before_insert")
def _impronte_audit(mapper, connection, riga):
    from ..services.impronte import impronta
    riga.user_email_idx = impronta(riga.user_email)
    riga.ip_idx = impronta(riga.ip_address)


class AuditEsportazione(Base):
    """Giorni del registro gia' esportati: tiene il conto indipendentemente dai file, che un
    collettore di log puo' spostare o cancellare dopo averli prelevati."""
    __tablename__ = "audit_esportazioni"
    giorno      = Column(Date, primary_key=True)
    righe       = Column(Integer, nullable=False, default=0)
    esportato_at = Column(DateTime(timezone=True), server_default=func.now())
