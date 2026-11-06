"""Add strategy evidence reviews.

Revision ID: 20260607_0017
Revises: 20260607_0016
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0017"
down_revision: str | None = "20260607_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_evidence_reviews",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=12), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("next_actions", sa.JSON(), nullable=False),
        sa.Column("gate_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_evidence_reviews_decision",
        "strategy_evidence_reviews",
        ["decision"],
    )
    op.create_index(
        "ix_strategy_evidence_reviews_live_deployment_plan_id",
        "strategy_evidence_reviews",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_strategy_evidence_reviews_strategy",
        "strategy_evidence_reviews",
        ["strategy"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_evidence_reviews_strategy",
        table_name="strategy_evidence_reviews",
    )
    op.drop_index(
        "ix_strategy_evidence_reviews_live_deployment_plan_id",
        table_name="strategy_evidence_reviews",
    )
    op.drop_index(
        "ix_strategy_evidence_reviews_decision",
        table_name="strategy_evidence_reviews",
    )
    op.drop_table("strategy_evidence_reviews")
