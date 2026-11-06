from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution_v2 import (  # noqa: E402
    S1BtcSourceAcquisitionResultV2,
)
from aurex.backtest_engine.s1_btc_source_result_audit_v2 import (  # noqa: E402
    S1BtcSourceAcquisitionAuditV2,
)
from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1SourceTimingAmendmentAuditV2,
    S1SourceTimingAmendmentV2,
)
from aurex.backtest_engine.s1_development_outcome import (  # noqa: E402
    S11DevelopmentOutcomeProtocol,
)
from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureResult,
    S1NfciFeatureResultAudit,
)
from aurex.backtest_engine.s1_strategy_preregistration import (  # noqa: E402
    S1StrategyPreregistration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

PREREGISTRATION_PATH = Path("data/evidence/s1_strategy_preregistration_v1.json")
AMENDMENT_PATH = Path("data/evidence/s1_source_timing_amendment_v2.json")
AMENDMENT_AUDIT_PATH = Path("data/evidence/s1_source_timing_amendment_audit_v2.json")
FEATURE_RESULT_PATH = Path("data/evidence/s1_nfci_feature_result_v1.json")
FEATURE_AUDIT_PATH = Path("data/evidence/s1_nfci_feature_result_audit_v1.json")
FEATURE_DATASET_PATH = Path(
    "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
)
SOURCE_RESULT_PATH = Path("data/evidence/s1_btc_source_acquisition_result_v2.json")
SOURCE_AUDIT_PATH = Path("data/evidence/s1_btc_source_acquisition_audit_v2.json")
PRICE_DATASET_PATH = Path(
    "data/evidence/datasets/s1_1_btcusdt_friday_first_opens_v2.jsonl"
)
DEFAULT_OUTPUT = Path("data/evidence/s1_1_development_outcome_protocol_v1.json")
BUILDER_PATH = Path("scripts/freeze_s1_1_development_outcome_protocol.py")


def build_protocol(*, frozen_at: datetime) -> S11DevelopmentOutcomeProtocol:
    preregistration = S1StrategyPreregistration.model_validate_json(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    amendment = S1SourceTimingAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    amendment_audit = S1SourceTimingAmendmentAuditV2.model_validate_json(
        AMENDMENT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    feature_result = S1NfciFeatureResult.model_validate_json(
        FEATURE_RESULT_PATH.read_text(encoding="utf-8")
    )
    feature_audit = S1NfciFeatureResultAudit.model_validate_json(
        FEATURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    source_result = S1BtcSourceAcquisitionResultV2.model_validate_json(
        SOURCE_RESULT_PATH.read_text(encoding="utf-8")
    )
    source_audit = S1BtcSourceAcquisitionAuditV2.model_validate_json(
        SOURCE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        amendment.amendment_evidence_hash != amendment_audit.amendment_evidence_hash
        or feature_result.result_evidence_hash != feature_audit.result_evidence_hash
        or source_result.result_evidence_hash != source_audit.result_evidence_hash
        or source_result.decision != "PASS_S1_1_BTC_SOURCE_ACQUISITION"
        or source_result.next_authorization
        != "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_ONLY"
        or file_sha256(FEATURE_DATASET_PATH)
        != feature_result.feature_dataset_file_sha256
        or file_sha256(PRICE_DATASET_PATH) != source_result.dataset_file_sha256
    ):
        raise ValueError("S1.1 outcome protocol input lineage changed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "strategy_preregistration_file_sha256": file_sha256(PREREGISTRATION_PATH),
        "strategy_preregistration_evidence_hash": (
            preregistration.protocol_evidence_hash
        ),
        "timing_amendment_file_sha256": file_sha256(AMENDMENT_PATH),
        "timing_amendment_evidence_hash": amendment.amendment_evidence_hash,
        "timing_amendment_audit_file_sha256": file_sha256(AMENDMENT_AUDIT_PATH),
        "timing_amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
        "feature_result_file_sha256": file_sha256(FEATURE_RESULT_PATH),
        "feature_result_evidence_hash": feature_result.result_evidence_hash,
        "feature_audit_file_sha256": file_sha256(FEATURE_AUDIT_PATH),
        "feature_audit_evidence_hash": feature_audit.audit_evidence_hash,
        "feature_dataset_file_sha256": file_sha256(FEATURE_DATASET_PATH),
        "source_result_file_sha256": file_sha256(SOURCE_RESULT_PATH),
        "source_result_evidence_hash": source_result.result_evidence_hash,
        "source_audit_file_sha256": file_sha256(SOURCE_AUDIT_PATH),
        "source_audit_evidence_hash": source_audit.audit_evidence_hash,
        "price_dataset_file_sha256": file_sha256(PRICE_DATASET_PATH),
    }
    provisional = S11DevelopmentOutcomeProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S11DevelopmentOutcomeProtocol.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the S1.1 outcome protocol.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1.1 outcome protocol exists: {args.output}")
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "features_parsed=0 prices_parsed=0 returns=0 outcomes=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
