"""sessioni sempre aperte (video senza date, attestato automatico)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-21 09:00:00

- edizioni.sempre_aperta: una sessione video senza date che chiunque puo' seguire quando vuole; chi raggiunge la
  soglia di visione (e supera il test finale, se c'e') risulta completato e riceve l'attestato in automatico.
  Le sessioni che ci sono gia' restano come sono (false).
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    if "sempre_aperta" not in _colonne("edizioni"):
        op.add_column("edizioni", sa.Column("sempre_aperta", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    if "sempre_aperta" in _colonne("edizioni"):
        op.drop_column("edizioni", "sempre_aperta")
