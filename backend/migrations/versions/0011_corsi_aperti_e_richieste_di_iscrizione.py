"""corsi chiusi o aperti ai responsabili, richieste di iscrizione

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-20 15:00:00

- corsi.iscrizione_responsabili: chi puo' iscrivere (solo la Formazione, i responsabili direttamente, i responsabili su richiesta).
  I corsi che ci sono gia' restano «diretta» (oggi un responsabile puo' gia' iscrivere le sue persone): cambia solo il
  predefinito dei corsi nuovi, che sono «chiusi»;
- tabella delle richieste di iscrizione dei responsabili.
"""
from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    conn = op.get_bind()
    if "iscrizione_responsabili" not in _colonne("corsi"):
        op.add_column("corsi", sa.Column("iscrizione_responsabili", sa.String(), nullable=False, server_default="solo_formazione"))
        conn.execute(sa.text("UPDATE corsi SET iscrizione_responsabili = 'diretta'"))     # chi c'era prima: comportamento invariato
    if not sa.inspect(conn).has_table("richieste_iscrizione"):
        op.create_table(
            "richieste_iscrizione",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("edizione_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("richiedente_id", sa.UUID(), nullable=False),
            sa.Column("stato", sa.String(), nullable=False, server_default="in_attesa"),
            sa.Column("motivo_rifiuto", sa.Text(), nullable=True),
            sa.Column("valutata_da_id", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("valutata_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["edizione_id"], ["edizioni.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["richiedente_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["valutata_da_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    indici = {i["name"] for i in sa.inspect(conn).get_indexes("richieste_iscrizione")}
    if "uq_richiesta_iscrizione_in_attesa" not in indici:
        op.create_index("uq_richiesta_iscrizione_in_attesa", "richieste_iscrizione", ["edizione_id", "user_id"], unique=True,
                        postgresql_where=sa.text("stato = 'in_attesa'"))


def downgrade():
    raise RuntimeError("Migrazione non reversibile. Ripristina una copia del database.")
