from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class StatoVideo(str, enum.Enum):
    caricato       = "caricato"
    in_elaborazione = "in_elaborazione"  # transcodifica ffmpeg in corso
    pronto         = "pronto"
    errore         = "errore"

class VideoContenuto(Base):
    """Un contenuto video caricato e normalizzato dalla pipeline ffmpeg,
    servito da storage locale (mount su disco del datacenter)."""
    __tablename__ = "video_contenuti"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titolo         = Column(String, nullable=False)
    file_originale = Column(String, nullable=True)
    file_path      = Column(String, nullable=True)   # file normalizzato pronto per lo streaming
    durata_secondi = Column(Integer, nullable=True)
    stato          = Column(SAEnum(StatoVideo), nullable=False, default=StatoVideo.caricato)
    sottotitoli_path = Column(String, nullable=True)  # .vtt
    blocca_skip_avanti = Column(Boolean, default=True)  # impedisce di saltare oltre il punto raggiunto
    altre_versioni_in_corso = Column(Boolean, nullable=False, default=False, server_default="false")  # qualita' piu' alte ancora in preparazione
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    capitoli = relationship("VideoCapitolo", cascade="all, delete-orphan", back_populates="video",
                             order_by="VideoCapitolo.inizio_secondi")
    versioni = relationship("VideoVersione", cascade="all, delete-orphan", back_populates="video",
                             order_by="VideoVersione.altezza")

class VideoVersione(Base):
    """Una qualita' del video (480p, 720p, 1080p, 4K...): file MP4 separato, cifrato su disco."""
    __tablename__ = "video_versioni"
    __table_args__ = (UniqueConstraint("video_id", "altezza", name="uq_video_versione_altezza"),)
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id       = Column(UUID(as_uuid=True), ForeignKey("video_contenuti.id"), nullable=False, index=True)
    altezza        = Column(Integer, nullable=False)
    larghezza      = Column(Integer, nullable=True)
    bitrate_kbps   = Column(Integer, nullable=True)      # tetto di banda previsto: serve a scegliere la qualita' in base alla rete
    dimensione_bytes = Column(BigInteger, nullable=True)
    file_path      = Column(String, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    video          = relationship("VideoContenuto", back_populates="versioni")

class VideoCapitolo(Base):
    __tablename__ = "video_capitoli"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id       = Column(UUID(as_uuid=True), ForeignKey("video_contenuti.id"), nullable=False)
    titolo         = Column(String, nullable=False)
    inizio_secondi = Column(Integer, nullable=False, default=0)
    video          = relationship("VideoContenuto", back_populates="capitoli")

class VideoProgresso(Base):
    """Heartbeat lato server del punto di riproduzione massimo raggiunto per
    iscrizione - fonte di verità anti-frode per il completamento video, non
    fidarsi del solo stato client."""
    __tablename__ = "video_progressi"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iscrizione_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    secondo_massimo_raggiunto = Column(Integer, nullable=False, default=0)
    ultimo_heartbeat_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
