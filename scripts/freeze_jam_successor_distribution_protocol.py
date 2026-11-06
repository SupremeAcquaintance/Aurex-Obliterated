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
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    audit_jam_full_acquisition_audit,
    audit_jam_full_acquisition_protocol,
    audit_jam_full_acquisition_result,
)
from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityResult,
    audit_jam_archive_quality_result,
)
from aurex.backtest_engine.jam_successor_distribution_protocol import (  # noqa: E402
    JAM_DISTRIBUTION_MONTHS,
    JamDevelopmentArchiveTarget,
    JamSuccessorDevelopmentDistributionProtocol,
    audit_jam_successor_distribution_protocol,
    build_jam_successor_distribution_protocol,
)
from aurex.backtest_engine.jam_successor_feature_protocol import (  # noqa: E402
    JamSuccessorFeatureProtocol,
    audit_jam_successor_feature_protocol,
)
from aurex.backtest_engine.jam_successor_feature_specification import (  # noqa: E402
    JAM_FEATURE_NEXT_AUTHORIZATION,
    JAM_FEATURE_PASS_DECISION,
    JamSuccessorFeatureSpecification,
    JamSuccessorFeatureSpecificationAudit,
    audit_jam_successor_feature_audit,
    audit_jam_successor_feature_specification,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_FEATURE_PROTOCOL = Path(
    "data/evidence/jam_successor_feature_specification_protocol_v1.json"
)
DEFAULT_FEATURE_SPECIFICATION = Path(
    "data/evidence/jam_successor_feature_specification_v1.json"
)
DEFAULT_FEATURE_AUDIT = Path(
    "data/evidence/jam_successor_feature_specification_audit_v1.json"
)
DEFAULT_FULL_PROTOCOL = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
DEFAULT_FULL_RESULT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_FULL_AUDIT = Path(
    "data/evidence/jam_archive_full_acquisition_audit_v1.json"
)
DEFAULT_QUALITY_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_development_distribution_protocol_v1.json"
)
EXPECTED_FEATURE_PROTOCOL_FILE_SHA256 = (
    "8f863f6db68700431c02e653dbde0dbe770e768bb8d93fa10309e67fe2e0a1e6"
)
EXPECTED_FEATURE_PROTOCOL_EVIDENCE_HASH = (
    "86ee3e67c6fc78863378b4a1b30c8cb38f9aafda2335e92054309cd260bfffba"
)
EXPECTED_FEATURE_SPEC_FILE_SHA256 = (
    "83a91e2dc1037e240e8b43122cbe8e2109f86ad4afb0f7d45b8caf9d0aef9a36"
)
EXPECTED_FEATURE_SPEC_EVIDENCE_HASH = (
    "8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701"
)
EXPECTED_FEATURE_AUDIT_FILE_SHA256 = (
    "e1d296cd9c090b783bb4179dcd9683eb10b19fdeb830215d3ba8df867eec06d9"
)
EXPECTED_FEATURE_AUDIT_EVIDENCE_HASH = (
    "760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2"
)
EXPECTED_FULL_PROTOCOL_FILE_SHA256 = (
    "a990e2e9b7448c10531e4b4cb2d9423340ed60326e74fa9d40d0c3063fd1a4c0"
)
EXPECTED_FULL_RESULT_FILE_SHA256 = (
    "d33559a1696c1e4db45b410ef25e2b72d61854a9d10c2b5403521bac12a136a6"
)
EXPECTED_FULL_AUDIT_FILE_SHA256 = (
    "8a1cca59bb8c3238639bda0ed104331bdf27ef855b98b35ad4dd1d1acb881198"
)
EXPECTED_QUALITY_RESULT_FILE_SHA256 = (
    "db1d1321598e07ba24d30aacd8b41cc28af0db186ccf4de7789a5bb2f7b18097"
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
            PROJECT_ROOT
            / "scripts"
            / "freeze_jam_successor_distribution_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_distribution_protocol.py",
        ]
    )


def development_quarantine(
    quality: JamArchiveQualityResult,
) -> list[dict[str, int | str]]:
    minutes = {
        (item.month, open_time)
        for item in quality.kline_gap_intervals
        if item.month <= "2020-12"
        for open_time in range(
            item.start_open_time_ms,
            item.end_open_time_ms + 60_000,
            60_000,
        )
    }
    minutes.update(
        (item.month, item.open_time_ms)
        for item in quality.kline_row_defects
        if item.month <= "2020-12"
    )
    minutes.update(
        (item.month, item.open_time_ms)
        for item in quality.cross_family_mismatches
        if item.month <= "2020-12"
    )
    return [
        {"month": month, "open_time_ms": open_time}
        for month, open_time in sorted(minutes)
    ]


def load_inputs(
    *,
    feature_protocol_path: Path,
    feature_specification_path: Path,
    feature_audit_path: Path,
    full_protocol_path: Path,
    full_result_path: Path,
    full_audit_path: Path,
    quality_result_path: Path,
) -> tuple[
    JamSuccessorFeatureProtocol,
    JamSuccessorFeatureSpecification,
    JamSuccessorFeatureSpecificationAudit,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    JamFullAcquisitionAudit,
    JamArchiveQualityResult,
]:
    feature_protocol = JamSuccessorFeatureProtocol.model_validate_json(
        feature_protocol_path.read_text(encoding="utf-8")
    )
    feature_specification = JamSuccessorFeatureSpecification.model_validate_json(
        feature_specification_path.read_text(encoding="utf-8")
    )
    feature_audit = JamSuccessorFeatureSpecificationAudit.model_validate_json(
        feature_audit_path.read_text(encoding="utf-8")
    )
    full_protocol = JamFullAcquisitionProtocol.model_validate_json(
        full_protocol_path.read_text(encoding="utf-8")
    )
    full_result = JamFullAcquisitionResult.model_validate_json(
        full_result_path.read_text(encoding="utf-8")
    )
    full_audit = JamFullAcquisitionAudit.model_validate_json(
        full_audit_path.read_text(encoding="utf-8")
    )
    quality_result = JamArchiveQualityResult.model_validate_json(
        quality_result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_successor_feature_protocol(feature_protocol)
        or not audit_jam_successor_feature_specification(feature_specification)
        or not audit_jam_successor_feature_audit(feature_audit)
        or not audit_jam_full_acquisition_protocol(full_protocol)
        or not audit_jam_full_acquisition_result(full_result)
        or not audit_jam_full_acquisition_audit(full_audit)
        or not audit_jam_archive_quality_result(quality_result)
        or file_sha256(feature_protocol_path)
        != EXPECTED_FEATURE_PROTOCOL_FILE_SHA256
        or feature_protocol.protocol_evidence_hash
        != EXPECTED_FEATURE_PROTOCOL_EVIDENCE_HASH
        or file_sha256(feature_specification_path)
        != EXPECTED_FEATURE_SPEC_FILE_SHA256
        or feature_specification.specification_evidence_hash
        != EXPECTED_FEATURE_SPEC_EVIDENCE_HASH
        or file_sha256(feature_audit_path)
        != EXPECTED_FEATURE_AUDIT_FILE_SHA256
        or feature_audit.audit_evidence_hash
        != EXPECTED_FEATURE_AUDIT_EVIDENCE_HASH
        or file_sha256(full_protocol_path)
        != EXPECTED_FULL_PROTOCOL_FILE_SHA256
        or file_sha256(full_result_path) != EXPECTED_FULL_RESULT_FILE_SHA256
        or file_sha256(full_audit_path) != EXPECTED_FULL_AUDIT_FILE_SHA256
        or file_sha256(quality_result_path)
        != EXPECTED_QUALITY_RESULT_FILE_SHA256
        or feature_specification.protocol_evidence_hash
        != feature_protocol.protocol_evidence_hash
        or feature_audit.specification_evidence_hash
        != feature_specification.specification_evidence_hash
        or feature_specification.decision != JAM_FEATURE_PASS_DECISION
        or feature_specification.next_required_authorization
        != JAM_FEATURE_NEXT_AUTHORIZATION
        or quality_result.result_evidence_hash
        != feature_protocol.quality_result_evidence_hash
        or full_audit.result_evidence_hash != full_result.result_evidence_hash
        or full_audit.protocol_evidence_hash
        != full_protocol.protocol_evidence_hash
        or feature_specification.real_market_rows_inspected
        or feature_specification.future_labels_defined
        or feature_specification.decision_thresholds_defined
        or feature_specification.return_metrics_calculated
        or feature_specification.strategy_executions
        or feature_specification.creates_strategy
        or feature_specification.creates_signal
        or feature_specification.creates_candidate
        or feature_specification.creates_testnet_order_authority
        or feature_specification.creates_production_authority
        or feature_specification.creates_live_eligibility
    ):
        raise ValueError("Jam distribution protocol input lineage changed")
    return (
        feature_protocol,
        feature_specification,
        feature_audit,
        full_protocol,
        full_result,
        full_audit,
        quality_result,
    )


def archive_targets(
    full_result: JamFullAcquisitionResult,
) -> list[JamDevelopmentArchiveTarget]:
    targets = []
    for month in full_result.months:
        if month.month not in JAM_DISTRIBUTION_MONTHS:
            continue
        archive = month.aggregate_trades
        if (
            not archive.checksum_verified
            or archive.duplicate_primary_key_count
            or archive.out_of_order_count
            or "AGGREGATE_OR_RAW_TRADE_ID_GAP" in archive.reason_codes
        ):
            raise ValueError(
                f"Jam development aggregate source failed: {month.month}"
            )
        targets.append(
            JamDevelopmentArchiveTarget(
                month=month.month,
                local_path=archive.local_path,
                archive_sha256=archive.archive_sha256,
                archive_bytes=archive.archive_bytes,
                csv_member_name=archive.csv_member_name,
                csv_member_bytes=archive.zip_uncompressed_bytes,
                source_row_count=archive.row_count,
                source_minute_count=archive.unique_minute_count,
                header_present=archive.header_present,
            )
        )
    return sorted(targets, key=lambda item: item.month)


def authoritative_protocol(
    *,
    frozen_at: datetime,
    inputs,
    feature_protocol_path: Path,
    feature_specification_path: Path,
    feature_audit_path: Path,
) -> JamSuccessorDevelopmentDistributionProtocol:
    feature_protocol = inputs[0]
    feature_specification = inputs[1]
    feature_audit = inputs[2]
    full_protocol = inputs[3]
    full_result = inputs[4]
    full_audit = inputs[5]
    quality_result = inputs[6]
    quarantine = development_quarantine(quality_result)
    return build_jam_successor_distribution_protocol(
        frozen_at=frozen_at,
        feature_protocol_file_sha256=file_sha256(feature_protocol_path),
        feature_protocol_evidence_hash=feature_protocol.protocol_evidence_hash,
        feature_specification_file_sha256=file_sha256(
            feature_specification_path
        ),
        feature_specification_evidence_hash=(
            feature_specification.specification_evidence_hash
        ),
        feature_audit_file_sha256=file_sha256(feature_audit_path),
        feature_audit_evidence_hash=feature_audit.audit_evidence_hash,
        full_acquisition_protocol_evidence_hash=(
            full_protocol.protocol_evidence_hash
        ),
        full_acquisition_result_evidence_hash=full_result.result_evidence_hash,
        full_acquisition_audit_evidence_hash=full_audit.audit_evidence_hash,
        full_acquisition_raw_manifest_hash=full_audit.raw_manifest_hash,
        quality_result_evidence_hash=quality_result.result_evidence_hash,
        global_quarantine_manifest_hash=(
            quality_result.quarantined_minute_manifest_hash
        ),
        development_quarantine_minute_count=len(quarantine),
        development_quarantine_manifest_hash=universe_evidence_hash(
            {"minutes": quarantine}
        ),
        builder_contract_hash=builder_contract_hash(),
        archive_targets=archive_targets(full_result),
        limitations=[
            (
                "This stage may read only the twenty-four frozen BTCUSDT aggregate-"
                "trade archives from January 2019 through December 2020."
            ),
            (
                "All archive bytes and canonical member identities must match the "
                "full-acquisition evidence before value parsing."
            ),
            (
                "The frozen seventeen-feature implementation may not be modified "
                "after seeing a development value."
            ),
            (
                "The output calendar must contain every UTC minute from 2019-01-01 "
                "through 2020-12-31, including explicit non-ready states."
            ),
            (
                "The frozen development quarantine must be applied exactly; no "
                "missing minute or source defect may be synthesized."
            ),
            (
                "Every feature row must remain inside the 2019-2020 development "
                "partition and obey the 133-minute warm-up."
            ),
            (
                "Only fixed marginal quantiles, moments, variability, monthly "
                "quality, pairwise correlation, and one-percent tail concentration "
                "may be reported."
            ),
            (
                "Correlation and tail concentration are descriptive diagnostics, "
                "not feature-selection or trade-threshold authority."
            ),
            (
                "Structural gates concern source integrity, completeness, "
                "readiness, finiteness, and feature variability only."
            ),
            (
                "No row may contain a future label, forward price, future return, "
                "trade outcome, strategy field, or PnL metric."
            ),
            (
                "The 2021 sealed-validation and 2022 sealed-holdout archives may "
                "not be opened, parsed, joined, or summarized."
            ),
            (
                "The consumed 2023-2025 and all 2026 Jam periods remain excluded."
            ),
            (
                "No event cutoff, signal conjunction, candidate parameter, entry, "
                "exit, stop, target, or sizing rule may be defined."
            ),
            (
                "The feature-row Parquet must be hash-bound, schema-checked, and "
                "contain exactly one row per development calendar minute."
            ),
            (
                "A failed structural gate stops the Jam successor before event "
                "protocol design and cannot be repaired from outcomes."
            ),
            (
                "This protocol grants no strategy, signal, candidate, paper, "
                "Testnet order, production, live, capital, or profit authority."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: JamSuccessorDevelopmentDistributionProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorDevelopmentDistributionProtocol.model_validate_json(
            serialized
        )
        != protocol
    ):
        raise ValueError("Jam distribution protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamSuccessorDevelopmentDistributionProtocol:
    if args.output.exists():
        raise ValueError("Jam distribution protocol exists; use --check")
    inputs = load_inputs(
        feature_protocol_path=args.feature_protocol,
        feature_specification_path=args.feature_specification,
        feature_audit_path=args.feature_audit,
        full_protocol_path=args.full_protocol,
        full_result_path=args.full_result,
        full_audit_path=args.full_audit,
        quality_result_path=args.quality_result,
    )
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        inputs=inputs,
        feature_protocol_path=args.feature_protocol,
        feature_specification_path=args.feature_specification,
        feature_audit_path=args.feature_audit,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"archives={len(protocol.archive_targets)} "
        f"calendar={protocol.expected_calendar_row_count} "
        f"quarantine={protocol.development_quarantine_minute_count} "
        "returns=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamSuccessorDevelopmentDistributionProtocol:
    inputs = load_inputs(
        feature_protocol_path=args.feature_protocol,
        feature_specification_path=args.feature_specification,
        feature_audit_path=args.feature_audit,
        full_protocol_path=args.full_protocol,
        full_result_path=args.full_result,
        full_audit_path=args.full_audit,
        quality_result_path=args.quality_result,
    )
    protocol = JamSuccessorDevelopmentDistributionProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=inputs,
        feature_protocol_path=args.feature_protocol,
        feature_specification_path=args.feature_specification,
        feature_audit_path=args.feature_audit,
    )
    if (
        protocol != expected
        or not audit_jam_successor_distribution_protocol(protocol)
    ):
        raise ValueError("Jam distribution protocol is not reproducible")
    print(
        "PASS "
        f"jam_distribution_protocol={protocol.protocol_evidence_hash} "
        f"targets={protocol.archive_target_manifest_hash} "
        "development=True validation=False holdout=False returns=False",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Jam development distribution protocol."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--feature-protocol",
        type=Path,
        default=DEFAULT_FEATURE_PROTOCOL,
    )
    parser.add_argument(
        "--feature-specification",
        type=Path,
        default=DEFAULT_FEATURE_SPECIFICATION,
    )
    parser.add_argument(
        "--feature-audit",
        type=Path,
        default=DEFAULT_FEATURE_AUDIT,
    )
    parser.add_argument(
        "--full-protocol",
        type=Path,
        default=DEFAULT_FULL_PROTOCOL,
    )
    parser.add_argument(
        "--full-result",
        type=Path,
        default=DEFAULT_FULL_RESULT,
    )
    parser.add_argument(
        "--full-audit",
        type=Path,
        default=DEFAULT_FULL_AUDIT,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
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
