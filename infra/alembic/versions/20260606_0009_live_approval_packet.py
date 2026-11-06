"""Add live approval packet records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0009"
down_revision: str | None = "20260606_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_approval_packets",
        sa.Column("live_deployment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("broker_connection_id", sa.String(length=36), nullable=True),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("broker_name", sa.String(length=120), nullable=False),
        sa.Column("account_label", sa.String(length=120), nullable=False),
        sa.Column("account_type", sa.String(length=80), nullable=False),
        sa.Column("asset_class", sa.String(length=80), nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("broker_terms_reference", sa.Text(), nullable=True),
        sa.Column("fee_schedule_reference", sa.Text(), nullable=True),
        sa.Column("margin_policy_reference", sa.Text(), nullable=True),
        sa.Column("tax_notes", sa.Text(), nullable=True),
        sa.Column("credentials_stored", sa.Boolean(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["live_deployment_plan_id"], ["live_deployment_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_approval_packets_account_id",
        "live_approval_packets",
        ["account_id"],
    )
    op.create_index(
        "ix_live_approval_packets_broker_connection_id",
        "live_approval_packets",
        ["broker_connection_id"],
    )
    op.create_index(
        "ix_live_approval_packets_live_deployment_plan_id",
        "live_approval_packets",
        ["live_deployment_plan_id"],
    )
    op.create_index(
        "ix_live_approval_packets_status",
        "live_approval_packets",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_live_approval_packets_status", table_name="live_approval_packets")
    op.drop_index(
        "ix_live_approval_packets_live_deployment_plan_id",
        table_name="live_approval_packets",
    )
    op.drop_index(
        "ix_live_approval_packets_broker_connection_id",
        table_name="live_approval_packets",
    )
    op.drop_index("ix_live_approval_packets_account_id", table_name="live_approval_packets")
    op.drop_table("live_approval_packets")
