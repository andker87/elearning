from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class AzioneTestNonSuperato(str, enum.Enum):
    concludi_comunque       = "concludi_comunque"        # completa il corso anche se il test finale non è superato
    concludi_scadenza_breve = "concludi_scadenza_breve"  # completa, ma deve rifare il corso entro N giorni
    rifai_test              = "rifai_test"               # deve ripetere solo il test, finché non lo supera
    rifai_corso             = "rifai_corso"               # il corso risulta non completato, va rifatto da zero

class Corso(Base):
    """Definizione del corso, indipendente da come/quando viene erogato.
    La modalità di erogazione vive nella singola Edizione."""
    __tablename__ = "corsi"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titolo        = Column(String, nullable=False)
    descrizione   = Column(Text, nullable=True)
    categoria     = Column(String, nullable=True)  # libera: "sicurezza", "compliance", "onboarding", ...
    # Se valorizzato, il corso richiede un rinnovo periodico (refresh) ogni N mesi.
    validita_mesi = Column(Integer, nullable=True)

    # Non tutti i corsi hanno un test finale: la policy sotto ha senso solo se attivo.
    ha_test_finale = Column(Boolean, nullable=False, default=False)
    azione_test_non_superato = Column(SAEnum(AzioneTestNonSuperato), nullable=False,
                                       default=AzioneTestNonSuperato.concludi_comunque)
    giorni_scadenza_breve    = Column(Integer, nullable=True)  # usato solo con concludi_scadenza_breve

    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
