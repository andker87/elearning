"""Fixture comuni. I test girano su un database separato (<nome>_test) creato
al volo: non toccano mai i dati reali. Se il nome non finisce per _test il
processo si ferma."""
import os
import uuid

import sqlalchemy as sa

_url = os.environ["DATABASE_URL"]
_base, _, _nome = _url.rpartition("/")
if not _nome.endswith("_test"):
    _nome += "_test"
os.environ["DATABASE_URL"] = f"{_base}/{_nome}"
assert os.environ["DATABASE_URL"].endswith("_test")

_admin = sa.create_engine(f"{_base}/postgres", isolation_level="AUTOCOMMIT")
with _admin.connect() as _c:
    if not _c.execute(sa.text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _nome}).first():
        _c.execute(sa.text(f'CREATE DATABASE "{_nome}"'))
_admin.dispose()

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app  # importa anche tutti i modelli
from app.models.user import User, UserRole
from app.services import rate_limit
import bcrypt
from app.services.auth import token_per_utente

PASSWORD = "Password!Valida123"


def ricrea_schema():
    """Database di prova vuoto, costruito dalle migrazioni vere (come un'installazione nuova)."""
    from app.migrazioni import esegui_migrazioni
    with engine.begin() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    esegui_migrazioni()


@pytest.fixture(scope="session", autouse=True)
def schema():
    ricrea_schema()
    yield


@pytest.fixture(autouse=True)
def pulizia(schema, monkeypatch):
    """Ogni test parte da database vuoto, senza SMTP/SSO e con i contatori azzerati."""
    tabelle = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE {tabelle} RESTART IDENTITY CASCADE"))
    rate_limit._eventi.clear()
    for nome in ("SMTP_HOST", "SMTP_MITTENTE", "SSO_ISSUER", "SSO_CLIENT_ID", "SSO_CLIENT_SECRET", "SSO_PUBLIC_URL",
                 "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"):
        monkeypatch.setattr(settings, nome, None)
    monkeypatch.setattr(settings, "SSO_PROVISIONA_UTENTI", False)

    class _Immediato:  # gli invii in sottofondo nei test girano subito, cosi' si possono verificare
        def submit(self, funzione, *args):
            funzione(*args)
    monkeypatch.setattr("app.services.email._esecutore", _Immediato())
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def crea_utente(db):
    def _crea(email=None, ruolo=UserRole.user, password=PASSWORD, **kw):
        u = User(id=uuid.uuid4(), email=email or f"u{uuid.uuid4().hex[:8]}@test.it", full_name=kw.pop("full_name", "Utente Test"),
                 hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode(),
                 role=ruolo, **kw)  # costo bcrypt basso: i test restano veloci
        db.add(u)
        db.commit()
        db.refresh(u)
        return u
    return _crea


@pytest.fixture
def auth():
    def _auth(utente):
        return {"Authorization": f"Bearer {token_per_utente(utente)}"}
    return _auth


@pytest.fixture
def admin(crea_utente):
    return crea_utente("admin@test.it", UserRole.admin_tecnico, full_name="Admin Test")


@pytest.fixture
def formazione(crea_utente):
    return crea_utente("formazione@test.it", UserRole.training_admin, full_name="Ufficio Formazione")


@pytest.fixture
def utente(crea_utente):
    return crea_utente("utente@test.it", full_name="Utente Normale")


# --- fabbriche di dati di dominio -------------------------------------------------------
from datetime import datetime, timedelta, timezone

from app.models.corso import Corso
from app.models.edizione import Edizione, ModalitaErogazione, StatoEdizione
from app.models.group import Group, UserGroup
from app.models.iscrizione import Iscrizione, StatoIscrizione
from app.models.percorso import PercorsoAssegnazione, PercorsoFormativo, PercorsoStep


def adesso():
    return datetime.now(timezone.utc)


@pytest.fixture
def crea_corso(db):
    def _crea(titolo="Corso Test", validita_mesi=None, **kw):
        c = Corso(titolo=titolo, validita_mesi=validita_mesi, **kw)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c
    return _crea


@pytest.fixture
def crea_edizione(db):
    def _crea(corso, stato=StatoEdizione.chiusa, **kw):
        e = Edizione(corso_id=corso.id, modalita=kw.pop("modalita", ModalitaErogazione.esterna), stato=stato,
                     data_inizio=kw.pop("data_inizio", adesso() + timedelta(days=7)), **kw)
        db.add(e)
        db.commit()
        db.refresh(e)
        return e
    return _crea


@pytest.fixture
def crea_iscrizione(db):
    def _crea(edizione, utente, stato=StatoIscrizione.iscritto, giorni_fa=None, versione=1):
        i = Iscrizione(edizione_id=edizione.id, user_id=utente.id, stato=stato, versione_corso=versione,
                       completato_at=(adesso() - timedelta(days=giorni_fa)) if giorni_fa is not None else None)
        db.add(i)
        db.commit()
        db.refresh(i)
        return i
    return _crea


@pytest.fixture
def crea_percorso(db):
    """Percorso attivo con i corsi indicati, assegnato alle persone indicate."""
    def _crea(corsi, persone, nome="Percorso Test"):
        p = PercorsoFormativo(nome=nome)
        db.add(p)
        db.flush()
        for n, c in enumerate(corsi, start=1):
            db.add(PercorsoStep(percorso_id=p.id, corso_id=c.id, ordine=n))
        for u in persone:
            db.add(PercorsoAssegnazione(percorso_id=p.id, user_id=u.id))
        db.commit()
        return p
    return _crea


@pytest.fixture
def crea_ufficio(db):
    def _crea(nome="Ufficio Test", membri=(), responsabile=None):
        g = Group(name=nome, is_ufficio=True, responsabile_id=responsabile.id if responsabile else None)
        db.add(g)
        db.flush()
        for u in membri:
            db.add(UserGroup(user_id=u.id, group_id=g.id))
        db.commit()
        db.refresh(g)
        return g
    return _crea


@pytest.fixture
def famiglie(db):
    """Le famiglie iniziali, come dopo la prima installazione."""
    from app.services.etichette import crea_famiglie_iniziali
    from app.models.etichetta import Etichetta, EtichettaFamiglia
    crea_famiglie_iniziali(db)

    def etichetta(famiglia, nome):
        return (db.query(Etichetta).join(EtichettaFamiglia, EtichettaFamiglia.id == Etichetta.famiglia_id)
                .filter(EtichettaFamiglia.nome == famiglia, Etichetta.nome == nome).one())
    return etichetta
