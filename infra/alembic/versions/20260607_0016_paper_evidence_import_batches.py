"""Add paper evidence import batches.

Revision ID: 20260607_0016
Revises: 20260607_0015
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0016"
down_revision: str | None = "20260607_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_evidence_import_batches",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("import_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rows_received", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("required_headers", sa.JSON(), nullable=False),
        sa.Column("row_results", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_evidence_import_batches_account_id",
        "paper_evidence_import_batches",
        ["account_id"],
    )
    op.create_index(
        "ix_paper_evidence_import_batches_import_hash",
        "paper_evidence_import_batches",
        ["import_hash"],
    )
    op.create_index(
        "ix_paper_evidence_import_batches_source",
        "paper_evidence_import_batches",
        ["source"],
    )
    op.create_index(
        "ix_paper_evidence_import_batches_status",
        "paper_evidence_import_batches",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_evidence_import_batches_status",
        table_name="paper_evidence_import_batches",
    )
    op.drop_index(
        "ix_paper_evidence_import_batches_source",
        table_name="paper_evidence_import_batches",
    )
    op.drop_index(
        "ix_paper_evidence_import_batches_import_hash",
        table_name="paper_evidence_import_batches",
    )
    op.drop_index(
        "ix_paper_evidence_import_batches_account_id",
        table_name="paper_evidence_import_batches",
    )
    op.drop_table("paper_evidence_import_batches")
