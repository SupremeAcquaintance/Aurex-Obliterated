from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.contamination import (  # noqa: E402
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JAM_QUALITY_NEXT_AUTHORIZATION,
    JAM_QUALITY_PASS_DECISION,
    JamArchiveQualityAudit,
    JamArchiveQualityProtocol,
    JamArchiveQualityResult,
    audit_jam_archive_quality_audit,
    audit_jam_archive_quality_protocol,
    audit_jam_archive_quality_result,
)
from aurex.backtest_engine.jam_successor_charter import (  # noqa: E402
    JAM_SELECTED_PROPOSAL_ID,
    JamSuccessorHypothesisCharter,
    audit_jam_successor_hypothesis_charter,
)
from aurex.backtest_engine.jam_successor_feature_protocol import (  # noqa: E402
    JamSuccessorFeatureProtocol,
    audit_jam_successor_feature_protocol,
    build_jam_successor_feature_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_CHARTER = Path(
    "data/evidence/jam_successor_hypothesis_charter_v1.json"
)
DEFAULT_QUALITY_PROTOCOL = Path(
    "data/evidence/jam_archive_quality_remediation_protocol_v1.json"
)
DEFAULT_QUALITY_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_QUALITY_AUDIT = Path(
    "data/evidence/jam_archive_quality_remediation_audit_v1.json"
)
DEFAULT_CONTAMINATION_LEDGER = Path(
    "data/evidence/strategy_contamination_ledger_v2.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_feature_specification_protocol_v1.json"
)
EXPECTED_CHARTER_FILE_SHA256 = (
    "910dfc7c2292f457f97355d36f7c6a2151d59b76bea12ac9c903b0240b03cccd"
)
EXPECTED_CHARTER_EVIDENCE_HASH = (
    "426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019"
)
EXPECTED_QUALITY_PROTOCOL_FILE_SHA256 = (
    "aa48c6342792f2d34777f4dce5773619455911607d7132e32e5a3a3121ffb95e"
)
EXPECTED_QUALITY_PROTOCOL_EVIDENCE_HASH = (
    "128eb77a416ba9ebd47154639fe383f1f9b9c0058c149c8f7dc62c4e5e24c57a"
)
EXPECTED_QUALITY_RESULT_FILE_SHA256 = (
    "db1d1321598e07ba24d30aacd8b41cc28af0db186ccf4de7789a5bb2f7b18097"
)
EXPECTED_QUALITY_RESULT_EVIDENCE_HASH = (
    "02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c"
)
EXPECTED_QUALITY_AUDIT_FILE_SHA256 = (
    "e3b880637f65d73a35f4dd8c56a824f571223a586756346d97c3d80399890c8f"
)
EXPECTED_QUALITY_AUDIT_EVIDENCE_HASH = (
    "146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48"
)
EXPECTED_CONTAMINATION_LEDGER_FILE_SHA256 = (
    "69890df964ea4a293180d465f2e4dea68ab22f9f7124835092411ad9381186b1"
)
EXPECTED_CONTAMINATION_LEDGER_EVIDENCE_HASH = (
    "f24cc36011e9f9ddc40e277197bd3fa03310cac12b6848b30714aae26cdb37bd"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_jam_successor_feature_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_feature_protocol.py",
        ]
    )


def load_inputs(
    *,
    charter_path: Path,
    quality_protocol_path: Path,
    quality_result_path: Path,
    quality_audit_path: Path,
    contamination_ledger_path: Path,
) -> tuple[
    JamSuccessorHypothesisCharter,
    JamArchiveQualityProtocol,
    JamArchiveQualityResult,
    JamArchiveQualityAudit,
    StrategyContaminationLedger,
]:
    charter = JamSuccessorHypothesisCharter.model_validate_json(
        charter_path.read_text(encoding="utf-8")
    )
    quality_protocol = JamArchiveQualityProtocol.model_validate_json(
        quality_protocol_path.read_text(encoding="utf-8")
    )
    quality_result = JamArchiveQualityResult.model_validate_json(
        quality_result_path.read_text(encoding="utf-8")
    )
    quality_audit = JamArchiveQualityAudit.model_validate_json(
        quality_audit_path.read_text(encoding="utf-8")
    )
    contamination = StrategyContaminationLedger.model_validate_json(
        contamination_ledger_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_successor_hypothesis_charter(charter)
        or not audit_jam_archive_quality_protocol(quality_protocol)
        or not audit_jam_archive_quality_result(quality_result)
        or not audit_jam_archive_quality_audit(quality_audit)
        or not audit_contamination_ledger(contamination)
        or file_sha256(charter_path) != EXPECTED_CHARTER_FILE_SHA256
        or charter.charter_evidence_hash != EXPECTED_CHARTER_EVIDENCE_HASH
        or file_sha256(quality_protocol_path)
        != EXPECTED_QUALITY_PROTOCOL_FILE_SHA256
        or quality_protocol.protocol_evidence_hash
        != EXPECTED_QUALITY_PROTOCOL_EVIDENCE_HASH
        or file_sha256(quality_result_path)
        != EXPECTED_QUALITY_RESULT_FILE_SHA256
        or quality_result.result_evidence_hash
        != EXPECTED_QUALITY_RESULT_EVIDENCE_HASH
        or file_sha256(quality_audit_path)
        != EXPECTED_QUALITY_AUDIT_FILE_SHA256
        or quality_audit.audit_evidence_hash
        != EXPECTED_QUALITY_AUDIT_EVIDENCE_HASH
        or file_sha256(contamination_ledger_path)
        != EXPECTED_CONTAMINATION_LEDGER_FILE_SHA256
        or contamination.ledger_evidence_hash
        != EXPECTED_CONTAMINATION_LEDGER_EVIDENCE_HASH
        or charter.selected_proposal_id != JAM_SELECTED_PROPOSAL_ID
        or quality_result.decision != JAM_QUALITY_PASS_DECISION
        or quality_result.next_required_authorization
        != JAM_QUALITY_NEXT_AUTHORIZATION
        or quality_result.protocol_evidence_hash
        != quality_protocol.protocol_evidence_hash
        or quality_audit.result_evidence_hash
        != quality_result.result_evidence_hash
        or quality_result.return_metrics_calculated
        or quality_result.feature_fields_created
        or quality_result.parameters_defined
        or quality_result.thresholds_defined
        or quality_result.strategy_executions
        or quality_result.creates_candidate
        or quality_result.creates_paper_eligibility
        or quality_result.creates_testnet_order_authority
        or quality_result.creates_production_authority
        or quality_result.creates_live_eligibility
    ):
        raise ValueError("Jam feature specification input lineage changed")
    return (
        charter,
        quality_protocol,
        quality_result,
        quality_audit,
        contamination,
    )


def authoritative_protocol(
    *,
    frozen_at: datetime,
    charter: JamSuccessorHypothesisCharter,
    quality_protocol: JamArchiveQualityProtocol,
    quality_result: JamArchiveQualityResult,
    quality_audit: JamArchiveQualityAudit,
    contamination: StrategyContaminationLedger,
    charter_path: Path,
    quality_protocol_path: Path,
    quality_result_path: Path,
    quality_audit_path: Path,
    contamination_ledger_path: Path,
) -> JamSuccessorFeatureProtocol:
    return build_jam_successor_feature_protocol(
        frozen_at=frozen_at,
        parent_charter_file_sha256=file_sha256(charter_path),
        parent_charter_evidence_hash=charter.charter_evidence_hash,
        quality_protocol_file_sha256=file_sha256(quality_protocol_path),
        quality_protocol_evidence_hash=quality_protocol.protocol_evidence_hash,
        quality_result_file_sha256=file_sha256(quality_result_path),
        quality_result_evidence_hash=quality_result.result_evidence_hash,
        quality_audit_file_sha256=file_sha256(quality_audit_path),
        quality_audit_evidence_hash=quality_audit.audit_evidence_hash,
        contamination_ledger_file_sha256=file_sha256(
            contamination_ledger_path
        ),
        contamination_ledger_evidence_hash=(
            contamination.ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        quarantine_manifest_hash=(
            quality_result.quarantined_minute_manifest_hash
        ),
        limitations=[
            (
                "This stage may define causal feature transformations and "
                "lookbacks but may not inspect any real archive payload value."
            ),
            (
                "Only the eight frozen Binance aggregate-trade fields and the "
                "already audited quality manifest may inform the specification."
            ),
            (
                "Buyer-maker semantics must be explicit and proven with synthetic "
                "fixtures before any real-data feature generation."
            ),
            (
                "All windows must use observations available no later than the "
                "close of the evaluation minute."
            ),
            (
                "Baseline, pre-shock, shock, and confirmation phases must be "
                "non-overlapping and may not exceed four temporal phases."
            ),
            (
                "At most twenty-four output features and a maximum 240-minute "
                "lookback may be specified."
            ),
            (
                "The specification may use mathematically conventional "
                "normalization constants but may not define a trade threshold."
            ),
            (
                "No future return, directional label, profit field, or outcome "
                "join may be defined or calculated."
            ),
            (
                "Every source defect must reset state and require the complete "
                "maximum feature lookback before a row can become feature-ready."
            ),
            (
                "Development, validation, and holdout boundaries must each reset "
                "state; no rolling value may cross a partition boundary."
            ),
            (
                "Official klines remain QA-only and may not supply or overwrite a "
                "primary aggregate-trade feature value."
            ),
            (
                "Synthetic fixtures may contain at most one thousand rows and "
                "must not embed copied market values or strategy outcomes."
            ),
            (
                "Exact Pine parity is unavailable; the future backend may be the "
                "signal authority only after later evidence gates pass."
            ),
            (
                "This protocol grants no strategy, signal, candidate, paper, "
                "Testnet strategy-order, production, live, capital, or profit "
                "authority."
            ),
        ],
    )


def write_protocol(path: Path, protocol: JamSuccessorFeatureProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if JamSuccessorFeatureProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Jam feature protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamSuccessorFeatureProtocol:
    if args.output.exists():
        raise ValueError("Jam feature protocol exists; use --check")
    inputs = load_inputs(
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        charter=inputs[0],
        quality_protocol=inputs[1],
        quality_result=inputs[2],
        quality_audit=inputs[3],
        contamination=inputs[4],
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"max_features={protocol.maximum_feature_count} "
        f"max_lookback={protocol.maximum_lookback_minutes} returns=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamSuccessorFeatureProtocol:
    inputs = load_inputs(
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    protocol = JamSuccessorFeatureProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        charter=inputs[0],
        quality_protocol=inputs[1],
        quality_result=inputs[2],
        quality_audit=inputs[3],
        contamination=inputs[4],
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    if protocol != expected or not audit_jam_successor_feature_protocol(protocol):
        raise ValueError("Jam feature protocol is not reproducible")
    print(
        "PASS "
        f"jam_feature_protocol={protocol.protocol_evidence_hash} "
        f"quality={protocol.quality_result_evidence_hash} "
        "market_payload=False thresholds=False returns=False orders=False",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Jam successor feature protocol."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--quality-protocol",
        type=Path,
        default=DEFAULT_QUALITY_PROTOCOL,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument(
        "--quality-audit",
        type=Path,
        default=DEFAULT_QUALITY_AUDIT,
    )
    parser.add_argument(
        "--contamination-ledger",
        type=Path,
        default=DEFAULT_CONTAMINATION_LEDGER,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_check(args) if args.check else run_freeze(args)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
