from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1BtcSourceAcquisitionProtocolAuditV2,
    S1BtcSourceAcquisitionProtocolV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_btc_source_acquisition_protocol_v2 import (  # noqa: E402
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_PRIOR_CHECKPOINT,
    DEFAULT_PRIOR_RESULT,
    DEFAULT_V1_PROTOCOL,
    build_protocol,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_acquisition_protocol_audit_v2.json")
AUDITOR_PATH = Path("scripts/audit_s1_btc_source_acquisition_protocol_v2.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the S1.1 BTC source protocol.")
    parser.add_argument("--v1-protocol", type=Path, default=DEFAULT_V1_PROTOCOL)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--prior-checkpoint", type=Path, default=DEFAULT_PRIOR_CHECKPOINT)
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol = S1BtcSourceAcquisitionProtocolV2.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    reconstructed = build_protocol(
        v1_protocol_path=args.v1_protocol,
        amendment_path=args.amendment,
        amendment_audit_path=args.amendment_audit,
        prior_checkpoint_path=args.prior_checkpoint,
        prior_result_path=args.prior_result,
        frozen_at=protocol.frozen_at,
    )
    if reconstructed != protocol:
        raise SystemExit("S1.1 source protocol did not reconstruct exactly")
    payload = {
        "audited_at": datetime.now(UTC),
        "protocol_file_sha256": file_sha256(args.protocol),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "builder_contract_hash": protocol.builder_contract_hash,
        "timing_amendment_evidence_hash": protocol.timing_amendment_evidence_hash,
        "timing_amendment_audit_evidence_hash": (
            protocol.timing_amendment_audit_evidence_hash
        ),
        "prior_result_evidence_hash": protocol.prior_result_evidence_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    provisional = S1BtcSourceAcquisitionProtocolAuditV2.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S1BtcSourceAcquisitionProtocolAuditV2.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1.1 source protocol audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"protocol={audit.protocol_evidence_hash} btc_values=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
