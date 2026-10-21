"""questionari di gradimento personalizzabili

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-21 14:00:00

- questionari_gradimento / domande_gradimento: domande aggiuntive decise dalla Formazione (uno e' il predefinito);
- risposte_gradimento: le risposte, con il testo della domanda conservato;
- corsi.questionario_gradimento_id: il questionario scelto per il corso (vuoto = il predefinito).
Chi aggiorna non vede cambiare nulla: senza questionari il modulo resta quello di prima.
"""
from alembic import op
import sqlalchemy as sa


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("questionari_gradimento"):
        op.create_table(
            "questionari_gradimento",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("nome"),
        )
    if not insp.has_table("domande_gradimento"):
        op.create_table(
            "domande_gradimento",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("questionario_id", sa.UUID(), nullable=False),
            sa.Column("testo", sa.String(), nullable=False),
            sa.Column("tipo", sa.String(), nullable=False),
            sa.Column("opzioni", sa.JSON(), nullable=True),
            sa.Column("obbligatoria", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("ordine", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["questionario_id"], ["questionari_gradimento.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_domande_gradimento_questionario_id", "domande_gradimento", ["questionario_id"])
    if not insp.has_table("risposte_gradimento"):
        op.create_table(
            "risposte_gradimento",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("gradimento_id", sa.UUID(), nullable=False),
            sa.Column("domanda_id", sa.UUID(), nullable=True),
            sa.Column("testo_domanda", sa.String(), nullable=False),
            sa.Column("tipo", sa.String(), nullable=False),
            sa.Column("valore_num", sa.Integer(), nullable=True),
            sa.Column("valore_testo", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["gradimento_id"], ["gradimenti.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_risposte_gradimento_gradimento_id", "risposte_gradimento", ["gradimento_id"])
    if "questionario_gradimento_id" not in _colonne("corsi"):
        op.add_column("corsi", sa.Column("questionario_gradimento_id", sa.UUID(), nullable=True))
        op.create_foreign_key("fk_corsi_questionario_gradimento", "corsi", "questionari_gradimento", ["questionario_gradimento_id"], ["id"], ondelete="SET NULL")


def downgrade():
    if "questionario_gradimento_id" in _colonne("corsi"):
        op.drop_constraint("fk_corsi_questionario_gradimento", "corsi", type_="foreignkey")
        op.drop_column("corsi", "questionario_gradimento_id")
    for t in ("risposte_gradimento", "domande_gradimento", "questionari_gradimento"):
        if sa.inspect(op.get_bind()).has_table(t):
            op.drop_table(t)
