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
            c.execute(sa.text("CREATE TYPE userrole AS ENUM ('admin_tecnico', 'training_admin', 'user')"))   # ne' i tre interruttori: c'era il ruolo
            c.execute(sa.text("ALTER TABLE users ADD COLUMN role userrole NOT NULL DEFAULT 'user', DROP COLUMN is_admin, DROP COLUMN is_formazione, DROP COLUMN is_formatore"))
            c.execute(sa.text("INSERT INTO users (id, email, full_name, hashed_password, role, is_external, origine_credenziali) VALUES (gen_random_uuid(), 'vecchio@test.it', 'Vecchio', 'x', 'admin_tecnico', false, 'locale')"))
        esegui_migrazioni()
        assert versione_corrente() == ultima_migrazione()
        with engine.connect() as c:
            assert c.execute(sa.text("SELECT count(*) FROM users WHERE email = 'vecchio@test.it'")).scalar() == 1   # i dati restano
            assert c.execute(sa.text("SELECT is_admin FROM users WHERE email = 'vecchio@test.it'")).scalar() is True   # il ruolo e' diventato un permesso
    finally:
        ricrea_schema()


def test_la_migrazione_di_partenza_e_la_prima():
    with engine.connect() as c:
        radici = [s.revision for s in ScriptDirectory.from_config(_config(c)).walk_revisions() if s.down_revision is None]
    assert radici == [BASELINE]


def test_0008_trasforma_ruoli_gruppi_e_mansioni_senza_perdere_dati(caplog):
    """Un database della 1.9.x / 2.0.x / 2.1.x: ruolo unico, gruppi di sistema, gruppi liberi, una persona in due uffici."""
    import logging
    from datetime import datetime, timezone
    import uuid
    from app.database import SessionLocal
    from app.models.corso import Corso
    from app.models.edizione import Edizione, EdizioneDocente, ModalitaErogazione, StatoEdizione
    from app.models.group import Group, UserGroup
    from app.models.percorso import PercorsoFormativo
    from app.models.user import User

    s = None
    try:
        ricrea_schema()
        with engine.begin() as c:   # allora una persona poteva stare in piu' uffici
            c.execute(sa.text("ALTER TABLE user_groups DROP CONSTRAINT uq_user_groups_user"))
        s = SessionLocal()
        def u(email, **kw):
            x = User(id=uuid.uuid4(), email=email, full_name=email, hashed_password="x", **kw); s.add(x); s.flush(); return x
        def g(nome, **kw):
            x = Group(name=nome, **kw); s.add(x); s.flush(); return x
        adm, form = u("adm@t.it", is_admin=True), u("form@t.it", is_formazione=True)
        docente, nelgruppo = u("doc@t.it"), u("fmt@t.it")
        doppio, semplice = u("doppio@t.it"), u("semplice@t.it")
        sist = {n: g(n, is_ufficio=False) for n in ("Admin", "Ufficio Formazione", "Formatori", "Utenti")}
        prod = g("Produzione", is_ufficio=True)
        linea = g("Linea 2", is_ufficio=True, parent_id=prod.id)
        antincendio = g("Antincendio", is_ufficio=False)
        s.add_all([UserGroup(user_id=adm.id, group_id=sist["Admin"].id), UserGroup(user_id=nelgruppo.id, group_id=sist["Formatori"].id),
                   UserGroup(user_id=semplice.id, group_id=prod.id),
                   UserGroup(user_id=doppio.id, group_id=prod.id), UserGroup(user_id=doppio.id, group_id=linea.id),
                   UserGroup(user_id=doppio.id, group_id=antincendio.id), UserGroup(user_id=form.id, group_id=antincendio.id)])
        p = PercorsoFormativo(nome="Corso fuoco", trigger_tipo="gruppo", trigger_gruppo_id=antincendio.id)
        corso = Corso(titolo="C"); s.add_all([p, corso]); s.flush()
        ed = Edizione(corso_id=corso.id, modalita=ModalitaErogazione.esterna, stato=StatoEdizione.chiusa, data_inizio=datetime.now(timezone.utc)); s.add(ed); s.flush()
        s.add(EdizioneDocente(edizione_id=ed.id, user_id=docente.id)); s.commit()
        ids = {k: v.id for k, v in dict(adm=adm, form=form, docente=docente, nelgruppo=nelgruppo, doppio=doppio, semplice=semplice, prod=prod, linea=linea, antincendio=antincendio, p=p).items()}
        s.close()

        # ... lo riporta alla forma di prima (0007)
        with engine.begin() as c:
            c.execute(sa.text("UPDATE alembic_version SET version_num = '0007'"))
            c.execute(sa.text("CREATE TYPE userrole AS ENUM ('admin_tecnico', 'training_admin', 'user')"))
            c.execute(sa.text("ALTER TABLE users ADD COLUMN role userrole NOT NULL DEFAULT 'user'"))
            c.execute(sa.text("UPDATE users SET role = 'admin_tecnico' WHERE is_admin"))
            c.execute(sa.text("UPDATE users SET role = 'training_admin' WHERE is_formazione"))
            c.execute(sa.text("ALTER TABLE users DROP COLUMN is_admin, DROP COLUMN is_formazione, DROP COLUMN is_formatore"))
            c.execute(sa.text("ALTER TABLE groups ADD COLUMN permissions json, ADD COLUMN is_system boolean"))
            c.execute(sa.text("UPDATE groups SET is_system = (name IN ('Admin', 'Ufficio Formazione', 'Formatori', 'Utenti'))"))
            c.execute(sa.text("UPDATE percorsi_formativi SET trigger_tipo = 'gruppo'"))
            c.execute(sa.text("ALTER TABLE percorsi_formativi DROP COLUMN trigger_mansione_id"))
            c.execute(sa.text("DROP TABLE user_mansioni"))
            c.execute(sa.text("DROP TABLE mansioni"))
            c.execute(sa.text("ALTER TYPE triggerassegnazione RENAME TO ta_nuovo"))
            c.execute(sa.text("CREATE TYPE triggerassegnazione AS ENUM ('manuale', 'ingresso_azienda', 'gruppo')"))
            c.execute(sa.text("ALTER TABLE percorsi_formativi ALTER COLUMN trigger_tipo TYPE triggerassegnazione USING trigger_tipo::text::triggerassegnazione"))
            c.execute(sa.text("DROP TYPE ta_nuovo"))
            # l'ordine di inserimento decide qual e' «il primo» ufficio di chi ne ha piu' d'uno
            c.execute(sa.text("UPDATE user_groups SET created_at = now() - interval '2 days' WHERE group_id = :g"), {"g": ids["prod"]})
            c.execute(sa.text("UPDATE user_groups SET created_at = now() - interval '1 day' WHERE group_id = :g"), {"g": ids["linea"]})

        with caplog.at_level(logging.WARNING):
            esegui_migrazioni()
        assert versione_corrente() == ultima_migrazione()
        def q(sql, **p):
            with engine.connect() as c:
                return c.execute(sa.text(sql), p).fetchall()

        flags = {r[0]: r[1:] for r in q("SELECT email, is_admin, is_formazione, is_formatore FROM users")}
        assert flags["adm@t.it"] == (True, False, False) and flags["form@t.it"] == (False, True, False)
        assert flags["doc@t.it"] == (False, False, True)        # docente di un'edizione => Formatore
        assert flags["fmt@t.it"] == (False, False, True)        # era nel gruppo Formatori => Formatore
        assert flags["semplice@t.it"] == (False, False, False)
        assert not q("SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'role'")
        assert not q("SELECT 1 FROM pg_type WHERE typname = 'userrole'")

        nomi = {r[0] for r in q("SELECT name FROM groups")}
        assert nomi == {"Produzione", "Linea 2"}                # via i quattro gruppi di sistema e il gruppo che non era un ufficio
        assert {r[0] for r in q("SELECT name FROM mansioni")} == {"Antincendio"}
        assert {r[0] for r in q("SELECT u.email FROM user_mansioni um JOIN users u ON u.id = um.user_id")} == {"doppio@t.it", "form@t.it"}
        pr = q("SELECT trigger_tipo::text, trigger_gruppo_id, trigger_mansione_id FROM percorsi_formativi")[0]
        assert pr[0] == "mansione" and pr[1] is None and pr[2] is not None     # il percorso ora segue la mansione

        uffici = {r[0]: r[1] for r in q("SELECT u.email, g.name FROM user_groups ug JOIN users u ON u.id = ug.user_id JOIN groups g ON g.id = ug.group_id")}
        assert uffici == {"doppio@t.it": "Produzione", "semplice@t.it": "Produzione"}   # chi era in due uffici resta nel primo
        assert any("piu' uffici" in r.getMessage() for r in caplog.records)             # e la migrazione lo dice
        assert q("SELECT count(*) FROM users")[0][0] == 6                                # nessuna persona persa
        assert q("SELECT is_ufficio FROM groups WHERE name = 'Linea 2'")[0][0] is True
        assert q("SELECT parent_id FROM groups WHERE name = 'Linea 2'")[0][0] == ids["prod"]       # l'albero degli uffici resta
    finally:
        if s is not None:
            s.close()
        ricrea_schema()
