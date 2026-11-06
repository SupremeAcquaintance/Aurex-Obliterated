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
    S3_TRANSPORT_FAILURE_ADJUDICATION,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceTransportFailureAudit,
    audit_transport_failure,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s3_cftc_source_feasibility import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_v2.json"
)
PROTOCOL_PATH = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
PRIOR_RESULT_PATH = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
FAILURE_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_transport_failure_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s3_cftc_source_feasibility_transport.py"
)
SCRIPT_PATH = Path("scripts/freeze_s3_cftc_metadata_transport_amendment_v2.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_inputs():
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
    if (
        not audit_transport_failure(failure)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or prior.protocol_evidence_hash != protocol.protocol_evidence_hash
        or failure.result_evidence_hash != prior.result_evidence_hash
        or failure.adjudication != S3_TRANSPORT_FAILURE_ADJUDICATION
        or failure.successful_response_count != 0
        or failure.cftc_target_position_values_read != 0
        or prior.cftc_target_position_values_read != 0
        or prior.btc_market_values_read != 0
        or prior.orders_submitted != 0
    ):
        raise ValueError("S3 transport amendment lineage changed")
    return protocol, prior, failure


def bindings() -> tuple[S3FeasibilityBinding, ...]:
    paths = (
        PROTOCOL_PATH,
        PROTOCOL_AUDIT_PATH,
        PRIOR_RESULT_PATH,
        FAILURE_AUDIT_PATH,
    )
    return tuple(
        S3FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def build_amendment(*, frozen_at: datetime) -> S3CftcMetadataTransportAmendmentV2:
    protocol, prior, failure = load_inputs()
    return build_hashed(
        S3CftcMetadataTransportAmendmentV2,
        "amendment_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "prior_result_evidence_hash": prior.result_evidence_hash,
            "failure_audit_evidence_hash": failure.audit_evidence_hash,
            "source_bindings": bindings(),
            "limitations": tuple(
                sorted(
                    (
                        "The first run received zero CFTC responses and is preserved.",
                        "The rerun may change transport only, never URLs, tokens, or gates.",
                        "The rerun may occur once and make at most three metadata requests.",
                        "No target position row or value may be parsed.",
                        "No BTC value, parameter, return, candidate, or order is authorized.",
                        "A successful transport does not imply source feasibility or edge.",
                    )
                )
            ),
        },
    )


def write_atomic(path: Path, amendment: S3CftcMetadataTransportAmendmentV2) -> None:
    if path.exists():
        raise ValueError(f"S3 transport amendment exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 transport-amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S3CftcMetadataTransportAmendmentV2.model_validate_json(serialized) != amendment:
        raise ValueError("S3 transport amendment did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check S3 transport v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S3CftcMetadataTransportAmendmentV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_amendment(frozen_at=stored.frozen_at):
                raise ValueError("Stored S3 transport amendment changed")
            print(f"PASS {stored.amendment_evidence_hash}")
            return 0
        amendment = build_amendment(frozen_at=datetime.now(UTC))
        write_atomic(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "network=0 cftc_values=0 market_values=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
