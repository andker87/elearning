"""video in piu' qualita'

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-16 12:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "altre_versioni_in_corso" not in {c["name"] for c in insp.get_columns("video_contenuti")}:
        op.add_column("video_contenuti", sa.Column("altre_versioni_in_corso", sa.Boolean(), nullable=False, server_default="false"))
    if not insp.has_table("video_versioni"):
        op.create_table(
            "video_versioni",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("video_contenuti.id"), nullable=False),
            sa.Column("altezza", sa.Integer(), nullable=False),
            sa.Column("larghezza", sa.Integer(), nullable=True),
            sa.Column("bitrate_kbps", sa.Integer(), nullable=True),
            sa.Column("dimensione_bytes", sa.BigInteger(), nullable=True),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("video_id", "altezza", name="uq_video_versione_altezza"),
        )
        op.create_index("ix_video_versioni_video_id", "video_versioni", ["video_id"])


def downgrade():
    op.drop_table("video_versioni")
    op.drop_column("video_contenuti", "altre_versioni_in_corso")
