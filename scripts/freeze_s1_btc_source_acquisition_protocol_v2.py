from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_acquisition import (  # noqa: E402
    S1BtcSourceAcquisitionProtocol,
)
from aurex.backtest_engine.s1_btc_source_execution import (  # noqa: E402
    S1BtcAcquisitionCheckpoint,
    S1BtcSourceAcquisitionResult,
)
from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1_1_SOURCE_GATES,
    S1BtcReuseArtifactV2,
    S1BtcSourceAcquisitionProtocolV2,
    S1SourceTimingAmendmentAuditV2,
    S1SourceTimingAmendmentV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import (  # noqa: E402
    file_sha256,
    parse_checksum_text,
)

DEFAULT_V1_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")
DEFAULT_AMENDMENT = Path("data/evidence/s1_source_timing_amendment_v2.json")
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/s1_source_timing_amendment_audit_v2.json"
)
DEFAULT_PRIOR_CHECKPOINT = Path(
    "data/evidence/s1_btc_source_acquisition_checkpoint_v1.json"
)
DEFAULT_PRIOR_RESULT = Path("data/evidence/s1_btc_source_acquisition_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_acquisition_protocol_v2.json")
BUILDER_PATH = Path("scripts/freeze_s1_btc_source_acquisition_protocol_v2.py")


def build_reuse_artifact(target, evidence) -> S1BtcReuseArtifactV2:
    archive_path = PROJECT_ROOT / target.archive_path
    checksum_path = PROJECT_ROOT / target.checksum_path
    published = parse_checksum_text(checksum_path.read_text(), archive_path.name)
    if (
        file_sha256(archive_path) != evidence.archive_file_sha256
        or file_sha256(checksum_path) != evidence.checksum_file_sha256
        or published != evidence.archive_file_sha256
    ):
        raise ValueError("S1.1 local reuse evidence changed")
    payload = {
        "sequence": target.sequence,
        "target_id": target.target_id,
        "activation_date": target.activation_date,
        "archive_path": target.archive_path,
        "archive_file_sha256": evidence.archive_file_sha256,
        "archive_bytes": archive_path.stat().st_size,
        "checksum_path": target.checksum_path,
        "checksum_file_sha256": evidence.checksum_file_sha256,
        "checksum_bytes": checksum_path.stat().st_size,
        "published_archive_sha256": published,
    }
    provisional = S1BtcReuseArtifactV2.model_construct(
        **payload,
        reuse_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["reuse_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"reuse_evidence_hash"})
    )
    return S1BtcReuseArtifactV2.model_validate(complete)


def build_protocol(
    *,
    v1_protocol_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
    prior_checkpoint_path: Path,
    prior_result_path: Path,
    frozen_at: datetime,
) -> S1BtcSourceAcquisitionProtocolV2:
    v1_protocol = S1BtcSourceAcquisitionProtocol.model_validate_json(
        v1_protocol_path.read_text(encoding="utf-8")
    )
    amendment = S1SourceTimingAmendmentV2.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    amendment_audit = S1SourceTimingAmendmentAuditV2.model_validate_json(
        amendment_audit_path.read_text(encoding="utf-8")
    )
    checkpoint = S1BtcAcquisitionCheckpoint.model_validate_json(
        prior_checkpoint_path.read_text(encoding="utf-8")
    )
    result = S1BtcSourceAcquisitionResult.model_validate_json(
        prior_result_path.read_text(encoding="utf-8")
    )
    if (
        amendment.amendment_evidence_hash != amendment_audit.amendment_evidence_hash
        or amendment.failed_source_result_evidence_hash != result.result_evidence_hash
        or checkpoint.checkpoint_evidence_hash != result.checkpoint_evidence_hash
        or checkpoint.classified_target_count != 22
    ):
        raise ValueError("S1.1 source protocol input boundary changed")
    reuse = tuple(
        build_reuse_artifact(target, evidence)
        for target, evidence in zip(
            v1_protocol.targets[:22],
            checkpoint.target_evidence,
            strict=True,
        )
    )
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "timing_amendment_file_sha256": file_sha256(amendment_path),
        "timing_amendment_evidence_hash": amendment.amendment_evidence_hash,
        "timing_amendment_audit_file_sha256": file_sha256(amendment_audit_path),
        "timing_amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
        "prior_checkpoint_file_sha256": file_sha256(prior_checkpoint_path),
        "prior_checkpoint_evidence_hash": checkpoint.checkpoint_evidence_hash,
        "prior_result_file_sha256": file_sha256(prior_result_path),
        "prior_result_evidence_hash": result.result_evidence_hash,
        "reuse_artifacts": reuse,
        "targets": v1_protocol.targets,
        "quality_gates": S1_1_SOURCE_GATES,
    }
    provisional = S1BtcSourceAcquisitionProtocolV2.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1BtcSourceAcquisitionProtocolV2.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the S1.1 BTC source protocol.")
    parser.add_argument("--v1-protocol", type=Path, default=DEFAULT_V1_PROTOCOL)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--prior-checkpoint", type=Path, default=DEFAULT_PRIOR_CHECKPOINT)
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1.1 source protocol exists: {args.output}")
    protocol = build_protocol(
        v1_protocol_path=args.v1_protocol,
        amendment_path=args.amendment,
        amendment_audit_path=args.amendment_audit,
        prior_checkpoint_path=args.prior_checkpoint,
        prior_result_path=args.prior_result,
        frozen_at=datetime.now(UTC),
    )
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "reuse=22 network_targets=255 btc_values=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
