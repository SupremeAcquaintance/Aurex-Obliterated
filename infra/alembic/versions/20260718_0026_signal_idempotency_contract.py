"""Enforce one canonical signal per idempotency key.

Revision ID: 20260718_0026
Revises: 20260718_0025
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0026"
down_revision: str | None = "20260718_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            """
            SELECT idempotency_key, COUNT(*) AS duplicate_count
            FROM signals
            WHERE status <> 'DUPLICATE_REJECTED'
            GROUP BY idempotency_key
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).mappings().first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot enforce canonical signal idempotency while duplicate canonical "
            f"records exist for key {duplicate['idempotency_key']!r}"
        )

    op.create_index(
        "uq_signals_canonical_idempotency_key",
        "signals",
        ["idempotency_key"],
        unique=True,
        sqlite_where=sa.text("status <> 'DUPLICATE_REJECTED'"),
        postgresql_where=sa.text("status <> 'DUPLICATE_REJECTED'"),
    )


def downgrade() -> None:
    op.drop_index("uq_signals_canonical_idempotency_key", table_name="signals")
