"""Add analyst advisory notes

Revision ID: 20260606_0005
Revises: 20260606_0004
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0005"
down_revision: str | None = "20260606_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyst_notes",
        sa.Column("trade_id", sa.String(length=36), nullable=True),
        sa.Column("strategy", sa.String(length=100), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=True),
        sa.Column("note_type", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(12, 6), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("advisory_only", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["trade_id"], ["paper_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyst_notes_note_type", "analyst_notes", ["note_type"])
    op.create_index("ix_analyst_notes_severity", "analyst_notes", ["severity"])
    op.create_index("ix_analyst_notes_strategy", "analyst_notes", ["strategy"])
    op.create_index("ix_analyst_notes_symbol", "analyst_notes", ["symbol"])
    op.create_index("ix_analyst_notes_trade_id", "analyst_notes", ["trade_id"])


def downgrade() -> None:
    op.drop_index("ix_analyst_notes_trade_id", table_name="analyst_notes")
    op.drop_index("ix_analyst_notes_symbol", table_name="analyst_notes")
    op.drop_index("ix_analyst_notes_strategy", table_name="analyst_notes")
    op.drop_index("ix_analyst_notes_severity", table_name="analyst_notes")
    op.drop_index("ix_analyst_notes_note_type", table_name="analyst_notes")
    op.drop_table("analyst_notes")
