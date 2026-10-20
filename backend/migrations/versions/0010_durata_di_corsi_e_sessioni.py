"""durata di corsi e sessioni

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-20 10:00:00

- corsi.durata_minuti: quanto dura il corso;
- edizioni.durata_minuti: durata propria della sessione (vuota = segue il corso; alla chiusura si congela);
- il vecchio campo «ore dichiarate» (solo sessioni esterne) diventa la stessa durata: ore x 60 minuti, poi la colonna sparisce.
"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    conn = op.get_bind()
    if "durata_minuti" not in _colonne("corsi"):
        op.add_column("corsi", sa.Column("durata_minuti", sa.Integer(), nullable=True))
    if "durata_minuti" not in _colonne("edizioni"):
        op.add_column("edizioni", sa.Column("durata_minuti", sa.Integer(), nullable=True))
    if "ore_dichiarate" in _colonne("edizioni"):
        conn.execute(sa.text("UPDATE edizioni SET durata_minuti = ore_dichiarate * 60 WHERE ore_dichiarate IS NOT NULL AND durata_minuti IS NULL"))
        op.drop_column("edizioni", "ore_dichiarate")


def downgrade():
    raise RuntimeError("Migrazione non reversibile: ore dichiarate e durate sono state unificate. Ripristina una copia del database.")
