from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class UserRole(str, enum.Enum):
    # Ruolo funzionale minimo, non negoziabile. La struttura organizzativa vera
    # (reparti, sedi, chi-approva-cosa) vive nei Group liberi, non qui.
    admin_tecnico  = "admin_tecnico"   # IT/dev, configura la piattaforma
    training_admin = "training_admin" # ufficio formazione/HR, gestisce corsi/edizioni/iscrizioni
    user           = "user"           # dipendente/discente/eventuale docente occasionale

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    is_active = Column(Boolean, default=True)

    # Interno all'azienda vs esterno (docente/collaboratore di un ente terzo).
    # Un utente esterno deve avere un'organizzazione di riferimento.
    is_external = Column(Boolean, default=False, nullable=False)
    organizzazione_id = Column(UUID(as_uuid=True), ForeignKey("organizzazioni.id"), nullable=True)

    manager_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    can_see_all = Column(Boolean, default=False)

    # Data di ingresso in azienda: aggancio per i percorsi con trigger "ingresso in azienda".
    data_ingresso = Column(DateTime(timezone=True), nullable=True)

    # "locale" = password gestita qui (cambio self-service abilitato).
    # Altri valori (es. "dominio") disabilitano il cambio password in UI - pensato
    # per una futura integrazione SSO/AD, senza doverci ritornare sopra allora.
    origine_credenziali = Column(String, nullable=False, default="locale")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
