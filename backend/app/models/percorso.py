from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class MotivoObbligo(str, enum.Enum):
    legge          = "legge"
    policy_interna = "policy_interna"
    cliente        = "cliente"
    settore        = "settore"
    best_practice  = "best_practice"

class TriggerAssegnazione(str, enum.Enum):
    manuale          = "manuale"
    ingresso_azienda = "ingresso_azienda"
    gruppo           = "gruppo"      # ufficio (e sottouffici)
    mansione         = "mansione"

# Come si procede nei corsi del percorso: liberamente / uno dopo l'altro nell'ordine / con propedeuticita' scelte passo per passo
MODALITA_PERCORSO = ("libero", "sequenziale", "propedeuticita")


class PercorsoFormativo(Base):
    """Percorso: sequenza obbligatoria di Corsi (es. onboarding, refresh annuale).
    Puro livello di orchestrazione/assegnazione - lo stato di completamento di un
    Corso resta unico e condiviso tra tutti i percorsi che lo includono."""
    __tablename__ = "percorsi_formativi"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome         = Column(String, nullable=False)
    descrizione  = Column(Text, nullable=True)
    motivo       = Column(SAEnum(MotivoObbligo), nullable=False, default=MotivoObbligo.policy_interna)
    motivo_nota  = Column(String, nullable=True)  # es. "cliente Acme, contratto XYZ"
    trigger_tipo = Column(SAEnum(TriggerAssegnazione), nullable=False, default=TriggerAssegnazione.manuale)
    trigger_gruppo_id = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=True)
    trigger_mansione_id = Column(UUID(as_uuid=True), ForeignKey("mansioni.id"), nullable=True)
    modalita     = Column(String, nullable=False, default="libero", server_default="libero")
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    steps        = relationship("PercorsoStep", back_populates="percorso",
                                 cascade="all, delete-orphan", order_by="PercorsoStep.ordine")

class PercorsoStep(Base):
    __tablename__ = "percorso_steps"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    percorso_id = Column(UUID(as_uuid=True), ForeignKey("percorsi_formativi.id"), nullable=False)
    corso_id    = Column(UUID(as_uuid=True), ForeignKey("corsi.id"), nullable=False)
    ordine      = Column(Integer, nullable=False, default=0)
    percorso    = relationship("PercorsoFormativo", back_populates="steps")
    prerequisiti = relationship("PercorsoStepPrerequisito", foreign_keys="PercorsoStepPrerequisito.step_id",
                                 cascade="all, delete-orphan")

class PercorsoStepPrerequisito(Base):
    """step_id richiede che richiede_step_id sia completato prima di poter partire."""
    __tablename__ = "percorso_step_prerequisiti"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step_id          = Column(UUID(as_uuid=True), ForeignKey("percorso_steps.id"), nullable=False)
    richiede_step_id = Column(UUID(as_uuid=True), ForeignKey("percorso_steps.id"), nullable=False)

class PercorsoAssegnazione(Base):
    """Utente <-> Percorso: chi deve seguire questo percorso e con quale stato."""
    __tablename__ = "percorso_assegnazioni"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    percorso_id = Column(UUID(as_uuid=True), ForeignKey("percorsi_formativi.id"), nullable=False)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assegnato_il = Column(DateTime(timezone=True), server_default=func.now())
    completato   = Column(Boolean, default=False)
    completato_il = Column(DateTime(timezone=True), nullable=True)
