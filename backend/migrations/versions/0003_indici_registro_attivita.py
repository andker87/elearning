"""indici del registro attivita'

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15 20:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def _presente(nome):
    return nome in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("audit_log")}


def upgrade():
    if not _presente("ix_audit_log_created_at"):
        op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    if not _presente("ix_audit_log_action_created_at"):
        op.create_index("ix_audit_log_action_created_at", "audit_log", ["action", "created_at"])


def downgrade():
    op.drop_index("ix_audit_log_action_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
