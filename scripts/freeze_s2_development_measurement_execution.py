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
from aurex.backtest_engine.s2_bigquery_payload_v2 import (  # noqa: E402
    S2BigQueryPayloadAuditV2,
    S2BigQueryPayloadResultV2,
)
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2DevelopmentMeasurementExecutionAddendum,
)
from aurex.backtest_engine.s2_development_measurement_protocol import (  # noqa: E402
    S2_MEASUREMENT_NEXT,
    S2DevelopmentMeasurementProtocol,
    S2DevelopmentMeasurementProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s2_development_measurements import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_RESULT,
    PAYLOAD_PATH,
    runner_contract_hash,
)

DEFAULT_ADDENDUM = Path("data/evidence/s2_development_measurement_execution_addendum_v1.json")
PROTOCOL_PATH = Path("data/evidence/s2_development_measurement_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_development_measurement_protocol_audit_v1.json")
PAYLOAD_RESULT_PATH = Path("data/evidence/s2_bigquery_payload_result_v2.json")
PAYLOAD_AUDIT_PATH = Path("data/evidence/s2_bigquery_payload_audit_v2.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_development_measurement_execution.py")

SYNTHETIC_TEST_IDS = (
    "authority_boundary_rejects_market_and_return_escalation",
    "causal_current_and_prior_four_week_windows",
    "deterministic_jsonl_and_row_manifest",
    "half_even_ppm_integer_arithmetic",
    "inconsistent_measurement_row_rejected",
    "invalid_growth_denominators_rejected",
    "strict_three_state_agreement_classification",
    "zero_prior_fee_denominator_rejects_run",
)


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


def build_addendum(*, frozen_at: datetime) -> S2DevelopmentMeasurementExecutionAddendum:
    protocol = S2DevelopmentMeasurementProtocol.model_validate_json(PROTOCOL_PATH.read_text())
    protocol_audit = S2DevelopmentMeasurementProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text()
    )
    payload_result = S2BigQueryPayloadResultV2.model_validate_json(PAYLOAD_RESULT_PATH.read_text())
    payload_audit = S2BigQueryPayloadAuditV2.model_validate_json(PAYLOAD_AUDIT_PATH.read_text())
    if (
        protocol.next_authorization != S2_MEASUREMENT_NEXT
        or file_sha256(PROTOCOL_PATH) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.payload_result_evidence_hash != payload_result.result_evidence_hash
        or protocol.payload_result_audit_evidence_hash != payload_audit.audit_evidence_hash
        or protocol.payload_file_sha256 != file_sha256(PAYLOAD_PATH)
        or protocol.payload_file_sha256 != payload_result.payload_file_sha256
        or protocol.payload_evidence_hash != payload_result.payload_evidence_hash
        or DEFAULT_OUTPUT.exists()
        or DEFAULT_RESULT.exists()
    ):
        raise ValueError("S2 measurement execution amendment basis did not reconcile")
    return build_hashed(
        S2DevelopmentMeasurementExecutionAddendum,
        "addendum_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "protocol_file_sha256": file_sha256(PROTOCOL_PATH),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": file_sha256(PROTOCOL_AUDIT_PATH),
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "payload_result_evidence_hash": payload_result.result_evidence_hash,
            "payload_result_audit_evidence_hash": payload_audit.audit_evidence_hash,
            "payload_file_sha256": file_sha256(PAYLOAD_PATH),
            "payload_evidence_hash": payload_result.payload_evidence_hash,
            "runner_contract_hash": runner_contract_hash(),
            "synthetic_test_ids": SYNTHETIC_TEST_IDS,
        },
    )


def write_addendum(
    path: Path,
    addendum: S2DevelopmentMeasurementExecutionAddendum,
) -> None:
    if path.exists():
        raise ValueError(f"S2 development measurement execution addendum exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = addendum.model_dump_json(indent=2) + "\n"
    if S2DevelopmentMeasurementExecutionAddendum.model_validate_json(serialized) != addendum:
        raise ValueError("S2 development measurement execution addendum did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 measurement execution authority.")
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_ADDENDUM)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        addendum = build_addendum(frozen_at=datetime.now(UTC))
        write_addendum(args.output, addendum)
        print(
            f"FROZEN {args.output} {addendum.addendum_evidence_hash} "
            "payload_rows=0 measurements=0 market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
