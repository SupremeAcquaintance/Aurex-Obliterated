from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_feasibility import (  # noqa: E402
    S1SourceMetadataAudit,
    S1SourceMetadataProtocol,
    S1SourceMetadataResult,
)
from aurex.backtest_engine.s1_source_transport_v2 import (  # noqa: E402
    S1SourceTransportAmendmentV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_source_transport_amendment_v2.json")
V1_PROTOCOL_PATH = Path(
    "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
)
V1_RESULT_PATH = Path("data/evidence/s1_source_metadata_feasibility_result_v1.json")
V1_AUDIT_PATH = Path("data/evidence/s1_source_metadata_feasibility_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_source_transport_v2.py")
SCRIPT_PATH = Path("scripts/freeze_s1_source_transport_amendment_v2.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_amendment(*, frozen_at: datetime) -> S1SourceTransportAmendmentV2:
    protocol = S1SourceMetadataProtocol.model_validate_json(
        V1_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    result = S1SourceMetadataResult.model_validate_json(
        V1_RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1SourceMetadataAudit.model_validate_json(
        V1_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if result.decision != "STOP_S1_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE":
        raise ValueError("S1 v1 did not stop at the required transport boundary")
    transport_errors = tuple(
        response.error_type
        for response in result.responses
        if response.outcome == "TRANSPORT_ERROR"
    )
    if transport_errors != ("TimeoutError", "TimeoutError", "TimeoutError"):
        raise ValueError("S1 v1 failure class changed")
    if any(response.body_bytes_read != 0 for response in result.responses):
        raise ValueError("S1 v1 opened response body bytes")
    if audit.result_evidence_hash != result.result_evidence_hash:
        raise ValueError("S1 v1 audit does not bind the stopped result")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "v1_protocol_file_sha256": file_sha256(V1_PROTOCOL_PATH),
        "v1_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "v1_result_file_sha256": file_sha256(V1_RESULT_PATH),
        "v1_result_evidence_hash": result.result_evidence_hash,
        "v1_audit_file_sha256": file_sha256(V1_AUDIT_PATH),
        "v1_audit_evidence_hash": audit.audit_evidence_hash,
        "preserved_urls": tuple(request.url for request in protocol.requests),
        "unchanged_gates": protocol.feasibility_gates,
    }
    provisional = S1SourceTransportAmendmentV2.model_construct(
        **payload,
        amendment_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"amendment_evidence_hash"})
    )
    return S1SourceTransportAmendmentV2.model_validate(complete)


def write_atomic(path: Path, amendment: S1SourceTransportAmendmentV2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 v2 amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S1SourceTransportAmendmentV2.model_validate_json(serialized) != amendment:
        raise ValueError("S1 v2 amendment did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 transport v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1SourceTransportAmendmentV2.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_amendment(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 v2 amendment differs from reconstruction")
        print(f"PASS {stored.amendment_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 v2 amendment: {args.output}")
    amendment = build_amendment(frozen_at=datetime.now(UTC))
    write_atomic(args.output, amendment)
    print(
        f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
        "requests=0 read_calls=0 body_bytes=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
