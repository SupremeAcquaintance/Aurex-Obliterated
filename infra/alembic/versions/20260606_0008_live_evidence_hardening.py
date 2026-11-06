"""Add live approval and paper evidence records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0008"
down_revision: str | None = "20260606_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_approval_records",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("approval_type", sa.String(length=14), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("approver", sa.String(length=120), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_approval_records_approval_type",
        "live_approval_records",
        ["approval_type"],
    )
    op.create_index(
        "ix_live_approval_records_live_deployment_plan_id",
        "live_approval_records",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_approval_records_status",
        "live_approval_records",
        ["status"],
    )

    op.create_table(
        "live_paper_evidence_reports",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=7), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("expectancy", sa.Numeric(20, 8), nullable=False),
        sa.Column("profit_factor", sa.Numeric(12, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_net_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("requirements_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_paper_evidence_reports_live_deployment_plan_id",
        "live_paper_evidence_reports",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_paper_evidence_reports_status",
        "live_paper_evidence_reports",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_paper_evidence_reports_status",
        table_name="live_paper_evidence_reports",
    )
    op.drop_index(
        "ix_live_paper_evidence_reports_live_deployment_plan_id",
        table_name="live_paper_evidence_reports",
    )
    op.drop_table("live_paper_evidence_reports")
    op.drop_index("ix_live_approval_records_status", table_name="live_approval_records")
    op.drop_index(
        "ix_live_approval_records_live_deployment_plan_id",
        table_name="live_approval_records",
    )
    op.drop_index(
        "ix_live_approval_records_approval_type",
        table_name="live_approval_records",
    )
    op.drop_table("live_approval_records")
