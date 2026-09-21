from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class TipoCertificato(str, enum.Enum):
    base    = "base"     # PDF generato dal sistema + codice/hash di verifica pubblico
    firmato = "firmato"  # + firma digitale remota di un provider esterno (da configurare)

class Certificato(Base):
    __tablename__ = "certificati"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iscrizione_id = Column(UUID(as_uuid=True), ForeignKey("iscrizioni.id"), nullable=False)
    tipo          = Column(SAEnum(TipoCertificato), nullable=False, default=TipoCertificato.base)
    codice_verifica = Column(String, unique=True, nullable=False)
    pdf_path      = Column(String, nullable=True)
    emesso_at     = Column(DateTime(timezone=True), server_default=func.now())
