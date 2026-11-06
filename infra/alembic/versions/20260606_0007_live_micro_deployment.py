"""Add live micro-deployment control tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0007"
down_revision: str | None = "20260606_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_deployment_plans",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("broker_connection_id", sa.String(length=36), nullable=True),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=18), nullable=False),
        sa.Column("risk_per_trade", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_daily_loss", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_weekly_loss", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_open_positions", sa.Integer(), nullable=False),
        sa.Column("target_net_profit", sa.Numeric(20, 8), nullable=False),
        sa.Column("live_trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("approval_snapshot", sa.JSON(), nullable=False),
        sa.Column("rules_snapshot", sa.JSON(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("halted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_live_deployment_plans_account_id",
        "live_deployment_plans",
        ["account_id"],
    )
    op.create_index(
        "ix_live_deployment_plans_broker_connection_id",
        "live_deployment_plans",
        ["broker_connection_id"],
    )
    op.create_index("ix_live_deployment_plans_name", "live_deployment_plans", ["name"])
    op.create_index(
        "ix_live_deployment_plans_status",
        "live_deployment_plans",
        ["status"],
    )
    op.create_index(
        "ix_live_deployment_plans_strategy",
        "live_deployment_plans",
        ["strategy"],
    )

    op.create_table(
        "live_deployment_gates",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("gate_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=7), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_deployment_gates_gate_key",
        "live_deployment_gates",
        ["gate_key"],
    )
    op.create_index(
        "ix_live_deployment_gates_live_deployment_plan_id",
        "live_deployment_gates",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_deployment_gates_plan_key",
        "live_deployment_gates",
        ["live_deployment_plan_id", "gate_key"],
        unique=True,
    )
    op.create_index(
        "ix_live_deployment_gates_status",
        "live_deployment_gates",
        ["status"],
    )

    op.create_table(
        "live_daily_review_reports",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("realized_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("rule_violations", sa.JSON(), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=11), nullable=False),
        sa.Column("review_snapshot", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_daily_review_reports_live_deployment_plan_id",
        "live_daily_review_reports",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_daily_review_reports_plan_date",
        "live_daily_review_reports",
        ["live_deployment_plan_id", "review_date"],
        unique=True,
    )
    op.create_index(
        "ix_live_daily_review_reports_reconciliation_status",
        "live_daily_review_reports",
        ["reconciliation_status"],
    )
    op.create_index(
        "ix_live_daily_review_reports_review_date",
        "live_daily_review_reports",
        ["review_date"],
    )
    op.create_index(
        "ix_live_daily_review_reports_status",
        "live_daily_review_reports",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_live_daily_review_reports_status", table_name="live_daily_review_reports")
    op.drop_index(
        "ix_live_daily_review_reports_review_date",
        table_name="live_daily_review_reports",
    )
    op.drop_index(
        "ix_live_daily_review_reports_reconciliation_status",
        table_name="live_daily_review_reports",
    )
    op.drop_index(
        "ix_live_daily_review_reports_plan_date",
        table_name="live_daily_review_reports",
    )
    op.drop_index(
        "ix_live_daily_review_reports_live_deployment_plan_id",
        table_name="live_daily_review_reports",
    )
    op.drop_table("live_daily_review_reports")
    op.drop_index("ix_live_deployment_gates_status", table_name="live_deployment_gates")
    op.drop_index("ix_live_deployment_gates_plan_key", table_name="live_deployment_gates")
    op.drop_index(
        "ix_live_deployment_gates_live_deployment_plan_id",
        table_name="live_deployment_gates",
    )
    op.drop_index("ix_live_deployment_gates_gate_key", table_name="live_deployment_gates")
    op.drop_table("live_deployment_gates")
    op.drop_index("ix_live_deployment_plans_strategy", table_name="live_deployment_plans")
    op.drop_index("ix_live_deployment_plans_status", table_name="live_deployment_plans")
    op.drop_index("ix_live_deployment_plans_name", table_name="live_deployment_plans")
    op.drop_index(
        "ix_live_deployment_plans_broker_connection_id",
        table_name="live_deployment_plans",
    )
    op.drop_index("ix_live_deployment_plans_account_id", table_name="live_deployment_plans")
    op.drop_table("live_deployment_plans")
