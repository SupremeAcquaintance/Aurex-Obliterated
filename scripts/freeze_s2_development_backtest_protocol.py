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
from aurex.backtest_engine.s2_btc_source_execution import (  # noqa: E402
    S2_BTC_ACQUISITION_NEXT,
    S2BtcSourceAcquisitionAudit,
)
from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2DevelopmentBacktestProtocol,
)
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2DevelopmentMeasurementResult,
    S2DevelopmentMeasurementResultAudit,
)
from aurex.backtest_engine.s2_strategy_preregistration import (  # noqa: E402
    S2StrategyPreregistration,
    S2StrategyPreregistrationAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_development_backtest_protocol_v1.json")
PREREGISTRATION_PATH = Path("data/evidence/s2_strategy_preregistration_v1.json")
PREREGISTRATION_AUDIT_PATH = Path(
    "data/evidence/s2_strategy_preregistration_audit_v1.json"
)
MEASUREMENT_RESULT_PATH = Path("data/evidence/s2_development_measurement_result_v1.json")
MEASUREMENT_AUDIT_PATH = Path(
    "data/evidence/s2_development_measurement_result_audit_v1.json"
)
MEASUREMENT_DATASET_PATH = Path("data/evidence/s2_development_measurements_v1.jsonl")
SOURCE_RESULT_PATH = Path("data/evidence/s2_btc_source_acquisition_result_v1.json")
SOURCE_AUDIT_PATH = Path("data/evidence/s2_btc_source_acquisition_audit_v1.json")
PRICE_DATASET_PATH = Path(
    "data/evidence/datasets/s2_btcusdt_monday_00h_opens_v1.jsonl"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s2_development_backtest.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "builder_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "builder_sha256": file_sha256(Path(__file__)),
        }
    )


def build_protocol(*, frozen_at: datetime) -> S2DevelopmentBacktestProtocol:
    preregistration = S2StrategyPreregistration.model_validate_json(
        rooted(PREREGISTRATION_PATH).read_text(encoding="utf-8")
    )
    preregistration_audit = S2StrategyPreregistrationAudit.model_validate_json(
        rooted(PREREGISTRATION_AUDIT_PATH).read_text(encoding="utf-8")
    )
    measurement_result = S2DevelopmentMeasurementResult.model_validate_json(
        rooted(MEASUREMENT_RESULT_PATH).read_text(encoding="utf-8")
    )
    measurement_audit = S2DevelopmentMeasurementResultAudit.model_validate_json(
        rooted(MEASUREMENT_AUDIT_PATH).read_text(encoding="utf-8")
    )
    source_audit = S2BtcSourceAcquisitionAudit.model_validate_json(
        rooted(SOURCE_AUDIT_PATH).read_text(encoding="utf-8")
    )
    if (
        preregistration_audit.protocol_evidence_hash
        != preregistration.protocol_evidence_hash
        or measurement_audit.result_evidence_hash
        != measurement_result.result_evidence_hash
        or source_audit.decision != "PASS_S2_BTC_SOURCE_ACQUISITION_AUDIT"
        or source_audit.lineage_next_authorization != S2_BTC_ACQUISITION_NEXT
        or source_audit.result_file_sha256 != file_sha256(rooted(SOURCE_RESULT_PATH))
        or source_audit.classified_target_count != 273
        or source_audit.complete_target_count != 273
        or source_audit.failed_target_count != 0
        or source_audit.price_rows_reconstructed != 273
        or preregistration.candidate_count != 1
        or preregistration.candidate.parameter_combinations != 1
        or preregistration.candidate.long_rule
        != "SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING"
        or preregistration.expected_weekly_interval_count != 272
        or len(preregistration.development_gates) != 15
        or measurement_result.measurement_row_count != 273
        or file_sha256(rooted(MEASUREMENT_DATASET_PATH))
        != measurement_result.measurement_dataset_file_sha256
        or file_sha256(rooted(PRICE_DATASET_PATH)) != source_audit.dataset_file_sha256
    ):
        raise ValueError("S2 development backtest protocol input lineage changed")
    return build_hashed(
        S2DevelopmentBacktestProtocol,
        "protocol_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "preregistration_file_sha256": file_sha256(rooted(PREREGISTRATION_PATH)),
            "preregistration_evidence_hash": preregistration.protocol_evidence_hash,
            "preregistration_audit_file_sha256": file_sha256(
                rooted(PREREGISTRATION_AUDIT_PATH)
            ),
            "preregistration_audit_evidence_hash": (
                preregistration_audit.audit_evidence_hash
            ),
            "measurement_result_file_sha256": file_sha256(
                rooted(MEASUREMENT_RESULT_PATH)
            ),
            "measurement_result_evidence_hash": measurement_result.result_evidence_hash,
            "measurement_audit_file_sha256": file_sha256(
                rooted(MEASUREMENT_AUDIT_PATH)
            ),
            "measurement_audit_evidence_hash": measurement_audit.audit_evidence_hash,
            "measurement_dataset_file_sha256": file_sha256(
                rooted(MEASUREMENT_DATASET_PATH)
            ),
            "source_result_file_sha256": file_sha256(rooted(SOURCE_RESULT_PATH)),
            "source_result_evidence_hash": source_audit.result_evidence_hash,
            "source_audit_file_sha256": file_sha256(rooted(SOURCE_AUDIT_PATH)),
            "source_audit_evidence_hash": source_audit.audit_evidence_hash,
            "price_dataset_file_sha256": file_sha256(rooted(PRICE_DATASET_PATH)),
        },
    )


def write_protocol(path: Path, protocol: S2DevelopmentBacktestProtocol) -> None:
    if path.exists():
        raise ValueError(f"S2 development backtest protocol exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2DevelopmentBacktestProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S2 development backtest protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 backtest protocol transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the S2 development backtest protocol.")
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "measurements_parsed=0 prices_parsed=0 returns=0 outcomes=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
