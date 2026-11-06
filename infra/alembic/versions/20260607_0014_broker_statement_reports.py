"""Add broker statement reconciliation reports.

Revision ID: 20260607_0014
Revises: 20260607_0013
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0014"
down_revision: str | None = "20260607_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_broker_statement_reports",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=7), nullable=False),
        sa.Column("statement_reference", sa.Text(), nullable=False),
        sa.Column("statement_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("statement_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("broker_trade_count", sa.Integer(), nullable=False),
        sa.Column("aurex_trade_count", sa.Integer(), nullable=False),
        sa.Column("broker_net_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("aurex_net_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("broker_fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("aurex_fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("broker_slippage", sa.Numeric(20, 8), nullable=False),
        sa.Column("aurex_slippage", sa.Numeric(20, 8), nullable=False),
        sa.Column("discrepancies", sa.JSON(), nullable=False),
        sa.Column("statement_snapshot", sa.JSON(), nullable=False),
        sa.Column("aurex_snapshot", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_broker_statement_reports_live_deployment_plan_id",
        "live_broker_statement_reports",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_broker_statement_reports_status",
        "live_broker_statement_reports",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_broker_statement_reports_status",
        table_name="live_broker_statement_reports",
    )
    op.drop_index(
        "ix_live_broker_statement_reports_live_deployment_plan_id",
        table_name="live_broker_statement_reports",
    )
    op.drop_table("live_broker_statement_reports")
