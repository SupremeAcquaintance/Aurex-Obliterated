from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    S3FeasibilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (  # noqa: E402
    S3_TRANSPORT_RUN_AUTHORIZATION,
    S3CftcMetadataTransportAmendmentAuditV2,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceTransportFailureAudit,
)
from aurex.backtest_engine.s3_cftc_source_transport_outcome import (  # noqa: E402
    S3_TRANSPORT_V2_FAILURE_MESSAGE,
    S3CftcMetadataTransportExecutionReceiptV2,
    audit_transport_execution_receipt,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s3_cftc_source_feasibility import file_sha256  # noqa: E402
from scripts.run_s3_cftc_source_feasibility_v2 import (  # noqa: E402
    runner_contract_hash,
)

PROTOCOL_PATH = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
PRIOR_RESULT_PATH = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
FAILURE_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_transport_failure_audit_v1.json"
)
AMENDMENT_PATH = Path("data/evidence/s3_cftc_metadata_transport_amendment_v2.json")
AMENDMENT_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_audit_v2.json"
)
RESULT_PATH = Path("data/evidence/s3_cftc_source_feasibility_result_v2.json")
RESPONSE_PATHS = (
    Path("data/evidence/s3_cftc_metadata_v2/cot_faq.html"),
    Path(
        "data/evidence/s3_cftc_metadata_v2/historical_special_announcements.html"
    ),
    Path("data/evidence/s3_cftc_metadata_v2/historical_viewable_index.html"),
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_v2.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s3_cftc_source_transport_outcome.py"
)
SCRIPT_PATH = Path("scripts/record_s3_cftc_metadata_transport_outcome_v2.py")


def recorder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def source_bindings() -> tuple[S3FeasibilityBinding, ...]:
    paths = (
        PROTOCOL_PATH,
        PROTOCOL_AUDIT_PATH,
        PRIOR_RESULT_PATH,
        FAILURE_AUDIT_PATH,
        AMENDMENT_PATH,
        AMENDMENT_AUDIT_PATH,
    )
    return tuple(
        S3FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def build_receipt(*, recorded_at: datetime) -> S3CftcMetadataTransportExecutionReceiptV2:
    protocol = S3CftcSourceFeasibilityProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    prior = S3CftcSourceFeasibilityResult.model_validate_json(
        PRIOR_RESULT_PATH.read_text(encoding="utf-8")
    )
    failure = S3CftcSourceTransportFailureAudit.model_validate_json(
        FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    amendment = S3CftcMetadataTransportAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    amendment_audit = S3CftcMetadataTransportAmendmentAuditV2.model_validate_json(
        AMENDMENT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or prior.protocol_evidence_hash != protocol.protocol_evidence_hash
        or failure.result_evidence_hash != prior.result_evidence_hash
        or amendment.protocol_evidence_hash != protocol.protocol_evidence_hash
        or amendment.prior_result_evidence_hash != prior.result_evidence_hash
        or amendment.failure_audit_evidence_hash != failure.audit_evidence_hash
        or amendment_audit.amendment_evidence_hash
        != amendment.amendment_evidence_hash
        or amendment.next_authorization != S3_TRANSPORT_RUN_AUTHORIZATION
        or amendment.maximum_rerun_count != 1
        or amendment.maximum_metadata_requests != 3
        or RESULT_PATH.exists()
        or any(path.exists() for path in RESPONSE_PATHS)
    ):
        raise ValueError("S3 transport v2 outcome lineage or filesystem state changed")
    return build_hashed(
        S3CftcMetadataTransportExecutionReceiptV2,
        "receipt_evidence_hash",
        {
            "recorded_at": recorded_at,
            "recorder_contract_hash": recorder_contract_hash(),
            "runner_contract_hash": runner_contract_hash(),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "prior_result_evidence_hash": prior.result_evidence_hash,
            "failure_audit_evidence_hash": failure.audit_evidence_hash,
            "transport_amendment_evidence_hash": amendment.amendment_evidence_hash,
            "transport_amendment_audit_evidence_hash": (
                amendment_audit.audit_evidence_hash
            ),
            "source_bindings": source_bindings(),
            "expected_response_paths": tuple(
                path.as_posix() for path in RESPONSE_PATHS
            ),
            "terminal_message": S3_TRANSPORT_V2_FAILURE_MESSAGE,
            "limitations": tuple(
                sorted(
                    (
                        "The exact count of successful in-memory responses was not persisted.",
                        "The runner proved only that fewer than all three responses arrived.",
                        "No response body or v2 feasibility result was persisted.",
                        "The one authorized transport rerun is exhausted and may not repeat.",
                        "S3 source feasibility was not established under the frozen protocol.",
                        "This retirement is not evidence of edge, profitability, "
                        "or source impossibility.",
                        "No CFTC position value, BTC value, return, or order was created.",
                    )
                )
            ),
        },
    )


def write_atomic(
    path: Path, receipt: S3CftcMetadataTransportExecutionReceiptV2
) -> None:
    if path.exists():
        raise ValueError(f"S3 transport execution receipt exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 transport receipt transaction exists: {temporary}")
    serialized = receipt.model_dump_json(indent=2) + "\n"
    if S3CftcMetadataTransportExecutionReceiptV2.model_validate_json(
        serialized
    ) != receipt:
        raise ValueError("S3 transport execution receipt did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record S3 transport v2 outcome.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--record", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S3CftcMetadataTransportExecutionReceiptV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_receipt(recorded_at=stored.recorded_at)
            if stored != expected or not audit_transport_execution_receipt(stored):
                raise ValueError("Stored S3 transport execution receipt changed")
            print(f"PASS {stored.receipt_evidence_hash}")
            return 0
        receipt = build_receipt(recorded_at=datetime.now(UTC))
        write_atomic(args.output, receipt)
        print(
            f"RECORDED {args.output} {receipt.receipt_evidence_hash} "
            "exit=1 responses_persisted=0 result=false values=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
