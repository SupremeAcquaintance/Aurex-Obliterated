from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s2_bigquery_payload import (  # noqa: E402
    S2DevelopmentWeeklyPayload,
)
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2_MEASUREMENT_PASS,
    S2DevelopmentMeasurementExecutionAddendum,
    S2DevelopmentMeasurementExecutionAudit,
    S2DevelopmentMeasurementResult,
    S2DevelopmentMeasurementResultAudit,
    build_measurement_rows,
    measurement_row_hashes,
    serialize_measurement_rows,
)
from aurex.backtest_engine.s2_development_measurement_protocol import (  # noqa: E402
    S2DevelopmentMeasurementProtocol,
    S2DevelopmentMeasurementProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s2_development_measurements import (  # noqa: E402
    EXECUTION_ADDENDUM_PATH,
    EXECUTION_AUDIT_PATH,
    PAYLOAD_PATH,
    PROTOCOL_AUDIT_PATH,
    PROTOCOL_PATH,
    file_sha256,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s2_development_measurement_result_v1.json")
DEFAULT_DATASET = Path("data/evidence/s2_development_measurements_v1.jsonl")
DEFAULT_OUTPUT = Path("data/evidence/s2_development_measurement_result_audit_v1.json")


def auditor_contract_hash() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S2 development measurement result.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 measurement result audit exists: {args.output}")
        protocol = S2DevelopmentMeasurementProtocol.model_validate_json(PROTOCOL_PATH.read_text())
        protocol_audit = S2DevelopmentMeasurementProtocolAudit.model_validate_json(
            PROTOCOL_AUDIT_PATH.read_text()
        )
        addendum = S2DevelopmentMeasurementExecutionAddendum.model_validate_json(
            EXECUTION_ADDENDUM_PATH.read_text()
        )
        execution_audit = S2DevelopmentMeasurementExecutionAudit.model_validate_json(
            EXECUTION_AUDIT_PATH.read_text()
        )
        payload = S2DevelopmentWeeklyPayload.model_validate_json(PAYLOAD_PATH.read_text())
        result = S2DevelopmentMeasurementResult.model_validate_json(args.result.read_text())
        rows = build_measurement_rows(payload)
        expected_dataset = serialize_measurement_rows(rows)
        expected_row_hashes = measurement_row_hashes(rows)
        if (
            file_sha256(PROTOCOL_PATH) != addendum.protocol_file_sha256
            or protocol.protocol_evidence_hash != result.protocol_evidence_hash
            or protocol_audit.audit_evidence_hash != result.protocol_audit_evidence_hash
            or file_sha256(EXECUTION_ADDENDUM_PATH) != result.execution_addendum_file_sha256
            or addendum.addendum_evidence_hash != result.execution_addendum_evidence_hash
            or execution_audit.audit_evidence_hash != result.execution_audit_evidence_hash
            or runner_contract_hash() != result.runner_contract_hash
            or file_sha256(PAYLOAD_PATH) != result.payload_file_sha256
            or payload.payload_evidence_hash != result.payload_evidence_hash
            or args.dataset.read_bytes() != expected_dataset
            or sha256(expected_dataset).hexdigest() != result.measurement_dataset_file_sha256
            or len(expected_dataset) != result.measurement_dataset_bytes
            or expected_row_hashes != result.row_evidence_hashes
            or result.decision != S2_MEASUREMENT_PASS
            or result.market_values_read != 0
            or result.returns_calculated != 0
            or result.orders_submitted != 0
        ):
            raise ValueError("S2 development measurement result did not reconstruct exactly")
        audit = build_hashed(
            S2DevelopmentMeasurementResultAudit,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "result_file_sha256": file_sha256(args.result),
                "result_evidence_hash": result.result_evidence_hash,
                "measurement_dataset_file_sha256": result.measurement_dataset_file_sha256,
                "runner_contract_hash": result.runner_contract_hash,
                "auditor_contract_hash": auditor_contract_hash(),
                "measurement_row_manifest_evidence_hash": universe_evidence_hash(
                    expected_row_hashes
                ),
            },
        )
        args.output.write_text(
            audit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"rows={audit.measurement_row_count} market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
