"""Add evidence-grade paper execution assumptions.

Revision ID: 20260718_0029
Revises: 20260718_0028
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0029"
down_revision: str | None = "20260718_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_orders",
        sa.Column(
            "execution_assumptions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "paper_orders",
        sa.Column("execution_assumptions_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_paper_orders_execution_assumptions_hash",
        "paper_orders",
        ["execution_assumptions_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_orders_execution_assumptions_hash",
        table_name="paper_orders",
    )
    op.drop_column("paper_orders", "execution_assumptions_hash")
    op.drop_column("paper_orders", "execution_assumptions")
