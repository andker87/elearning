from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.database import Base
from app.migrazioni import importa_modelli

importa_modelli()
target_metadata = Base.metadata


def run_migrations_online():
    # Se l'avvio ha gia' aperto una connessione (con il blocco che impedisce due migrazioni insieme) si usa quella.
    connessione = context.config.attributes.get("connection")
    if connessione is not None:
        context.configure(connection=connessione, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
