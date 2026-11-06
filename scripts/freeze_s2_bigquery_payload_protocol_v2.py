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
from aurex.backtest_engine.s2_bigquery_payload import (  # noqa: E402
    S2_PAYLOAD_BLOCK_VALIDATION,
    S2BigQueryPayloadProtocol,
    S2BigQueryPayloadProtocolAudit,
    S2BigQueryPayloadResult,
    S2PayloadQuerySpec,
)
from aurex.backtest_engine.s2_bigquery_payload_v2 import (  # noqa: E402
    S2BigQueryPayloadFailureAuditV1,
    S2BigQueryPayloadProtocolV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_payload_protocol_v2.json")
V1_PROTOCOL_PATH = Path("data/evidence/s2_bigquery_payload_protocol_v1.json")
V1_PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_payload_protocol_audit_v1.json")
V1_RESULT_PATH = Path("data/evidence/s2_bigquery_payload_result_v1.json")
V1_FAILURE_AUDIT_PATH = Path("data/evidence/s2_bigquery_payload_failure_audit_v1.json")
V1_RUNNER_PATH = Path("scripts/run_s2_bigquery_payload.py")
TRANSACTIONS_METADATA_PATH = Path(
    "data/evidence/s2_bigquery_metadata_v2/transactions_table_metadata.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_payload_v2.py")


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


def load_v1_lineage():
    protocol = S2BigQueryPayloadProtocol.model_validate_json(V1_PROTOCOL_PATH.read_text())
    protocol_audit = S2BigQueryPayloadProtocolAudit.model_validate_json(
        V1_PROTOCOL_AUDIT_PATH.read_text()
    )
    result = S2BigQueryPayloadResult.model_validate_json(V1_RESULT_PATH.read_text())
    failure_audit = S2BigQueryPayloadFailureAuditV1.model_validate_json(
        V1_FAILURE_AUDIT_PATH.read_text()
    )
    if (
        file_sha256(V1_PROTOCOL_PATH) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != result.protocol_evidence_hash
        or result.result_evidence_hash != failure_audit.result_evidence_hash
        or result.decision != S2_PAYLOAD_BLOCK_VALIDATION
        or result.blockers != ("payload_schema_mismatch",)
        or result.query_completed is not True
        or result.query_result_rows_returned != 0
        or failure_audit.blocker != "payload_schema_mismatch"
    ):
        raise ValueError("S2 payload v1 amendment basis did not reconcile")
    return protocol, protocol_audit, result, failure_audit


def corrected_query(protocol: S2BigQueryPayloadProtocol) -> S2PayloadQuerySpec:
    old = "SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS confirmed_fee_satoshis,"
    new = "CAST(SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS INT64) AS confirmed_fee_satoshis,"
    if protocol.query_spec.google_sql.count(old) != 1:
        raise ValueError("S2 payload fee expression amendment target changed")
    query = protocol.query_spec.google_sql.replace(old, new)
    return S2PayloadQuerySpec(
        google_sql=query,
        query_sha256=universe_evidence_hash(query),
    )


def build_protocol(*, frozen_at: datetime) -> S2BigQueryPayloadProtocolV2:
    protocol_v1, protocol_audit_v1, result_v1, failure_audit_v1 = load_v1_lineage()
    source_paths = (
        TRANSACTIONS_METADATA_PATH,
        V1_FAILURE_AUDIT_PATH,
        V1_PROTOCOL_AUDIT_PATH,
        V1_PROTOCOL_PATH,
        V1_RESULT_PATH,
        V1_RUNNER_PATH,
    )
    if not all(path.is_file() for path in source_paths):
        raise ValueError("S2 payload v2 source set is incomplete")
    inherited = protocol_v1.model_dump(
        exclude={
            "schema_version",
            "protocol_id",
            "frozen_at",
            "status",
            "builder_contract_hash",
            "source_bindings",
            "query_spec",
            "decision",
            "next_authorization",
            "limitations",
            "protocol_evidence_hash",
        }
    )
    values = {
        **inherited,
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "prior_payload_protocol_evidence_hash": protocol_v1.protocol_evidence_hash,
        "prior_payload_protocol_audit_evidence_hash": protocol_audit_v1.audit_evidence_hash,
        "prior_payload_result_evidence_hash": result_v1.result_evidence_hash,
        "prior_payload_failure_audit_evidence_hash": failure_audit_v1.audit_evidence_hash,
        "prior_payload_result_decision": result_v1.decision,
        "source_bindings": tuple(
            S2FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
            for path in sorted(source_paths, key=lambda item: item.as_posix())
        ),
        "query_spec": corrected_query(protocol_v1),
        "limitations": tuple(
            sorted(
                (
                    *protocol_v1.limitations,
                    "V1 completed its query but accepted zero rows after the "
                    "observed schema mismatch.",
                    "V2 changes only the confirmed-fee aggregate output cast "
                    "from NUMERIC to INT64.",
                )
            )
        ),
    }
    return build_hashed(S2BigQueryPayloadProtocolV2, "protocol_evidence_hash", values)


def write_protocol(path: Path, protocol: S2BigQueryPayloadProtocolV2) -> None:
    if path.exists():
        raise ValueError(f"S2 BigQuery payload protocol v2 exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2BigQueryPayloadProtocolV2.model_validate_json(serialized) != protocol:
        raise ValueError("S2 BigQuery payload protocol v2 did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 payload schema amendment v2.")
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
