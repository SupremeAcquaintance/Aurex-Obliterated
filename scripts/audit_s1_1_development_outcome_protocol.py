from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome import (  # noqa: E402
    S11DevelopmentOutcomeProtocol,
    S11DevelopmentOutcomeProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_1_development_outcome_protocol import (  # noqa: E402
    AMENDMENT_PATH,
    FEATURE_DATASET_PATH,
    PREREGISTRATION_PATH,
    PRICE_DATASET_PATH,
    SOURCE_AUDIT_PATH,
    SOURCE_RESULT_PATH,
    build_protocol,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_1_development_outcome_protocol_v1.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_1_development_outcome_protocol_audit_v1.json"
)
AUDITOR_PATH = Path("scripts/audit_s1_1_development_outcome_protocol.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the S1.1 outcome protocol.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol = S11DevelopmentOutcomeProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    if build_protocol(frozen_at=protocol.frozen_at) != protocol:
        raise SystemExit("S1.1 outcome protocol did not reconstruct exactly")
    payload = {
        "audited_at": datetime.now(UTC),
        "protocol_file_sha256": file_sha256(args.protocol),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "builder_contract_hash": protocol.builder_contract_hash,
        "strategy_preregistration_evidence_hash": (
            protocol.strategy_preregistration_evidence_hash
        ),
        "timing_amendment_evidence_hash": protocol.timing_amendment_evidence_hash,
        "source_result_evidence_hash": protocol.source_result_evidence_hash,
        "source_audit_evidence_hash": protocol.source_audit_evidence_hash,
        "feature_dataset_file_sha256": file_sha256(FEATURE_DATASET_PATH),
        "price_dataset_file_sha256": file_sha256(PRICE_DATASET_PATH),
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    if (
        file_sha256(PREREGISTRATION_PATH)
        != protocol.strategy_preregistration_file_sha256
        or file_sha256(AMENDMENT_PATH) != protocol.timing_amendment_file_sha256
        or file_sha256(SOURCE_RESULT_PATH) != protocol.source_result_file_sha256
        or file_sha256(SOURCE_AUDIT_PATH) != protocol.source_audit_file_sha256
    ):
        raise SystemExit("S1.1 outcome protocol source hash changed")
    provisional = S11DevelopmentOutcomeProtocolAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S11DevelopmentOutcomeProtocolAudit.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1.1 outcome protocol audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"protocol={audit.protocol_evidence_hash} values=0 returns=0 outcomes=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
