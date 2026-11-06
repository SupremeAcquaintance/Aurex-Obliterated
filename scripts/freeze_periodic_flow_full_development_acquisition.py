from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_full_acquisition import (  # noqa: E402
    JamFullAcquisitionAudit,
    JamFullAcquisitionResult,
    audit_jam_full_acquisition_audit,
    audit_jam_full_acquisition_result,
)
from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityAudit,
    JamArchiveQualityResult,
    audit_jam_archive_quality_audit,
    audit_jam_archive_quality_result,
)
from aurex.backtest_engine.periodic_flow_full_development_acquisition import (  # noqa: E402
    FULL_DEVELOPMENT_AUTHORIZATION,
    FULL_DEVELOPMENT_MONTHS,
    PeriodicFlowDevelopmentTarget,
    PeriodicFlowFullDevelopmentProtocol,
    audit_full_development_protocol,
    build_full_development_protocol,
    raw_archive_url,
    raw_reuse_path,
    spot_archive_url,
    spot_reuse_path,
)
from aurex.backtest_engine.periodic_flow_metadata_census import (  # noqa: E402
    PeriodicFlowMetadataCensusAudit,
    PeriodicFlowMetadataCensusResult,
    audit_metadata_census_audit,
    audit_metadata_census_result,
)
from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    RawTradesMetadataCensusAudit,
    RawTradesMetadataCensusResult,
    audit_raw_trades_audit,
    audit_raw_trades_result,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_evidence_v2 import (  # noqa: E402
    RawTradesPayloadPilotAuditV2,
    RawTradesPayloadPilotResultV2,
    audit_raw_payload_audit_v2,
    audit_raw_payload_result_v2,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PARENT_RESULT = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_result_v2.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_audit_v2.json"
)
DEFAULT_SPOT_CENSUS_RESULT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_result_v1.json"
)
DEFAULT_SPOT_CENSUS_AUDIT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_audit_v1.json"
)
DEFAULT_RAW_CENSUS_RESULT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_result_v1.json"
)
DEFAULT_RAW_CENSUS_AUDIT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_audit_v1.json"
)
DEFAULT_JAM_RESULT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_JAM_AUDIT = Path(
    "data/evidence/jam_archive_full_acquisition_audit_v1.json"
)
DEFAULT_REMEDIATION_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_REMEDIATION_AUDIT = Path(
    "data/evidence/jam_archive_quality_remediation_audit_v1.json"
)
DEFAULT_READINESS_RESULT = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v8.json"
)
DEFAULT_READINESS_AUDIT = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v8.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_full_development_acquisition.py"
)
SCRIPT_PATH = Path(
    "scripts/freeze_periodic_flow_full_development_acquisition.py"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_contract_hash(paths: tuple[Path, ...]) -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                path.as_posix(): file_sha256(PROJECT_ROOT / path)
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash((MODULE_PATH, SCRIPT_PATH))


def _load(path: Path, model):
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def load_inputs(
    *,
    parent_result_path: Path,
    parent_audit_path: Path,
    spot_census_result_path: Path,
    spot_census_audit_path: Path,
    raw_census_result_path: Path,
    raw_census_audit_path: Path,
    jam_result_path: Path,
    jam_audit_path: Path,
    remediation_result_path: Path,
    remediation_audit_path: Path,
    readiness_result_path: Path,
    readiness_audit_path: Path,
):
    parent = _load(parent_result_path, RawTradesPayloadPilotResultV2)
    parent_audit = _load(parent_audit_path, RawTradesPayloadPilotAuditV2)
    spot_census = _load(spot_census_result_path, PeriodicFlowMetadataCensusResult)
    spot_census_audit = _load(
        spot_census_audit_path, PeriodicFlowMetadataCensusAudit
    )
    raw_census = _load(raw_census_result_path, RawTradesMetadataCensusResult)
    raw_census_audit = _load(raw_census_audit_path, RawTradesMetadataCensusAudit)
    jam_result = _load(jam_result_path, JamFullAcquisitionResult)
    jam_audit = _load(jam_audit_path, JamFullAcquisitionAudit)
    remediation = _load(remediation_result_path, JamArchiveQualityResult)
    remediation_audit = _load(remediation_audit_path, JamArchiveQualityAudit)
    readiness = _load(readiness_result_path, StrategyFactoryReadinessResult)
    readiness_audit = _load(readiness_audit_path, StrategyFactoryReadinessAudit)
    if (
        not audit_raw_payload_result_v2(parent)
        or not audit_raw_payload_audit_v2(parent_audit)
        or parent_audit.result_file_sha256 != file_sha256(parent_result_path)
        or parent_audit.result_evidence_hash != parent.result_evidence_hash
        or not parent.authorizes_paired_full_development_acquisition_protocol
        or parent.next_authorization
        != "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL"
        or parent.authorizes_paper_operation
        or parent.authorizes_testnet_strategy_orders
        or parent.authorizes_live
        or not audit_metadata_census_result(spot_census)
        or not audit_metadata_census_audit(spot_census_audit)
        or spot_census_audit.result_file_sha256
        != file_sha256(spot_census_result_path)
        or spot_census_audit.result_evidence_hash != spot_census.result_evidence_hash
        or not audit_raw_trades_result(raw_census)
        or not audit_raw_trades_audit(raw_census_audit)
        or raw_census_audit.result_file_sha256 != file_sha256(raw_census_result_path)
        or raw_census_audit.result_evidence_hash != raw_census.result_evidence_hash
        or not audit_jam_full_acquisition_result(jam_result)
        or not audit_jam_full_acquisition_audit(jam_audit)
        or jam_audit.result_evidence_hash != jam_result.result_evidence_hash
        or not audit_jam_archive_quality_result(remediation)
        or not audit_jam_archive_quality_audit(remediation_audit)
        or remediation_audit.result_evidence_hash
        != remediation.result_evidence_hash
        or not remediation.aggregate_primary_source_qualified
        or remediation.duplicate_member_policy
        != "TOP_LEVEL_CANONICAL_ONLY_WHEN_BYTE_IDENTICAL"
        or not remediation.duplicate_member.byte_identical
        or remediation.duplicate_member.month != "2021-12"
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_file_sha256 != file_sha256(readiness_result_path)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or not readiness.strategy_research_ready
        or readiness.strategy_candidates_created != 0
        or readiness.orders_submitted != 0
    ):
        raise ValueError("Q1 full-development parent lineage changed")
    return (
        parent,
        parent_audit,
        spot_census,
        spot_census_audit,
        raw_census,
        raw_census_audit,
        jam_result,
        jam_audit,
        remediation,
        remediation_audit,
        readiness,
        readiness_audit,
    )


def acquisition_targets(
    *,
    parent: RawTradesPayloadPilotResultV2,
    spot_census: PeriodicFlowMetadataCensusResult,
    raw_census: RawTradesMetadataCensusResult,
    jam_result: JamFullAcquisitionResult,
    remediation: JamArchiveQualityResult,
) -> tuple[PeriodicFlowDevelopmentTarget, ...]:
    spot_records = {
        record.month: record
        for record in spot_census.records
        if record.product == "SPOT" and record.partition_role == "DEVELOPMENT"
    }
    raw_records = {
        record.month: record
        for record in raw_census.records
        if record.partition_role == "DEVELOPMENT"
    }
    jam_spot = {
        month.month: month.aggregate_trades
        for month in jam_result.months
        if "2020-01" <= month.month <= "2022-12"
    }
    if (
        set(spot_records) != set(FULL_DEVELOPMENT_MONTHS)
        or set(raw_records) != set(FULL_DEVELOPMENT_MONTHS)
        or set(jam_spot) != set(FULL_DEVELOPMENT_MONTHS[:36])
    ):
        raise ValueError("Q1 full-development source matrix changed")
    targets: list[PeriodicFlowDevelopmentTarget] = []
    for month in FULL_DEVELOPMENT_MONTHS:
        spot = spot_records[month]
        raw = raw_records[month]
        if (
            spot.archive_sha256 is None
            or raw.archive_sha256 is None
            or spot.archive_url != spot_archive_url(month)
            or raw.archive_url != raw_archive_url(month)
        ):
            raise ValueError(f"Q1 development checksum unavailable for {month}")
        spot_path = spot_reuse_path(month)
        if spot_path is not None:
            if month == "2020-01":
                if (
                    parent.qualified_spot_archive_sha256 != spot.archive_sha256
                    or not parent.qualified_spot_archive_reverified
                ):
                    raise ValueError("Q1 qualified Spot pilot changed")
            else:
                evidence = jam_spot[month]
                accepted = evidence.archive_pass or (
                    month == "2021-12"
                    and remediation.duplicate_member.policy_pass
                    and remediation.duplicate_member.archive_sha256
                    == evidence.archive_sha256
                )
                if (
                    not accepted
                    or evidence.archive_sha256 != spot.archive_sha256
                    or evidence.local_path != spot_path
                ):
                    raise ValueError(f"Q1 Spot reuse lineage changed for {month}")
        targets.append(
            PeriodicFlowDevelopmentTarget(
                product="SPOT",
                family="aggTrades",
                month=month,
                archive_url=spot.archive_url,
                published_archive_sha256=spot.archive_sha256,
                expected_member_name=f"BTCUSDT-aggTrades-{month}.csv",
                expected_columns=(
                    "aggregate_trade_id",
                    "price",
                    "quantity",
                    "first_trade_id",
                    "last_trade_id",
                    "transact_time",
                    "is_buyer_maker",
                    "is_best_match",
                ),
                reuse_candidate_path=spot_path,
                reuse_candidate_file_sha256=(
                    spot.archive_sha256 if spot_path is not None else None
                ),
                member_policy=(
                    "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL"
                    if month == "2021-12"
                    else "EXACT_EXPECTED_MEMBER_ONLY"
                ),
            )
        )
        raw_path = raw_reuse_path(month)
        if raw_path is not None and (
            parent.raw_archive_evidence.archive_sha256 != raw.archive_sha256
            or not parent.raw_archive_evidence.archive_pass
        ):
            raise ValueError("Q1 qualified raw pilot changed")
        targets.append(
            PeriodicFlowDevelopmentTarget(
                product="USD_M_PERPETUAL",
                family="trades",
                month=month,
                archive_url=raw.archive_url,
                published_archive_sha256=raw.archive_sha256,
                expected_member_name=f"BTCUSDT-trades-{month}.csv",
                expected_columns=(
                    "trade_id",
                    "price",
                    "quantity",
                    "quote_quantity",
                    "timestamp",
                    "buyer_was_maker",
                ),
                reuse_candidate_path=raw_path,
                reuse_candidate_file_sha256=(
                    raw.archive_sha256 if raw_path is not None else None
                ),
                member_policy="EXACT_EXPECTED_MEMBER_ONLY",
            )
        )
    return tuple(sorted(targets, key=lambda item: item.key))


def authoritative_protocol(
    *,
    frozen_at: datetime,
    parent_result_path: Path = DEFAULT_PARENT_RESULT,
    parent_audit_path: Path = DEFAULT_PARENT_AUDIT,
    spot_census_result_path: Path = DEFAULT_SPOT_CENSUS_RESULT,
    spot_census_audit_path: Path = DEFAULT_SPOT_CENSUS_AUDIT,
    raw_census_result_path: Path = DEFAULT_RAW_CENSUS_RESULT,
    raw_census_audit_path: Path = DEFAULT_RAW_CENSUS_AUDIT,
    jam_result_path: Path = DEFAULT_JAM_RESULT,
    jam_audit_path: Path = DEFAULT_JAM_AUDIT,
    remediation_result_path: Path = DEFAULT_REMEDIATION_RESULT,
    remediation_audit_path: Path = DEFAULT_REMEDIATION_AUDIT,
    readiness_result_path: Path = DEFAULT_READINESS_RESULT,
    readiness_audit_path: Path = DEFAULT_READINESS_AUDIT,
) -> PeriodicFlowFullDevelopmentProtocol:
    loaded = load_inputs(
        parent_result_path=parent_result_path,
        parent_audit_path=parent_audit_path,
        spot_census_result_path=spot_census_result_path,
        spot_census_audit_path=spot_census_audit_path,
        raw_census_result_path=raw_census_result_path,
        raw_census_audit_path=raw_census_audit_path,
        jam_result_path=jam_result_path,
        jam_audit_path=jam_audit_path,
        remediation_result_path=remediation_result_path,
        remediation_audit_path=remediation_audit_path,
        readiness_result_path=readiness_result_path,
        readiness_audit_path=readiness_audit_path,
    )
    (
        parent,
        parent_audit,
        spot_census,
        spot_census_audit,
        raw_census,
        raw_census_audit,
        jam_result,
        jam_audit,
        remediation,
        remediation_audit,
        readiness,
        readiness_audit,
    ) = loaded
    targets = acquisition_targets(
        parent=parent,
        spot_census=spot_census,
        raw_census=raw_census,
        jam_result=jam_result,
        remediation=remediation,
    )
    return build_full_development_protocol(
        frozen_at=frozen_at,
        parent_result_file_sha256=file_sha256(parent_result_path),
        parent_result_evidence_hash=parent.result_evidence_hash,
        parent_audit_file_sha256=file_sha256(parent_audit_path),
        parent_audit_evidence_hash=parent_audit.audit_evidence_hash,
        spot_census_result_file_sha256=file_sha256(spot_census_result_path),
        spot_census_result_evidence_hash=spot_census.result_evidence_hash,
        spot_census_audit_file_sha256=file_sha256(spot_census_audit_path),
        spot_census_audit_evidence_hash=spot_census_audit.audit_evidence_hash,
        raw_census_result_file_sha256=file_sha256(raw_census_result_path),
        raw_census_result_evidence_hash=raw_census.result_evidence_hash,
        raw_census_audit_file_sha256=file_sha256(raw_census_audit_path),
        raw_census_audit_evidence_hash=raw_census_audit.audit_evidence_hash,
        jam_acquisition_result_file_sha256=file_sha256(jam_result_path),
        jam_acquisition_result_evidence_hash=jam_result.result_evidence_hash,
        jam_acquisition_audit_file_sha256=file_sha256(jam_audit_path),
        jam_acquisition_audit_evidence_hash=jam_audit.audit_evidence_hash,
        jam_remediation_result_file_sha256=file_sha256(remediation_result_path),
        jam_remediation_result_evidence_hash=remediation.result_evidence_hash,
        jam_remediation_audit_file_sha256=file_sha256(remediation_audit_path),
        jam_remediation_audit_evidence_hash=remediation_audit.audit_evidence_hash,
        readiness_result_evidence_hash=readiness.result_evidence_hash,
        readiness_audit_evidence_hash=readiness_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        targets=targets,
        next_authorization=FULL_DEVELOPMENT_AUTHORIZATION,
        limitations=(
            "A protocol pass authorizes archive acquisition, not a successful acquisition.",
            "All 37 local candidates require fresh checksum and structural revalidation.",
            "At most 59 archives may require network payload requests.",
            "Development covers 2020-01 through 2023-12 only.",
            "Forward raw-ID omissions remain measured against the frozen pilot gates.",
            "Partial archive bytes are discarded and never resumed or parsed.",
            "Price, quantity, quote quantity, features, and outcomes remain unopened.",
            "Spot 2021-12 uses the top-level member only after byte-identity proof.",
            "Validation, holdout, and forward outcomes remain sealed.",
            "No threshold, signal, strategy, or candidate is created.",
            "Paper and Testnet strategy-order authority remain false.",
            "Production, live, real-capital authority, and profit remain false.",
        ),
    )


def write_protocol(path: Path, protocol: PeriodicFlowFullDevelopmentProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowFullDevelopmentProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 full-development protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale protocol transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Q1 paired full-development acquisition protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_protocol(frozen_at=stored.frozen_at)
            if stored != expected or not audit_full_development_protocol(stored):
                raise ValueError("Stored Q1 full-development protocol changed")
            print(
                f"PASS {args.output} {stored.protocol_evidence_hash} "
                "targets=96 reuse=37 network=59 requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        if args.output.exists():
            raise ValueError(f"Refusing to overwrite frozen protocol: {args.output}")
        protocol = authoritative_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "targets=96 reuse=37 network=59 requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
