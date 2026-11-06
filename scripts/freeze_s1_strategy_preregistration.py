from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureResult,
    S1NfciFeatureResultAudit,
)
from aurex.backtest_engine.s1_strategy_preregistration import (  # noqa: E402
    S1DevelopmentGate,
    S1StrategyCandidate,
    S1StrategyPreregistration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_strategy_preregistration_v1.json")
FEATURE_RESULT_PATH = Path("data/evidence/s1_nfci_feature_result_v1.json")
FEATURE_AUDIT_PATH = Path("data/evidence/s1_nfci_feature_result_audit_v1.json")
FEATURE_DATASET_PATH = Path(
    "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s1_strategy_preregistration.py")
SCRIPT_PATH = Path("scripts/freeze_s1_strategy_preregistration.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_protocol(*, frozen_at: datetime) -> S1StrategyPreregistration:
    result = S1NfciFeatureResult.model_validate_json(
        FEATURE_RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFeatureResultAudit.model_validate_json(
        FEATURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        result.decision != "PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION"
        or result.next_authorization
        != "AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
        or audit.result_file_sha256 != file_sha256(FEATURE_RESULT_PATH)
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.feature_dataset_file_sha256 != result.feature_dataset_file_sha256
        or file_sha256(FEATURE_DATASET_PATH) != result.feature_dataset_file_sha256
        or FEATURE_DATASET_PATH.stat().st_size != result.feature_dataset_bytes
    ):
        raise ValueError("S1 features do not authorize strategy preregistration")
    candidates = (
        S1StrategyCandidate(
            candidate_id="S1-C1-CONSISTENT-EASING-PRIMARY",
            role="PRIMARY_ELIGIBILITY",
            long_rule="NFCI_CHANGE_1V_LT_0_AND_NFCI_CHANGE_4V_LT_0",
            may_be_promoted=True,
        ),
        S1StrategyCandidate(
            candidate_id="S1-D1-ONE-VINTAGE-EASING",
            role="DIAGNOSTIC_ONLY",
            long_rule="NFCI_CHANGE_1V_LT_0",
            may_be_promoted=False,
        ),
        S1StrategyCandidate(
            candidate_id="S1-D2-FOUR-VINTAGE-EASING",
            role="DIAGNOSTIC_ONLY",
            long_rule="NFCI_CHANGE_4V_LT_0",
            may_be_promoted=False,
        ),
        S1StrategyCandidate(
            candidate_id="S1-D3-LOOSE-AND-FOUR-VINTAGE-EASING",
            role="DIAGNOSTIC_ONLY",
            long_rule="NFCI_LEVEL_LT_0_AND_NFCI_CHANGE_4V_LT_0",
            may_be_promoted=False,
        ),
    )
    development_gates = (
        S1DevelopmentGate(
            gate_id="EXACT_WEEKLY_INTERVAL_COUNT", operator="EQ", threshold="276"
        ),
        S1DevelopmentGate(
            gate_id="MINIMUM_POSITION_TRANSITIONS", operator="GE", threshold="20"
        ),
        S1DevelopmentGate(
            gate_id="MINIMUM_LONG_EXPOSURE_FRACTION", operator="GE", threshold="0.20"
        ),
        S1DevelopmentGate(
            gate_id="MAXIMUM_LONG_EXPOSURE_FRACTION", operator="LE", threshold="0.80"
        ),
        S1DevelopmentGate(
            gate_id="BASE_NET_TOTAL_RETURN_POSITIVE", operator="GT", threshold="0"
        ),
        S1DevelopmentGate(
            gate_id="STRESS_NET_TOTAL_RETURN_POSITIVE", operator="GT", threshold="0"
        ),
        S1DevelopmentGate(
            gate_id="BASE_PROFIT_FACTOR", operator="GE", threshold="1.10"
        ),
        S1DevelopmentGate(
            gate_id="STRESS_PROFIT_FACTOR", operator="GE", threshold="1.00"
        ),
        S1DevelopmentGate(
            gate_id="BASE_MAXIMUM_DRAWDOWN", operator="LE", threshold="0.20"
        ),
        S1DevelopmentGate(
            gate_id="STRESS_MAXIMUM_DRAWDOWN", operator="LE", threshold="0.22"
        ),
        S1DevelopmentGate(
            gate_id="POSITIVE_FULL_CALENDAR_YEARS", operator="GE", threshold="3"
        ),
        S1DevelopmentGate(
            gate_id="STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN",
            operator="GT",
            threshold="0",
        ),
    )
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "feature_result_file_sha256": file_sha256(FEATURE_RESULT_PATH),
        "feature_result_evidence_hash": result.result_evidence_hash,
        "feature_audit_file_sha256": file_sha256(FEATURE_AUDIT_PATH),
        "feature_audit_evidence_hash": audit.audit_evidence_hash,
        "feature_dataset_file_sha256": result.feature_dataset_file_sha256,
        "feature_row_manifest_evidence_hash": universe_evidence_hash(
            result.row_evidence_hashes
        ),
        "feature_decision": result.decision,
        "feature_next_authorization": result.next_authorization,
        "candidates": candidates,
        "development_gates": development_gates,
    }
    provisional = S1StrategyPreregistration.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1StrategyPreregistration.model_validate(complete)


def write_atomic(path: Path, protocol: S1StrategyPreregistration) -> None:
    if path.exists():
        raise ValueError(f"S1 preregistration exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 preregistration transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1StrategyPreregistration.model_validate_json(serialized) != protocol:
        raise ValueError("S1 preregistration did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 strategy.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1StrategyPreregistration.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 preregistration differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "candidates=4 promotable=1 feature_rows_parsed=0 btc_values=0 returns=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
