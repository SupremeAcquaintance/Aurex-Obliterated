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
    JAM_FULL_ACQUISITION_FAIL_DECISION,
    JamFullAcquisitionAudit,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    audit_jam_full_acquisition_audit,
    audit_jam_full_acquisition_protocol,
    audit_jam_full_acquisition_result,
)
from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityProtocol,
    audit_jam_archive_quality_protocol,
    build_jam_archive_quality_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PARENT_PROTOCOL = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
DEFAULT_PARENT_RESULT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/jam_archive_full_acquisition_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_quality_remediation_protocol_v1.json"
)
EXPECTED_PARENT_PROTOCOL_FILE_SHA256 = (
    "a990e2e9b7448c10531e4b4cb2d9423340ed60326e74fa9d40d0c3063fd1a4c0"
)
EXPECTED_PARENT_PROTOCOL_EVIDENCE_HASH = (
    "b27197c3b9c7e4366b3e72442206562e1ae2967931ec3fa383e59c9133bcaf74"
)
EXPECTED_PARENT_RESULT_FILE_SHA256 = (
    "d33559a1696c1e4db45b410ef25e2b72d61854a9d10c2b5403521bac12a136a6"
)
EXPECTED_PARENT_RESULT_EVIDENCE_HASH = (
    "ffe45a45bc9340e3323aac9ddd4257a19597bcee260961f787b50c8b1dee121b"
)
EXPECTED_PARENT_AUDIT_FILE_SHA256 = (
    "8a1cca59bb8c3238639bda0ed104331bdf27ef855b98b35ad4dd1d1acb881198"
)
EXPECTED_PARENT_AUDIT_EVIDENCE_HASH = (
    "d0f1d8bc4a2fe8745bf678aacdeeaeb3ef547fed49b9956dc54d36311c96e961"
)
EXPECTED_RAW_MANIFEST_HASH = (
    "362633896615d1ce287f71563b5e63c97b87a47dec4a5a8a5af5524fbbfe017d"
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
            / "freeze_jam_archive_quality_remediation_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_quality_remediation.py",
        ]
    )


def load_parent_inputs(
    *,
    protocol_path: Path,
    result_path: Path,
    audit_path: Path,
) -> tuple[
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    JamFullAcquisitionAudit,
]:
    protocol = JamFullAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = JamFullAcquisitionResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    audit = JamFullAcquisitionAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_full_acquisition_protocol(protocol)
        or not audit_jam_full_acquisition_result(result)
        or not audit_jam_full_acquisition_audit(audit)
        or file_sha256(protocol_path)
        != EXPECTED_PARENT_PROTOCOL_FILE_SHA256
        or protocol.protocol_evidence_hash
        != EXPECTED_PARENT_PROTOCOL_EVIDENCE_HASH
        or file_sha256(result_path) != EXPECTED_PARENT_RESULT_FILE_SHA256
        or result.result_evidence_hash != EXPECTED_PARENT_RESULT_EVIDENCE_HASH
        or file_sha256(audit_path) != EXPECTED_PARENT_AUDIT_FILE_SHA256
        or audit.audit_evidence_hash != EXPECTED_PARENT_AUDIT_EVIDENCE_HASH
        or audit.raw_manifest_hash != EXPECTED_RAW_MANIFEST_HASH
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.result_evidence_hash != result.result_evidence_hash
        or result.decision != JAM_FULL_ACQUISITION_FAIL_DECISION
        or result.next_required_authorization != "NONE_ACQUISITION_FAILED"
        or result.return_metrics_calculated
        or result.feature_fields_created
        or result.parameters_defined
        or result.strategy_executions
        or result.creates_candidate
        or result.creates_paper_eligibility
        or result.creates_testnet_order_authority
        or result.creates_production_authority
        or result.creates_live_eligibility
    ):
        raise ValueError("Jam quality parent lineage changed")
    return protocol, result, audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    parent_protocol: JamFullAcquisitionProtocol,
    parent_result: JamFullAcquisitionResult,
    parent_audit: JamFullAcquisitionAudit,
    parent_protocol_path: Path,
    parent_result_path: Path,
    parent_audit_path: Path,
) -> JamArchiveQualityProtocol:
    return build_jam_archive_quality_protocol(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(parent_protocol_path),
        parent_protocol_evidence_hash=parent_protocol.protocol_evidence_hash,
        parent_result_file_sha256=file_sha256(parent_result_path),
        parent_result_evidence_hash=parent_result.result_evidence_hash,
        parent_audit_file_sha256=file_sha256(parent_audit_path),
        parent_audit_evidence_hash=parent_audit.audit_evidence_hash,
        raw_manifest_hash=parent_audit.raw_manifest_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "This stage uses only the ninety-six already acquired and "
                "checksum-verified BTCUSDT archives from January 2019 through "
                "December 2022."
            ),
            (
                "The failed full-acquisition decision remains immutable; this "
                "stage may explain and remediate source policy but may not relabel "
                "the parent result as a pass."
            ),
            (
                "No network request, replacement download, alternate venue data, "
                "or new market period is permitted."
            ),
            (
                "The aggregate-trade family is only a primary-source candidate "
                "until every aggregate continuity assertion and the duplicate "
                "member identity question pass."
            ),
            (
                "The official one-minute kline family is a secondary quality "
                "reference and may not silently overwrite aggregate-trade values."
            ),
            (
                "Every missing kline minute must be enumerated and treated as an "
                "observability gap; it may not be synthesized as a tradable bar or "
                "zero-flow observation."
            ),
            (
                "Every invalid kline row and every cross-family mismatch minute "
                "must be enumerated and quarantined."
            ),
            (
                "A later feature implementation must reset state at each defect "
                "boundary and withhold eligibility for its maximum causal lookback."
            ),
            (
                "The 2019-2020 development, 2021 sealed-validation, and 2022 "
                "sealed-holdout partitions are frozen before any feature, return, "
                "or strategy calculation."
            ),
            (
                "The already consumed 2023-2025 Jam material remains contaminated "
                "and excluded from successor evaluation."
            ),
            (
                "The current 2026 exploratory and forward boundaries remain "
                "outside this historical pool and may not be accessed here."
            ),
            (
                "Market values may be inspected only to classify source defects; "
                "no directional label, feature, threshold, signal, return, PnL, "
                "ranking, or optimization may be calculated."
            ),
            (
                "This stage grants no candidate, paper, Testnet strategy-order, "
                "production, live, capital, or profit authority."
            ),
        ],
    )


def write_protocol(path: Path, protocol: JamArchiveQualityProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if JamArchiveQualityProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Jam quality protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamArchiveQualityProtocol:
    if args.output.exists():
        raise ValueError("Jam quality protocol exists; use --check")
    parent_protocol, parent_result, parent_audit = load_parent_inputs(
        protocol_path=args.parent_protocol,
        result_path=args.parent_result,
        audit_path=args.parent_audit,
    )
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"months={len(protocol.months)} returns=False network=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamArchiveQualityProtocol:
    parent_protocol, parent_result, parent_audit = load_parent_inputs(
        protocol_path=args.parent_protocol,
        result_path=args.parent_result,
        audit_path=args.parent_audit,
    )
    protocol = JamArchiveQualityProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    if protocol != expected or not audit_jam_archive_quality_protocol(protocol):
        raise ValueError("Jam quality protocol is not reproducible")
    print(
        "PASS "
        f"jam_quality_protocol={protocol.protocol_evidence_hash} "
        f"parent_result={protocol.parent_result_evidence_hash} "
        "returns=False orders=False live=False",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Jam archive remediation protocol."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--parent-protocol",
        type=Path,
        default=DEFAULT_PARENT_PROTOCOL,
    )
    parser.add_argument(
        "--parent-result",
        type=Path,
        default=DEFAULT_PARENT_RESULT,
    )
    parser.add_argument(
        "--parent-audit",
        type=Path,
        default=DEFAULT_PARENT_AUDIT,
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
