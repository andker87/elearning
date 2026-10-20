"""auto-iscrizione con approvazione della Formazione

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-21 02:00:00

- corsi.richiedi_approvazione_formazione: chi si iscrive da solo a un corso puo' avere l'iscrizione approvata dalla Formazione
  (oltre a «liberamente» e «approva il responsabile»). I corsi che ci sono gia' restano come sono.
"""
from alembic import op
import sqlalchemy as sa


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    if "richiedi_approvazione_formazione" not in _colonne("corsi"):
        op.add_column("corsi", sa.Column("richiedi_approvazione_formazione", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    if "richiedi_approvazione_formazione" in _colonne("corsi"):
        op.drop_column("corsi", "richiedi_approvazione_formazione")
