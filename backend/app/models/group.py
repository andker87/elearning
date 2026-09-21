from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Group(Base):
    """Gruppi liberi, non vincolati a una struttura organizzativa predefinita:
    ogni azienda li userà per modellare la propria realtà (reparti, sedi, ruoli),
    da qui i permessi in JSON invece di un enum chiuso."""
    __tablename__ = "groups"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color       = Column(String, default="#5a6b8a")
    permissions = Column(JSON, default=dict)
    is_system   = Column(Boolean, default=False)   # "Ruoli": non eliminabili, ma rinominabili
    is_active   = Column(Boolean, default=True)
    sort_order  = Column(String, default="0")
    # Sottogruppi: solo per i gruppi liberi (non per i Ruoli di sistema).
    parent_id   = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
    members     = relationship("UserGroup", back_populates="group", cascade="all, delete-orphan")

class UserGroup(Base):
    __tablename__ = "user_groups"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    group_id   = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user       = relationship("User", backref="group_memberships")
    group      = relationship("Group", back_populates="members")
