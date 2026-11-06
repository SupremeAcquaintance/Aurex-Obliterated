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
    S2BigQueryFeasibilityAudit,
    S2BigQueryFeasibilityProtocol,
    S2BigQueryFeasibilityProtocolAudit,
    S2BigQueryFeasibilityResult,
    S2DryRunSpec,
    S2FeasibilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (  # noqa: E402
    S2AuthenticatedMetadataEndpointSpec,
    S2BigQueryFeasibilityProtocolV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_protocol_v2.json")
V1_PROTOCOL_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_v1.json")
V1_PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v1.json")
V1_RESULT_PATH = Path("data/evidence/s2_bigquery_feasibility_result_v1.json")
V1_RESULT_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_audit_v1.json")
CHARTER_PATH = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
CHARTER_AUDIT_PATH = Path("data/evidence/s2_onchain_settlement_charter_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_feasibility_v2.py")


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


def load_v1_lineage():
    protocol = S2BigQueryFeasibilityProtocol.model_validate_json(V1_PROTOCOL_PATH.read_text())
    protocol_audit = S2BigQueryFeasibilityProtocolAudit.model_validate_json(
        V1_PROTOCOL_AUDIT_PATH.read_text()
    )
    result = S2BigQueryFeasibilityResult.model_validate_json(V1_RESULT_PATH.read_text())
    result_audit = S2BigQueryFeasibilityAudit.model_validate_json(V1_RESULT_AUDIT_PATH.read_text())
    if (
        protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != result.protocol_evidence_hash
        or result.result_evidence_hash != result_audit.result_evidence_hash
        or result_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
    ):
        raise ValueError("S2 BigQuery v1 lineage did not reconcile")
    return protocol, protocol_audit, result, result_audit


def build_protocol(*, frozen_at: datetime) -> S2BigQueryFeasibilityProtocolV2:
    protocol_v1, protocol_audit_v1, result_v1, result_audit_v1 = load_v1_lineage()
    source_paths = (
        CHARTER_AUDIT_PATH,
        CHARTER_PATH,
        V1_RESULT_AUDIT_PATH,
        V1_PROTOCOL_AUDIT_PATH,
        V1_PROTOCOL_PATH,
        V1_RESULT_PATH,
    )
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": protocol_v1.charter_evidence_hash,
        "prior_protocol_evidence_hash": protocol_v1.protocol_evidence_hash,
        "prior_protocol_audit_evidence_hash": protocol_audit_v1.audit_evidence_hash,
        "prior_result_evidence_hash": result_v1.result_evidence_hash,
        "prior_result_audit_evidence_hash": result_audit_v1.audit_evidence_hash,
        "source_bindings": tuple(
            S2FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
            for path in sorted(source_paths, key=lambda item: item.as_posix())
        ),
        "metadata_endpoints": (
            S2AuthenticatedMetadataEndpointSpec(
                target_id="BLOCKS_TABLE",
                url=(
                    "https://bigquery.googleapis.com/bigquery/v2/projects/"
                    "bigquery-public-data/datasets/crypto_bitcoin/tables/blocks"
                ),
                expected_reference="bigquery-public-data:crypto_bitcoin.blocks",
            ),
            S2AuthenticatedMetadataEndpointSpec(
                target_id="DATASET",
                url=(
                    "https://bigquery.googleapis.com/bigquery/v2/projects/"
                    "bigquery-public-data/datasets/crypto_bitcoin"
                ),
                expected_reference="bigquery-public-data:crypto_bitcoin",
            ),
            S2AuthenticatedMetadataEndpointSpec(
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
                    "A feasibility pass cannot establish predictive edge.",
                    "Authenticated metadata can change after this check.",
                    "Dry-run byte estimates can differ from later processed bytes.",
                    "No account, project, credential, or token identifier may enter evidence.",
                    "No numeric query may run without a separately frozen payload protocol.",
                    "The no-billing boundary must be verified before metadata or dry-runs.",
                    "This stage returns no blockchain rows, market values, or outcomes.",
                )
            )
        ),
    }
    return build_hashed(
        S2BigQueryFeasibilityProtocolV2,
        "protocol_evidence_hash",
        values,
    )


def write_protocol(path: Path, protocol: S2BigQueryFeasibilityProtocolV2) -> None:
    if path.exists():
        raise ValueError(f"S2 BigQuery feasibility protocol v2 exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2BigQueryFeasibilityProtocolV2.model_validate_json(serialized) != protocol:
        raise ValueError("S2 BigQuery feasibility protocol v2 did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 BigQuery preflight v2.")
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
            "requests=0 identifiers=0 values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
