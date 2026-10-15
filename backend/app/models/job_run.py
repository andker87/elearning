from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from ..database import Base

class JobRun(Base):
    """Storico esecuzioni dei job pianificati: l'APScheduler vive in memoria e
    perde tutto al riavvio, qui resta traccia di quando e come e' girato."""
    __tablename__ = "job_runs"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id      = Column(String, nullable=False, index=True)
    started_at  = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    esito       = Column(String, nullable=False)  # ok | errore
    durata_ms   = Column(Integer, nullable=True)
    errore      = Column(Text, nullable=True)
    dettaglio   = Column(Text, nullable=True)  # riepilogo prodotto dal job (es. quanti utenti toccati)
