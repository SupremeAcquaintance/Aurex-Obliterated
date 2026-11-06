from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import (  # noqa: E402
    S2BigQueryFeasibilityProtocol,
    S2DryRunSpec,
    S2FeasibilityBinding,
    S2MetadataEndpointSpec,
    build_hashed,
)
from aurex.backtest_engine.s2_onchain_settlement_charter import (  # noqa: E402
    S2OnchainSettlementCharter,
    S2OnchainSettlementCharterAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_protocol_v1.json")
CHARTER_PATH = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
CHARTER_AUDIT_PATH = Path(
    "data/evidence/s2_onchain_settlement_charter_audit_v1.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_feasibility.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "builder_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "builder_sha256": file_sha256(Path(__file__)),
        }
    )


def queries() -> tuple[S2DryRunSpec, ...]:
    causal = """WITH confirmed_cutoff AS (
  SELECT MAX(number) - 6 AS maximum_confirmed_block
  FROM `bigquery-public-data.crypto_bitcoin.blocks`
  WHERE timestamp < TIMESTAMP('2023-01-01T00:00:00Z')
)
SELECT
  DATE_TRUNC(DATE(t.block_timestamp), WEEK(MONDAY)) AS week_start,
  COUNTIF(NOT t.is_coinbase) AS confirmed_non_coinbase_transaction_count,
  SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS confirmed_fee_satoshis
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
CROSS JOIN confirmed_cutoff AS c
WHERE t.block_timestamp >= TIMESTAMP('2017-08-17T00:00:00Z')
  AND t.block_timestamp < TIMESTAMP('2023-01-01T00:00:00Z')
  AND t.block_number <= c.maximum_confirmed_block
GROUP BY week_start
ORDER BY week_start
"""
    development = """SELECT
  DATE_TRUNC(DATE(block_timestamp), WEEK(MONDAY)) AS week_start,
  COUNTIF(NOT is_coinbase) AS non_coinbase_transaction_count,
  SUM(IF(NOT is_coinbase, fee, 0)) AS fee_satoshis
FROM `bigquery-public-data.crypto_bitcoin.transactions`
WHERE block_timestamp >= TIMESTAMP('2017-08-17T00:00:00Z')
  AND block_timestamp < TIMESTAMP('2023-01-01T00:00:00Z')
GROUP BY week_start
ORDER BY week_start
"""
    return (
        S2DryRunSpec(
            query_id="CAUSAL_SIX_CONFIRMATION",
            google_sql=causal,
            query_sha256=sha256(causal.encode("utf-8")).hexdigest(),
        ),
        S2DryRunSpec(
            query_id="DEVELOPMENT_WEEKLY_AGGREGATE",
            google_sql=development,
            query_sha256=sha256(development.encode("utf-8")).hexdigest(),
        ),
    )


def build_protocol(*, frozen_at: datetime) -> S2BigQueryFeasibilityProtocol:
    charter = S2OnchainSettlementCharter.model_validate_json(CHARTER_PATH.read_text())
    charter_audit = S2OnchainSettlementCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text()
    )
    if charter.charter_evidence_hash != charter_audit.charter_evidence_hash:
        raise ValueError("S2 charter and audit do not reconcile")
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "source_bindings": (
            S2FeasibilityBinding(
                path=CHARTER_AUDIT_PATH.as_posix(),
                file_sha256=file_sha256(CHARTER_AUDIT_PATH),
            ),
            S2FeasibilityBinding(
                path=CHARTER_PATH.as_posix(),
                file_sha256=file_sha256(CHARTER_PATH),
            ),
        ),
        "metadata_endpoints": (
            S2MetadataEndpointSpec(
                target_id="BLOCKS_TABLE",
                url=(
                    "https://bigquery.googleapis.com/bigquery/v2/projects/"
                    "bigquery-public-data/datasets/crypto_bitcoin/tables/blocks"
                ),
                expected_reference="bigquery-public-data:crypto_bitcoin.blocks",
            ),
            S2MetadataEndpointSpec(
                target_id="DATASET",
                url=(
                    "https://bigquery.googleapis.com/bigquery/v2/projects/"
                    "bigquery-public-data/datasets/crypto_bitcoin"
                ),
                expected_reference="bigquery-public-data:crypto_bitcoin",
            ),
            S2MetadataEndpointSpec(
                target_id="TRANSACTIONS_TABLE",
                url=(
                    "https://bigquery.googleapis.com/bigquery/v2/projects/"
                    "bigquery-public-data/datasets/crypto_bitcoin/tables/transactions"
                ),
                expected_reference="bigquery-public-data:crypto_bitcoin.transactions",
            ),
        ),
        "dry_run_specs": queries(),
        "limitations": tuple(
            sorted(
                (
                    "A metadata or dry-run pass cannot establish predictive edge.",
                    "BigQuery table availability and schema can change after this check.",
                    "Dry-run byte estimates can differ from billed bytes at execution time.",
                    "No numeric query may run without a separately frozen payload protocol.",
                    "The zero-dollar boundary requires a sandbox project without billing.",
                    "This stage returns no blockchain rows, market values, or strategy outcomes.",
                )
            )
        ),
    }
    return build_hashed(
        S2BigQueryFeasibilityProtocol,
        "protocol_evidence_hash",
        values,
    )


def write_protocol(path: Path, protocol: S2BigQueryFeasibilityProtocol) -> None:
    if path.exists():
        raise ValueError(f"S2 BigQuery feasibility protocol exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2BigQueryFeasibilityProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S2 BigQuery feasibility protocol did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze the S2 BigQuery preflight.")
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "requests=0 values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
