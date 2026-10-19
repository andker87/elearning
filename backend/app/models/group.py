from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Group(Base):
    """Ufficio: nodo della struttura organizzativa (albero di uffici e sottouffici) con un
    responsabile (singolo, niente co-gestione). La gerarchia dei responsabili si deriva risalendo
    parent_id (vedi services/gerarchia.py). Dalla 2.2.0 i gruppi sono SOLO uffici: le categorie
    trasversali (preposto, addetto antincendio...) sono le Mansioni (models/mansione.py)."""
    __tablename__ = "groups"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color       = Column(String, default="#5a6b8a")
    is_active   = Column(Boolean, default=True)
    sort_order  = Column(String, default="0")
    parent_id   = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=True)

    # Sempre vero dalla 2.2.0 (ogni gruppo e' un ufficio). La colonna resta perche' la gerarchia
    # la usa nei filtri: da togliere in una pulizia dedicata.
    is_ufficio      = Column(Boolean, default=True, nullable=False)
    responsabile_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
    members     = relationship("UserGroup", back_populates="group", cascade="all, delete-orphan")
    responsabile = relationship("User", foreign_keys=[responsabile_id])

class UserGroup(Base):
    """Ufficio di appartenenza: una sola riga per persona (vincolo sul user_id)."""
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_groups_user"),)
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    group_id   = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user       = relationship("User", backref="group_memberships")
    group      = relationship("Group", back_populates="members")
