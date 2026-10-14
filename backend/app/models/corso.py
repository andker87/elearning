from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, Enum as SAEnum
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

    # Se il corso ha sia un test iniziale che uno finale, l'Ufficio Formazione
    # decide corso per corso se vuole il confronto pre/post (delta di
    # apprendimento) - non è un comportamento automatico.
    confronta_pre_post_test = Column(Boolean, nullable=False, default=False)

    # Auto-iscrizione dal catalogo (non per corsi obbligatori via percorso):
    # richiedi_approvazione_responsabile ha senso solo se permetti_autoiscrizione è attivo.
    permetti_autoiscrizione = Column(Boolean, nullable=False, default=False)
    richiedi_approvazione_responsabile = Column(Boolean, nullable=False, default=False)

    # Rinnovo automatico (opzione dell'Ufficio Formazione, spenta di default): a
    # ridosso della scadenza iscrive la persona alla prossima sessione utile.
    # Ha senso solo se il corso ha una validita' (validita_mesi).
    rinnovo_automatico      = Column(Boolean, nullable=False, default=False, server_default="false")
    rinnovo_giorni_anticipo = Column(Integer, nullable=False, default=30, server_default="30")

    # Versionamento contenuti: bump esplicito (azione separata dalla normale
    # modifica dei campi, vedi api/corsi.py "nuova-versione"), mai automatico.
    # versione_minima_valida <= versione: chi ha completato con una versione
    # precedente a questa non è più compliant (serve davvero per gli
    # aggiornamenti normativi); se invece versione_minima_valida resta
    # indietro rispetto a versione, chi ha completato prima resta compliant e
    # vede solo un'etichetta informativa "aggiornamento disponibile".
    versione               = Column(Integer, nullable=False, default=1)
    versione_minima_valida = Column(Integer, nullable=False, default=1)

    # Template grafico per gli attestati di questo corso (editor in
    # api/certificato_templates.py) - se non impostato si usa il template
    # aziendale di default, se esiste (vedi services/certificati.py).
    certificato_template_id = Column(UUID(as_uuid=True), ForeignKey("certificato_templates.id"), nullable=True)

    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
