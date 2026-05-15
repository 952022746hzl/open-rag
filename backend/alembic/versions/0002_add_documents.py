"""add documents table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15

"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        # object_key 允许 NULL：DB 记录先于 MinIO 上传创建，上传成功后回填
        sa.Column("object_key", sa.String(512), nullable=True),
        sa.Column("uploader_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.BigInteger(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="public"),
        sa.Column("tags", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("upload_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_documents_uploader_id", "documents", ["uploader_id"])
    op.create_index("idx_documents_department_id", "documents", ["department_id"])
    op.create_index("idx_documents_visibility", "documents", ["visibility"])
    op.create_index("idx_documents_file_type", "documents", ["file_type"])


def downgrade() -> None:
    op.drop_index("idx_documents_file_type", "documents")
    op.drop_index("idx_documents_visibility", "documents")
    op.drop_index("idx_documents_department_id", "documents")
    op.drop_index("idx_documents_uploader_id", "documents")
    op.drop_table("documents")
