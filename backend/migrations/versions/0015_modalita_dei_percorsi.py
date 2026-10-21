"""modalita' dei percorsi formativi (libero / sequenziale / con propedeuticita')

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-21 10:00:00

- percorsi_formativi.modalita: i percorsi che hanno gia' dei prerequisiti diventano «con propedeuticita'» (si comportano
  come prima); gli altri «libero».
"""
from alembic import op
import sqlalchemy as sa


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    if "modalita" not in _colonne("percorsi_formativi"):
        op.add_column("percorsi_formativi", sa.Column("modalita", sa.String(), nullable=False, server_default="libero"))
        op.get_bind().execute(sa.text(
            "UPDATE percorsi_formativi SET modalita = 'propedeuticita' WHERE id IN ("
            " SELECT DISTINCT s.percorso_id FROM percorso_steps s JOIN percorso_step_prerequisiti r ON r.step_id = s.id)"))


def downgrade():
    if "modalita" in _colonne("percorsi_formativi"):
        op.drop_column("percorsi_formativi", "modalita")
