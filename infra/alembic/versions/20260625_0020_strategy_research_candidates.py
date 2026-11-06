"""Add strategy research candidate intake ledger.

Revision ID: 20260625_0020
Revises: 20260625_0019
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0020"
down_revision: str | None = "20260625_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "strategy_research_candidates",
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("candidate_key", sa.String(length=128), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trade_eligible", sa.Boolean(), nullable=False),
        sa.Column("eligibility_reason", sa.Text(), nullable=False),
        sa.Column("required_evidence", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_research_candidates_source_key",
        "strategy_research_candidates",
        ["source", "candidate_key"],
        unique=True,
    )
    op.create_index(
        "ix_strategy_research_candidates_source",
        "strategy_research_candidates",
        ["source"],
    )
    op.create_index(
        "ix_strategy_research_candidates_candidate_key",
        "strategy_research_candidates",
        ["candidate_key"],
    )
    op.create_index(
        "ix_strategy_research_candidates_strategy",
        "strategy_research_candidates",
        ["strategy"],
    )
    op.create_index(
        "ix_strategy_research_candidates_status",
        "strategy_research_candidates",
        ["status"],
    )
    op.create_index(
        "ix_strategy_research_candidates_evidence_hash",
        "strategy_research_candidates",
        ["evidence_hash"],
    )

    op.create_table(
        "strategy_research_observations",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("observation_type", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", sa.String(length=160), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=True),
        sa.Column("contract_ticker", sa.String(length=160), nullable=True),
        sa.Column("side", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Numeric(12, 6), nullable=True),
        sa.Column("implied_probability", sa.Numeric(12, 6), nullable=True),
        sa.Column("expected_edge", sa.Numeric(12, 6), nullable=True),
        sa.Column("observation_snapshot", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_snapshot", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["candidate_id"], ["strategy_research_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_research_observations_candidate_id",
        "strategy_research_observations",
        ["candidate_id"],
    )
    op.create_index(
        "ix_strategy_research_observations_observation_type",
        "strategy_research_observations",
        ["observation_type"],
    )
    op.create_index(
        "ix_strategy_research_observations_source_event_id",
        "strategy_research_observations",
        ["source_event_id"],
    )
    op.create_index(
        "ix_strategy_research_observations_symbol",
        "strategy_research_observations",
        ["symbol"],
    )
    op.create_index(
        "ix_strategy_research_observations_contract_ticker",
        "strategy_research_observations",
        ["contract_ticker"],
    )
    op.create_index(
        "ix_strategy_research_observations_side",
        "strategy_research_observations",
        ["side"],
    )
    op.create_index(
        "ix_strategy_research_observations_evidence_hash",
        "strategy_research_observations",
        ["evidence_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_research_observations_evidence_hash",
        table_name="strategy_research_observations",
    )
    op.drop_index(
        "ix_strategy_research_observations_side",
        table_name="strategy_research_observations",
    )
    op.drop_index(
        "ix_strategy_research_observations_contract_ticker",
        table_name="strategy_research_observations",
    )
    op.drop_index(
        "ix_strategy_research_observations_symbol",
        table_name="strategy_research_observations",
    )
    op.drop_index(
        "ix_strategy_research_observations_source_event_id",
        table_name="strategy_research_observations",
    )
    op.drop_index(
        "ix_strategy_research_observations_observation_type",
        table_name="strategy_research_observations",
    )
    op.drop_index(
        "ix_strategy_research_observations_candidate_id",
        table_name="strategy_research_observations",
    )
    op.drop_table("strategy_research_observations")

    op.drop_index(
        "ix_strategy_research_candidates_evidence_hash",
        table_name="strategy_research_candidates",
    )
    op.drop_index(
        "ix_strategy_research_candidates_status",
        table_name="strategy_research_candidates",
    )
    op.drop_index(
        "ix_strategy_research_candidates_strategy",
        table_name="strategy_research_candidates",
    )
    op.drop_index(
        "ix_strategy_research_candidates_candidate_key",
        table_name="strategy_research_candidates",
    )
    op.drop_index(
        "ix_strategy_research_candidates_source",
        table_name="strategy_research_candidates",
    )
    op.drop_index(
        "ix_strategy_research_candidates_source_key",
        table_name="strategy_research_candidates",
    )
    op.drop_table("strategy_research_candidates")
