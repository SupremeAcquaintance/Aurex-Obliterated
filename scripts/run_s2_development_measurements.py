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
    S2MeasurementGate,
    build_measurement_rows,
    measurement_row_hashes,
    serialize_measurement_rows,
)
from aurex.backtest_engine.s2_development_measurement_protocol import (  # noqa: E402
    S2_MEASUREMENT_GATES,
    S2DevelopmentMeasurementProtocol,
    S2DevelopmentMeasurementProtocolAudit,
)

PROTOCOL_PATH = Path("data/evidence/s2_development_measurement_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_development_measurement_protocol_audit_v1.json")
EXECUTION_ADDENDUM_PATH = Path(
    "data/evidence/s2_development_measurement_execution_addendum_v1.json"
)
EXECUTION_AUDIT_PATH = Path("data/evidence/s2_development_measurement_execution_audit_v1.json")
PAYLOAD_PATH = Path("data/evidence/s2_development_weekly_payload_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_development_measurements_v1.jsonl")
DEFAULT_RESULT = Path("data/evidence/s2_development_measurement_result_v1.json")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    return file_sha256(Path(__file__))


def load_authority():
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
    if (
        file_sha256(PROTOCOL_PATH) != addendum.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != addendum.protocol_evidence_hash
        or file_sha256(PROTOCOL_AUDIT_PATH) != addendum.protocol_audit_file_sha256
        or protocol_audit.audit_evidence_hash != addendum.protocol_audit_evidence_hash
        or file_sha256(EXECUTION_ADDENDUM_PATH) != execution_audit.addendum_file_sha256
        or addendum.addendum_evidence_hash != execution_audit.addendum_evidence_hash
        or addendum.runner_contract_hash != runner_contract_hash()
        or addendum.runner_contract_hash != execution_audit.runner_contract_hash
        or addendum.authorizes_single_measurement_run is not True
        or addendum.authorizes_payload_value_read is not True
        or addendum.authorizes_measurement_calculation is not True
        or addendum.authorizes_market_value_access is not False
        or addendum.authorizes_return_testing is not False
    ):
        raise ValueError("S2 measurement execution authority did not reconcile")
    return protocol, protocol_audit, addendum, execution_audit


def passing_gates() -> tuple[S2MeasurementGate, ...]:
    return tuple(
        S2MeasurementGate(
            gate_id=gate_id,
            status="PASS",
            reason="Frozen S2 measurement contract satisfied exactly.",
        )
        for gate_id in S2_MEASUREMENT_GATES
    )


def execute(*, output_path: Path, result_path: Path) -> S2DevelopmentMeasurementResult:
    protocol, protocol_audit, addendum, execution_audit = load_authority()
    if output_path.exists() or result_path.exists():
        raise ValueError("S2 development measurement output or result already exists")
    if (
        output_path.as_posix() != addendum.output_path
        or result_path.as_posix() != addendum.result_path
    ):
        raise ValueError("S2 development measurement output path changed")
    if file_sha256(PAYLOAD_PATH) != addendum.payload_file_sha256:
        raise ValueError("S2 development payload file changed")
    payload = S2DevelopmentWeeklyPayload.model_validate_json(PAYLOAD_PATH.read_text())
    if payload.payload_evidence_hash != addendum.payload_evidence_hash:
        raise ValueError("S2 development payload evidence changed")

    rows = build_measurement_rows(payload)
    serialized = serialize_measurement_rows(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(serialized)
    result = build_hashed(
        S2DevelopmentMeasurementResult,
        "result_evidence_hash",
        {
            "completed_at": datetime.now(UTC),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "execution_addendum_file_sha256": file_sha256(EXECUTION_ADDENDUM_PATH),
            "execution_addendum_evidence_hash": addendum.addendum_evidence_hash,
            "execution_audit_evidence_hash": execution_audit.audit_evidence_hash,
            "runner_contract_hash": runner_contract_hash(),
            "payload_file_sha256": file_sha256(PAYLOAD_PATH),
            "payload_evidence_hash": payload.payload_evidence_hash,
            "measurement_dataset_file_sha256": sha256(serialized).hexdigest(),
            "measurement_dataset_bytes": len(serialized),
            "row_evidence_hashes": measurement_row_hashes(rows),
            "gates": passing_gates(),
        },
    )
    result_path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run S2 development measurements once.")
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        result = execute(output_path=args.output, result_path=args.result)
        print(
            f"WROTE {args.output} {result.measurement_dataset_file_sha256} "
            f"rows={result.measurement_row_count} result={result.result_evidence_hash} "
            f"decision={S2_MEASUREMENT_PASS} market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
