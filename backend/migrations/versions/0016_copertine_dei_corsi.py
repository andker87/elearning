"""copertine dei corsi

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22 16:00:00

- corsi.copertina_path / copertina_v: l'immagine del corso (cifrata su disco) e un codice che cambia con l'immagine.
  I corsi che ci sono gia' restano senza copertina (la pagina ne mostra una generata).
"""
from alembic import op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    presenti = _colonne("corsi")
    if "copertina_path" not in presenti:
        op.add_column("corsi", sa.Column("copertina_path", sa.String(), nullable=True))
    if "copertina_v" not in presenti:
        op.add_column("corsi", sa.Column("copertina_v", sa.String(), nullable=True))


def downgrade():
    presenti = _colonne("corsi")
    for c in ("copertina_v", "copertina_path"):
        if c in presenti:
            op.drop_column("corsi", c)
