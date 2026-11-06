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
    S2FeasibilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (  # noqa: E402
    S2_FEASIBILITY_V3_NEXT,
    S2_FEASIBILITY_V3_PASS,
    S2BigQueryFeasibilityAuditV3,
    S2BigQueryFeasibilityProtocolAuditV3,
    S2BigQueryFeasibilityProtocolV3,
    S2BigQueryFeasibilityResultV3,
)
from aurex.backtest_engine.s2_bigquery_payload import (  # noqa: E402
    S2BigQueryPayloadProtocol,
    S2PayloadQuerySpec,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_payload_protocol_v1.json")
V3_PROTOCOL_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_v3.json")
V3_PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v3.json")
V3_RESULT_PATH = Path("data/evidence/s2_bigquery_feasibility_result_v3.json")
V3_RESULT_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_audit_v3.json")
V3_RUNNER_PATH = Path("scripts/run_s2_bigquery_feasibility_v3.py")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_payload.py")


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


def payload_sql() -> str:
    return """WITH candidate_blocks AS (
  SELECT
    b.number AS block_number,
    DATE_TRUNC(DATE(b.timestamp, 'UTC'), WEEK(SATURDAY)) AS week_start,
    confirmation.timestamp AS sixth_confirmation_timestamp
  FROM `bigquery-public-data.crypto_bitcoin.blocks` AS b
  JOIN `bigquery-public-data.crypto_bitcoin.blocks` AS confirmation
    ON confirmation.number = b.number + 6
  WHERE b.timestamp >= TIMESTAMP('2017-08-19T00:00:00Z')
    AND b.timestamp < TIMESTAMP('2022-12-31T00:00:00Z')
),
qualified_blocks AS (
  SELECT *
  FROM candidate_blocks
  WHERE sixth_confirmation_timestamp
    < TIMESTAMP(DATE_ADD(week_start, INTERVAL 7 DAY), 'UTC')
)
SELECT
  FORMAT_DATE('%F', q.week_start) AS week_start,
  FORMAT_DATE('%F', DATE_ADD(q.week_start, INTERVAL 7 DAY)) AS decision_cutoff_at,
  FORMAT_DATE('%F', DATE_ADD(q.week_start, INTERVAL 9 DAY)) AS earliest_execution_at,
  COUNT(DISTINCT q.block_number) AS confirmed_block_count,
  COUNTIF(NOT t.is_coinbase) AS confirmed_non_coinbase_transaction_count,
  SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS confirmed_fee_satoshis,
  FORMAT_TIMESTAMP(
    '%Y-%m-%dT%H:%M:%E6SZ',
    MAX(q.sixth_confirmation_timestamp),
    'UTC'
  ) AS latest_sixth_confirmation_at
FROM qualified_blocks AS q
JOIN `bigquery-public-data.crypto_bitcoin.transactions` AS t
  ON t.block_number = q.block_number
WHERE t.block_timestamp >= TIMESTAMP('2017-08-19T00:00:00Z')
  AND t.block_timestamp < TIMESTAMP('2022-12-31T00:00:00Z')
GROUP BY q.week_start
ORDER BY q.week_start
"""


def load_v3_lineage():
    protocol = S2BigQueryFeasibilityProtocolV3.model_validate_json(V3_PROTOCOL_PATH.read_text())
    protocol_audit = S2BigQueryFeasibilityProtocolAuditV3.model_validate_json(
        V3_PROTOCOL_AUDIT_PATH.read_text()
    )
    result = S2BigQueryFeasibilityResultV3.model_validate_json(V3_RESULT_PATH.read_text())
    result_audit = S2BigQueryFeasibilityAuditV3.model_validate_json(
        V3_RESULT_AUDIT_PATH.read_text()
    )
    if (
        file_sha256(V3_PROTOCOL_PATH) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != result.protocol_evidence_hash
        or result.result_evidence_hash != result_audit.result_evidence_hash
        or result.decision != S2_FEASIBILITY_V3_PASS
        or result.next_authorization != S2_FEASIBILITY_V3_NEXT
        or result.rest_dry_run_request_count != 2
        or not all(item.succeeded for item in result.rest_dry_run_attempts)
        or result.authorizes_numeric_query is not False
        or result.authorizes_payload_acquisition is not False
    ):
        raise ValueError("S2 BigQuery v3 payload authorization basis did not reconcile")
    return protocol, protocol_audit, result, result_audit


def build_protocol(*, frozen_at: datetime) -> S2BigQueryPayloadProtocol:
    protocol_v3, protocol_audit_v3, result_v3, result_audit_v3 = load_v3_lineage()
    metadata_paths = tuple(
        Path(binding.path)
        for binding in protocol_v3.source_bindings
        if binding.path.startswith("data/evidence/s2_bigquery_metadata_v2/")
    )
    if len(metadata_paths) != 3:
        raise ValueError("S2 BigQuery authenticated metadata bindings are incomplete")
    source_paths = (
        V3_PROTOCOL_PATH,
        V3_PROTOCOL_AUDIT_PATH,
        V3_RESULT_PATH,
        V3_RESULT_AUDIT_PATH,
        V3_RUNNER_PATH,
        *metadata_paths,
    )
    if len(source_paths) != 8 or not all(path.is_file() for path in source_paths):
        raise ValueError("S2 BigQuery payload source set is incomplete")
    query = payload_sql()
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": protocol_v3.charter_evidence_hash,
        "feasibility_protocol_evidence_hash": protocol_v3.protocol_evidence_hash,
        "feasibility_protocol_audit_evidence_hash": protocol_audit_v3.audit_evidence_hash,
        "feasibility_result_evidence_hash": result_v3.result_evidence_hash,
        "feasibility_result_audit_evidence_hash": result_audit_v3.audit_evidence_hash,
        "source_bindings": tuple(
            S2FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
            for path in sorted(source_paths, key=lambda item: item.as_posix())
        ),
        "query_spec": S2PayloadQuerySpec(
            google_sql=query,
            query_sha256=universe_evidence_hash(query),
        ),
        "limitations": tuple(
            sorted(
                (
                    "A valid payload cannot establish predictive edge.",
                    "All acquired values are development-only and outcome-aware.",
                    "Historical screen, validation, and holdout values remain sealed.",
                    "No account, project, credential, token, job ID, or raw "
                    "response may enter evidence.",
                    "No market price or return may be read during payload acquisition.",
                    "Only complete Saturday-through-Friday UTC weeks may be accepted.",
                    "The query must fail before processing more than 60,000,000,000 bytes.",
                    "This stage grants no parameter, signal, paper, Testnet, "
                    "production, or live authority.",
                )
            )
        ),
    }
    return build_hashed(S2BigQueryPayloadProtocol, "protocol_evidence_hash", values)


def write_protocol(path: Path, protocol: S2BigQueryPayloadProtocol) -> None:
    if path.exists():
        raise ValueError(f"S2 BigQuery payload protocol exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2BigQueryPayloadProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S2 BigQuery payload protocol did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 development payload protocol.")
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
            "queries=0 rows=0 market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
