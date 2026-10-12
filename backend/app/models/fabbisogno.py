from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid, enum
from ..database import Base

class StatoCampagna(str, enum.Enum):
    aperta = "aperta"
    chiusa = "chiusa"

class StatoInvito(str, enum.Enum):
    da_decidere = "da_decidere"  # il responsabile dell'ufficio deve ancora scegliere
    delegato    = "delegato"      # ha girato la campagna ai sotto-uffici
    risposto    = "risposto"      # ha risposto direttamente (creata una FabbisognoRichiesta)

class PeriodoFabbisogno(str, enum.Enum):
    mese       = "mese"
    trimestre  = "trimestre"
    semestre   = "semestre"
    anno       = "anno"

class StatoFabbisognoRichiesta(str, enum.Enum):
    in_revisione  = "in_revisione"   # sta risalendo la catena, in attesa del prossimo responsabile
    approvata_hr  = "approvata_hr"    # ha raggiunto la radice ed è stata approvata: pronta per HR
    rifiutata     = "rifiutata"
    fusa          = "fusa"           # unita ad altre in una richiesta piu' ampia (vedi fusa_in_id): non e' piu' in coda da sola

class FabbisognoCampagna(Base):
    """Campagna avviata da HR/Formazione (flusso A, sezione Q): invito a cascata
    ai responsabili, con scadenza opzionale. Le richieste spontanee (flusso B)
    non hanno una campagna (FabbisognoRichiesta.campagna_id = None)."""
    __tablename__ = "fabbisogno_campagne"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titolo      = Column(String, nullable=False)
    descrizione = Column(Text, nullable=True)
    creata_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    scadenza    = Column(DateTime(timezone=True), nullable=True)
    stato       = Column(SAEnum(StatoCampagna), nullable=False, default=StatoCampagna.aperta)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class FabbisognoCampagnaInvito(Base):
    """Un ufficio è stato raggiunto dalla campagna: il suo responsabile deve
    decidere se rispondere direttamente o delegare ai sotto-uffici (sezione L)."""
    __tablename__ = "fabbisogno_campagna_inviti"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campagna_id = Column(UUID(as_uuid=True), ForeignKey("fabbisogno_campagne.id"), nullable=False)
    ufficio_id  = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    stato       = Column(SAEnum(StatoInvito), nullable=False, default=StatoInvito.da_decidere)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class FabbisognoRichiesta(Base):
    """Un contributo di fabbisogno, posseduto da un ufficio, che risale la
    catena di approvazione (sezione Q): ad ogni approvazione del responsabile
    corrente, 'ufficio_in_revisione_presso_id' si sposta all'ufficio padre,
    finché non raggiunge la radice (diventa None, stato=approvata_hr)."""
    __tablename__ = "fabbisogno_richieste"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campagna_id = Column(UUID(as_uuid=True), ForeignKey("fabbisogno_campagne.id"), nullable=True)
    ufficio_origine_id = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    ufficio_in_revisione_presso_id = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=True)
    creata_da_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    argomento   = Column(String, nullable=False)
    note        = Column(Text, nullable=True)
    periodo     = Column(SAEnum(PeriodoFabbisogno), nullable=True)
    riferimento_periodo = Column(String, nullable=True)  # es. "Q2 2027", libero
    numero_persone_stimate = Column(Integer, nullable=True)
    stato       = Column(SAEnum(StatoFabbisognoRichiesta), nullable=False, default=StatoFabbisognoRichiesta.in_revisione)
    motivo_rifiuto = Column(Text, nullable=True)
    # Fusione: chi sta nella catena di approvazione puo' unire richieste simili in una sola.
    # Le originali restano intatte (stato "fusa") e puntano alla richiesta che le contiene,
    # cosi' la provenienza si ricostruisce sempre, anche dopo piu' fusioni a livelli diversi.
    fusa_in_id  = Column(UUID(as_uuid=True), ForeignKey("fabbisogno_richieste.id"), nullable=True, index=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    aggiornato_at = Column(DateTime(timezone=True), onupdate=func.now())
