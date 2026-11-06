"""Retain native warmup history without reseeding existing processing streams."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0031"
down_revision: str | None = "20260930_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_history_seeds",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stream_key", sa.String(64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream_key"),
    )


def downgrade() -> None:
    op.drop_table("native_history_seeds")
