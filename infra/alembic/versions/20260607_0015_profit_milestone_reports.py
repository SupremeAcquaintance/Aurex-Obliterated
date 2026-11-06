"""Add first profit milestone reports.

Revision ID: 20260607_0015
Revises: 20260607_0014
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0015"
down_revision: str | None = "20260607_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_profit_milestone_reports",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=7), nullable=False),
        sa.Column("target_net_profit", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_net_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("first_trade_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_trade_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("journaled_trade_count", sa.Integer(), nullable=False),
        sa.Column("unjournaled_trade_count", sa.Integer(), nullable=False),
        sa.Column("journal_rule_violation_count", sa.Integer(), nullable=False),
        sa.Column("unexplained_trade_count", sa.Integer(), nullable=False),
        sa.Column("risk_rule_violation_count", sa.Integer(), nullable=False),
        sa.Column("daily_loss_breach_count", sa.Integer(), nullable=False),
        sa.Column("weekly_loss_breach_count", sa.Integer(), nullable=False),
        sa.Column("broker_statement_report_id", sa.String(length=36), nullable=True),
        sa.Column("broker_statement_status", sa.String(length=7), nullable=True),
        sa.Column("kill_switch_enabled", sa.Boolean(), nullable=False),
        sa.Column("live_execution_adapter_implemented", sa.Boolean(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("requirements_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["broker_statement_report_id"],
            ["live_broker_statement_reports.id"],
        ),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_profit_milestone_reports_broker_statement_report_id",
        "live_profit_milestone_reports",
        ["broker_statement_report_id"],
    )
    op.create_index(
        "ix_live_profit_milestone_reports_live_deployment_plan_id",
        "live_profit_milestone_reports",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_profit_milestone_reports_status",
        "live_profit_milestone_reports",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_profit_milestone_reports_status",
        table_name="live_profit_milestone_reports",
    )
    op.drop_index(
        "ix_live_profit_milestone_reports_live_deployment_plan_id",
        table_name="live_profit_milestone_reports",
    )
    op.drop_index(
        "ix_live_profit_milestone_reports_broker_statement_report_id",
        table_name="live_profit_milestone_reports",
    )
    op.drop_table("live_profit_milestone_reports")
