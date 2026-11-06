from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution import (  # noqa: E402
    S1BtcSourceAcquisitionResult,
)
from aurex.backtest_engine.s1_btc_source_result_audit import (  # noqa: E402
    S1BtcSourceAcquisitionAudit,
)
from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1SourceTimingAmendmentV2,
)
from aurex.backtest_engine.s1_strategy_preregistration import (  # noqa: E402
    S1StrategyPreregistration,
    S1StrategyPreregistrationAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PREREGISTRATION = Path("data/evidence/s1_strategy_preregistration_v1.json")
DEFAULT_PREREGISTRATION_AUDIT = Path(
    "data/evidence/s1_strategy_preregistration_audit_v1.json"
)
DEFAULT_FAILED_RESULT = Path("data/evidence/s1_btc_source_acquisition_result_v1.json")
DEFAULT_FAILED_AUDIT = Path("data/evidence/s1_btc_source_acquisition_audit_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_source_timing_amendment_v2.json")
BUILDER_PATH = Path("scripts/freeze_s1_source_timing_amendment_v2.py")


def build_amendment(
    *,
    preregistration_path: Path,
    preregistration_audit_path: Path,
    failed_result_path: Path,
    failed_audit_path: Path,
    frozen_at: datetime,
) -> S1SourceTimingAmendmentV2:
    preregistration = S1StrategyPreregistration.model_validate_json(
        preregistration_path.read_text(encoding="utf-8")
    )
    preregistration_audit = S1StrategyPreregistrationAudit.model_validate_json(
        preregistration_audit_path.read_text(encoding="utf-8")
    )
    failed_result = S1BtcSourceAcquisitionResult.model_validate_json(
        failed_result_path.read_text(encoding="utf-8")
    )
    failed_audit = S1BtcSourceAcquisitionAudit.model_validate_json(
        failed_audit_path.read_text(encoding="utf-8")
    )
    if (
        preregistration.protocol_evidence_hash
        != preregistration_audit.protocol_evidence_hash
        or failed_result.result_evidence_hash != failed_audit.result_evidence_hash
        or failed_result.decision
        != "STOP_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED"
        or failed_audit.diagnosed_failure != "MISSING_EXACT_00_00_UTC_TARGET_OPEN"
        or failed_result.price_rows
        or failed_result.return_metrics_calculated
    ):
        raise ValueError("S1.1 timing amendment input boundary changed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "strategy_preregistration_file_sha256": file_sha256(preregistration_path),
        "strategy_preregistration_evidence_hash": (
            preregistration.protocol_evidence_hash
        ),
        "strategy_preregistration_audit_file_sha256": file_sha256(
            preregistration_audit_path
        ),
        "strategy_preregistration_audit_evidence_hash": (
            preregistration_audit.audit_evidence_hash
        ),
        "failed_source_result_file_sha256": file_sha256(failed_result_path),
        "failed_source_result_evidence_hash": failed_result.result_evidence_hash,
        "failed_source_audit_file_sha256": file_sha256(failed_audit_path),
        "failed_source_audit_evidence_hash": failed_audit.audit_evidence_hash,
        "failed_source_decision": failed_result.decision,
    }
    provisional = S1SourceTimingAmendmentV2.model_construct(
        **payload,
        amendment_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return S1SourceTimingAmendmentV2.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the outcome-blind S1.1 timing amendment.")
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument(
        "--preregistration-audit",
        type=Path,
        default=DEFAULT_PREREGISTRATION_AUDIT,
    )
    parser.add_argument("--failed-result", type=Path, default=DEFAULT_FAILED_RESULT)
    parser.add_argument("--failed-audit", type=Path, default=DEFAULT_FAILED_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1.1 timing amendment exists: {args.output}")
    amendment = build_amendment(
        preregistration_path=args.preregistration,
        preregistration_audit_path=args.preregistration_audit,
        failed_result_path=args.failed_result,
        failed_audit_path=args.failed_audit,
        frozen_at=datetime.now(UTC),
    )
    serialized = amendment.model_dump_json(indent=2) + "\n"
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {amendment.amendment_evidence_hash} "
        "prior_prices=21 returns=0 outcomes=0 network_requests=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
