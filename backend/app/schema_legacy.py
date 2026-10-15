"""Come si portava lo schema in pari prima di Alembic.

Serve UNA volta sola, per i database nati prima delle migrazioni: li porta all'ultimo stato
descritto dai modelli di allora, poi `migrazioni.esegui_migrazioni` li marca come gia' alla
migrazione di partenza (0001). Per le installazioni nuove e per ogni cambio futuro non si
usa: lo schema lo costruiscono e lo cambiano le migrazioni in `migrations/versions`.
NON aggiungere altro qui.

Attenzione: `create_all` usa i modelli di OGGI, non quelli di quando e' nata la 0001. Per questo ogni
migrazione dalla 0002 in poi DEVE essere idempotente (controllare se la colonna/il vincolo c'e' gia'
prima di crearlo): un database vecchio arriva alla 0001 con gia' le novita' dei modelli attuali."""
from sqlalchemy import text

from .database import Base


def porta_a_baseline(engine):
    """Niente Alembic configurato ancora: create_all crea solo tabelle nuove,
    non altera quelle esistenti. Per i pochi cambi di colonna fuori da una
    tabella nuova si usano ALTER idempotenti qui, finché non serve altro."""
    Base.metadata.create_all(bind=engine)
    # ALTER TYPE ... ADD VALUE non può girare dentro la stessa transazione di
    # altri comandi su quel tipo (limite Postgres) - connessione autocommit a parte.
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))
        conn.execute(text(
            "ALTER TYPE statoiscrizione ADD VALUE IF NOT EXISTS 'in_lista_attesa'"
        ))
        conn.execute(text(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'statofabbisognorichiesta') THEN "
            "ALTER TYPE statofabbisognorichiesta ADD VALUE IF NOT EXISTS 'fusa'; END IF; END $$"
        ))
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS is_ufficio BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS responsabile_id UUID REFERENCES users(id)"
        ))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS manager_id"))
        conn.execute(text(
            "ALTER TABLE corsi ADD COLUMN IF NOT EXISTS confronta_pre_post_test BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE corsi ADD COLUMN IF NOT EXISTS permetti_autoiscrizione BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE corsi ADD COLUMN IF NOT EXISTS richiedi_approvazione_responsabile BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text("ALTER TABLE gradimenti ADD COLUMN IF NOT EXISTS voto_corso INTEGER"))
        conn.execute(text("ALTER TABLE gradimenti ADD COLUMN IF NOT EXISTS commento_corso TEXT"))
        colonna_vecchia_presente = conn.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_name = 'gradimenti' AND column_name = 'voto'"
        )).first()
        if colonna_vecchia_presente:
            conn.execute(text("UPDATE gradimenti SET voto_corso = voto WHERE voto_corso IS NULL AND voto IS NOT NULL"))
            conn.execute(text("UPDATE gradimenti SET commento_corso = commento WHERE commento_corso IS NULL AND commento IS NOT NULL"))
            conn.execute(text("ALTER TABLE gradimenti DROP COLUMN voto"))
            conn.execute(text("ALTER TABLE gradimenti DROP COLUMN IF EXISTS commento"))
        conn.execute(text("ALTER TABLE gradimenti ALTER COLUMN voto_corso SET NOT NULL"))
        conn.execute(text(
            "ALTER TABLE edizioni ADD COLUMN IF NOT EXISTS lista_attesa_abilitata BOOLEAN NOT NULL DEFAULT false"
        ))
        # SMTP è passato a configurazione solo da ambiente (vedi config.py):
        # le colonne DB non servono più e potevano contenere una password in
        # chiaro da installazioni precedenti, quindi vengono rimosse.
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tentativi_falliti INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS bloccato_fino TIMESTAMPTZ"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_da_cambiare BOOLEAN NOT NULL DEFAULT false"))
        conn.execute(text("ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS dettaglio TEXT"))
        conn.execute(text("ALTER TABLE fabbisogno_richieste ADD COLUMN IF NOT EXISTS fusa_in_id UUID REFERENCES fabbisogno_richieste(id)"))
        conn.execute(text("ALTER TABLE corsi ADD COLUMN IF NOT EXISTS rinnovo_automatico BOOLEAN NOT NULL DEFAULT false"))
        conn.execute(text("ALTER TABLE corsi ADD COLUMN IF NOT EXISTS rinnovo_giorni_anticipo INTEGER NOT NULL DEFAULT 30"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS privacy_testo TEXT"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS privacy_pdf_path VARCHAR"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS privacy_aggiornata_at TIMESTAMPTZ"))
        # Le richieste di cancellazione sono state tolte: la piattaforma e' uno
        # strumento aziendale e i dati di formazione si conservano per obbligo.
        conn.execute(text("DROP TABLE IF EXISTS richieste_cancellazione"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_abilitato"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_host"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_port"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_user"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_password"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_mittente"))
        conn.execute(text("ALTER TABLE azienda DROP COLUMN IF EXISTS smtp_tls"))
        conn.execute(text("ALTER TABLE corsi ADD COLUMN IF NOT EXISTS versione INTEGER NOT NULL DEFAULT 1"))
        conn.execute(text("ALTER TABLE corsi ADD COLUMN IF NOT EXISTS versione_minima_valida INTEGER NOT NULL DEFAULT 1"))
        conn.execute(text("ALTER TABLE iscrizioni ADD COLUMN IF NOT EXISTS versione_corso INTEGER"))
        conn.execute(text(
            "ALTER TABLE corsi ADD COLUMN IF NOT EXISTS certificato_template_id UUID "
            "REFERENCES certificato_templates(id)"
        ))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS vapid_private_key TEXT"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS vapid_public_key VARCHAR"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS calendar_token VARCHAR"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_calendar_token ON users (calendar_token)"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS nome_piattaforma VARCHAR"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS url_pubblico VARCHAR"))
        conn.execute(text("ALTER TABLE azienda ADD COLUMN IF NOT EXISTS icona_path VARCHAR"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_subject VARCHAR"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_sso_subject ON users (sso_subject)"))

