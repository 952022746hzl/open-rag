"""add qa_sessions and qa_records tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-15

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_sessions",
        sa.Column("session_id", sa.String(50), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_sessions_user_id", "qa_sessions", ["user_id"])
    op.create_index("idx_sessions_last_active", "qa_sessions", ["last_active_at"])

    op.create_table(
        "qa_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(50),
            sa.ForeignKey("qa_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "turn_id"),
    )
    op.create_index("idx_records_session_id", "qa_records", ["session_id"])
    op.create_index(
        "idx_records_context_gin",
        "qa_records",
        ["context"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_records_context_gin", "qa_records")
    op.drop_index("idx_records_session_id", "qa_records")
    op.drop_table("qa_records")
    op.drop_index("idx_sessions_last_active", "qa_sessions")
    op.drop_index("idx_sessions_user_id", "qa_sessions")
    op.drop_table("qa_sessions")
