from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Azienda(Base):
    """Singleton: l'azienda proprietaria di questa istanza della piattaforma."""
    __tablename__ = "azienda"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ragione_sociale = Column(String, nullable=True)
    partita_iva     = Column(String, nullable=True)
    codice_fiscale  = Column(String, nullable=True)
    indirizzo       = Column(String, nullable=True)
    cap             = Column(String, nullable=True)
    citta           = Column(String, nullable=True)
    provincia       = Column(String, nullable=True)
    nazione         = Column(String, default="IT")
    email           = Column(String, nullable=True)
    pec             = Column(String, nullable=True)
    logo_path       = Column(String, nullable=True)

    # Impostazioni della piattaforma (pagina "Piattaforma"): nome mostrato in
    # sidebar/login/manifest, URL pubblico (link nelle email, feed calendario),
    # icona dell'app che, se presente, ha la precedenza sul logo aziendale.
    nome_piattaforma = Column(String, nullable=True)
    url_pubblico     = Column(String, nullable=True)
    icona_path       = Column(String, nullable=True)

    # Informativa privacy (testo e/o PDF): consultabile da tutti dal profilo,
    # nessuna accettazione richiesta.
    privacy_testo         = Column(Text, nullable=True)
    privacy_pdf_path      = Column(String, nullable=True)
    privacy_aggiornata_at = Column(DateTime(timezone=True), nullable=True)

    # Chiavi VAPID per le notifiche push web (RFC 8292) - generate una volta
    # sola all'avvio se assenti (vedi main.py), non sono un segreto di terze
    # parti come SMTP: è la piattaforma stessa a generarle, quindi restano
    # nel DB invece che in ambiente (vedi sezione D2 del roadmap).
    vapid_private_key = Column(Text, nullable=True)
    vapid_public_key  = Column(String, nullable=True)

    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
