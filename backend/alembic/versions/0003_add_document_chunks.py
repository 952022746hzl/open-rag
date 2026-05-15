"""add document_chunks table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-15

"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.BigInteger(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_content", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("source_location", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index("idx_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("idx_chunks_document_id", "document_chunks")
    op.drop_table("document_chunks")
