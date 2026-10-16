from sqlalchemy import event, Column, String, Boolean, Integer, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base
from .tipi import TestoCifrato

class UserRole(str, enum.Enum):
    # Ruolo funzionale minimo, non negoziabile. La struttura organizzativa vera
    # (reparti, sedi, chi-approva-cosa) vive nei Group liberi, non qui.
    admin_tecnico  = "admin_tecnico"   # IT/dev, configura la piattaforma
    training_admin = "training_admin" # ufficio formazione/HR, gestisce corsi/edizioni/iscrizioni
    user           = "user"           # dipendente/discente/eventuale docente occasionale

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(TestoCifrato, nullable=False)          # cifrato: si cerca con email_idx
    email_idx = Column(String, unique=True, nullable=False, index=True)   # impronta dell'email (services/impronte.py), univoca senza badare alle maiuscole
    full_name = Column(TestoCifrato, nullable=False)      # cifrato: ordinamento e ricerca per nome si fanno nel programma
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    is_active = Column(Boolean, default=True)

    # Interno all'azienda vs esterno (docente/collaboratore di un ente terzo).
    # Un utente esterno deve avere un'organizzazione di riferimento.
    is_external = Column(Boolean, default=False, nullable=False)
    organizzazione_id = Column(UUID(as_uuid=True), ForeignKey("organizzazioni.id"), nullable=True)

    # Visibilità totale indipendente dalla gerarchia uffici (es. ufficio
    # formazione/HR). Il "chi è il responsabile di chi" NON vive qui: si
    # deriva dagli uffici (Group.is_ufficio + responsabile_id), vedi
    # services/gerarchia.py — una sola fonte di verità, niente da conciliare.
    can_see_all = Column(Boolean, default=False)

    # Data di ingresso in azienda: aggancio per i percorsi con trigger "ingresso in azienda".
    data_ingresso = Column(DateTime(timezone=True), nullable=True)

    # "locale" = password gestita qui (cambio self-service abilitato).
    # Altri valori (es. "dominio") disabilitano il cambio password in UI - pensato
    # per una futura integrazione SSO/AD, senza doverci ritornare sopra allora.
    origine_credenziali = Column(String, nullable=False, default="locale")

    # Identificativo stabile (claim "sub") dell'utente presso l'IdP aziendale,
    # fissato al primo accesso SSO: da li' in poi conta il sub, non solo
    # l'email (un indirizzo riassegnato a un'altra persona non eredita l'account).
    sso_subject = Column(String, nullable=True, unique=True)

    # Token opaco per il feed iCal personale (sezione H): generato al primo
    # accesso a GET /api/calendario/url, non all'onboarding - niente di
    # segreto sul piano dei permessi (dà solo le date dei propri corsi), ma
    # va comunque rigenerabile se qualcuno lo condivide per sbaglio.
    calendar_token_hash = Column(String, nullable=True, unique=True)   # SHA-256 del token: il token in chiaro non e' conservato

    # Sicurezza accessi: blocco temporaneo dopo troppi tentativi falliti,
    # versione del token (ogni cambio/reset password invalida le altre sessioni),
    # obbligo di scegliere una password propria dopo averne ricevuta una assegnata.
    tentativi_falliti   = Column(Integer, nullable=False, default=0, server_default="0")
    bloccato_fino       = Column(DateTime(timezone=True), nullable=True)
    token_version       = Column(Integer, nullable=False, default=0, server_default="0")
    password_da_cambiare = Column(Boolean, nullable=False, default=False, server_default="false")

    created_at = Column(DateTime(timezone=True), server_default=func.now())


@event.listens_for(User, "before_insert")
@event.listens_for(User, "before_update")
def _impronta_email(mapper, connection, utente):
    from ..services.impronte import impronta
    utente.email_idx = impronta(utente.email)
