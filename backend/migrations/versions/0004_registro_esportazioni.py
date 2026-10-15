"""giorni del registro gia' esportati

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15 21:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("audit_esportazioni"):
        op.create_table(
            "audit_esportazioni",
            sa.Column("giorno", sa.Date(), primary_key=True),
            sa.Column("righe", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("esportato_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table("audit_esportazioni")
