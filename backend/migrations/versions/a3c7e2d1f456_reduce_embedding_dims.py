"""Reduce embedding vector dimension from 1536 to 384.

Revision ID: a3c7e2d1f456
Revises: fb894aaee630
Create Date: 2026-02-28
"""

from alembic import op
from pgvector.sqlalchemy import Vector

revision = "a3c7e2d1f456"
down_revision = "fb894aaee630"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clear existing embeddings (wrong dimensionality)
    op.execute("DELETE FROM code_embeddings")
    op.alter_column(
        "code_embeddings",
        "embedding",
        type_=Vector(384),
        existing_type=Vector(1536),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM code_embeddings")
    op.alter_column(
        "code_embeddings",
        "embedding",
        type_=Vector(1536),
        existing_type=Vector(384),
        existing_nullable=True,
    )
