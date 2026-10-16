"""cifratura: verifica della chiave e token del calendario conservato solo come impronta

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def upgrade():
    if "cifratura_verifica" not in _colonne("azienda"):
        op.add_column("azienda", sa.Column("cifratura_verifica", sa.Text(), nullable=True))
    colonne = _colonne("users")
    if "calendar_token_hash" not in colonne:
        op.add_column("users", sa.Column("calendar_token_hash", sa.String(), nullable=True))
        op.create_unique_constraint("users_calendar_token_hash_key", "users", ["calendar_token_hash"])
    if "calendar_token" in colonne:
        # I link gia' consegnati continuano a funzionare: si conserva l'impronta, non il token.
        op.execute("UPDATE users SET calendar_token_hash = encode(sha256(convert_to(calendar_token, 'UTF8')), 'hex') "
                   "WHERE calendar_token IS NOT NULL AND calendar_token_hash IS NULL")
        op.execute("DROP INDEX IF EXISTS ix_users_calendar_token")
        op.drop_column("users", "calendar_token")


def downgrade():
    # Il token in chiaro non e' recuperabile: chi torna indietro dovra' rigenerare i link del calendario.
    op.add_column("users", sa.Column("calendar_token", sa.String(), nullable=True))
    op.drop_constraint("users_calendar_token_hash_key", "users", type_="unique")
    op.drop_column("users", "calendar_token_hash")
    op.drop_column("azienda", "cifratura_verifica")
