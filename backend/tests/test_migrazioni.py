"""Migrazioni dello schema: nuove installazioni, database precedenti, nessuna deriva dai modelli."""
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.database import Base, engine
from app.migrazioni import BASELINE, _config, esegui_migrazioni, importa_modelli

from conftest import ricrea_schema


def versione_corrente():
    with engine.connect() as c:
        return c.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


def ultima_migrazione():
    with engine.connect() as c:
        return ScriptDirectory.from_config(_config(c)).get_current_head()


def test_un_database_nuovo_arriva_all_ultima_migrazione():
    ricrea_schema()
    assert versione_corrente() == ultima_migrazione()


def test_le_migrazioni_coincidono_con_i_modelli():
    """Se questo fallisce hai cambiato un modello senza scrivere la migrazione:
    alembic revision --autogenerate -m "cosa cambia"."""
    importa_modelli()
    with engine.connect() as c:
        differenze = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata)
    assert differenze == [], differenze


def test_riavviare_non_rifa_nulla():
    esegui_migrazioni()
    esegui_migrazioni()
    assert versione_corrente() == ultima_migrazione()


def test_un_database_precedente_alle_migrazioni_si_marca_e_si_aggiorna():
    """Come l'ambiente di sviluppo di oggi: tabelle gia' presenti, nessuna alembic_version."""
    try:
        with engine.begin() as c:
            c.execute(sa.text("DROP SCHEMA public CASCADE"))
            c.execute(sa.text("CREATE SCHEMA public"))
        importa_modelli()
        Base.metadata.create_all(engine)
        with engine.begin() as c:
            c.execute(sa.text("ALTER TABLE users DROP COLUMN email_idx"))   # un database di allora non aveva ancora le impronte
            c.execute(sa.text("INSERT INTO users (id, email, full_name, hashed_password, role, is_external, origine_credenziali) VALUES (gen_random_uuid(), 'vecchio@test.it', 'Vecchio', 'x', 'admin_tecnico', false, 'locale')"))
        esegui_migrazioni()
        assert versione_corrente() == ultima_migrazione()
        with engine.connect() as c:
            assert c.execute(sa.text("SELECT count(*) FROM users WHERE email = 'vecchio@test.it'")).scalar() == 1   # i dati restano
    finally:
        ricrea_schema()


def test_la_migrazione_di_partenza_e_la_prima():
    with engine.connect() as c:
        radici = [s.revision for s in ScriptDirectory.from_config(_config(c)).walk_revisions() if s.down_revision is None]
    assert radici == [BASELINE]
