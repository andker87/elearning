"""Migrazioni dello schema all'avvio.

- database vuoto: si costruisce con le migrazioni, dalla 0001 all'ultima;
- database nato prima delle migrazioni (ha le tabelle ma non `alembic_version`): lo si porta
  all'ultimo stato di allora (schema_legacy) e lo si marca alla 0001, poi si applicano le
  migrazioni successive;
- database gia' sotto Alembic: si applicano quelle mancanti.
Tutto sotto un blocco del database (advisory lock): se partono due processi insieme il
secondo aspetta il primo e poi non trova nulla da fare."""
import importlib
import os
import pkgutil

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from .database import engine

BASELINE = "0001"
CHIAVE_BLOCCO = 7_302_026_001


def importa_modelli():
    """Carica tutti i modelli, cosi' Base.metadata li conosce (Alembic li confronta con il database)."""
    from . import models
    for m in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"{models.__name__}.{m.name}")


def _config(connessione) -> Config:
    radice = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(radice, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(radice, "migrations"))
    cfg.attributes["connection"] = connessione
    return cfg


def esegui_migrazioni():
    importa_modelli()
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": CHIAVE_BLOCCO})
        conn.commit()
        try:
            tabelle = set(inspect(conn).get_table_names())
            cfg = _config(conn)
            if "alembic_version" not in tabelle and "users" in tabelle:
                print("[migrazioni] database precedente alle migrazioni: lo porto allo stato di partenza e lo marco 0001")
                conn.commit()
                from .schema_legacy import porta_a_baseline
                porta_a_baseline(engine)
                command.stamp(cfg, BASELINE)
            command.upgrade(cfg, "head")
            conn.commit()
            print("[migrazioni] schema aggiornato")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": CHIAVE_BLOCCO})
            conn.commit()
