from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base

class CertificatoTemplate(Base):
    """Template grafico per attestati: sfondo caricato + campi (variabili)
    posizionati con l'editor drag-and-drop (api/certificato_templates.py).
    Più template possono coesistere: ogni Corso può assegnarne uno (vedi
    Corso.certificato_template_id); se non assegnato si usa quello con
    is_default=True; se nessuno esiste si ricade sul layout fisso in
    services/certificati.py."""
    __tablename__ = "certificato_templates"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome          = Column(String, nullable=False)
    immagine_path = Column(String, nullable=True)
    larghezza_px  = Column(Integer, nullable=True)
    altezza_px    = Column(Integer, nullable=True)
    # Lista di {chiave, x, y, font_size, bold, align, colore} - coordinate in
    # pixel dell'immagine originale, come posizionate nell'editor.
    campi         = Column(JSON, nullable=False, default=list)
    is_default    = Column(Boolean, nullable=False, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
