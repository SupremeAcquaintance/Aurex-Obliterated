from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_source_quality import (  # noqa: E402
    PeriodicFlowKnownSpotDisposition,
    PeriodicFlowSuccessorSourceQualityProtocol,
    PeriodicFlowSuccessorSourceQualityProtocolAudit,
    PeriodicFlowSuccessorSourceQualityResult,
    audit_hash,
    build_successor_source_quality_result,
)
from scripts.audit_periodic_flow_successor_source_quality_protocol import (  # noqa: E402
    DEFAULT_AUDIT_OUTPUT,
)
from scripts.freeze_periodic_flow_successor_source_quality import (  # noqa: E402
    DEFAULT_JAM_FULL_AUDIT,
    DEFAULT_JAM_FULL_RESULT,
    DEFAULT_JAM_REMEDIATION_AUDIT,
    DEFAULT_JAM_REMEDIATION_RESULT,
    DEFAULT_TERMINAL_AUDIT,
    DEFAULT_V1_PROTOCOL,
    file_sha256,
    load_parents,
)
from scripts.freeze_periodic_flow_successor_source_quality import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_source_quality_result_v1.json"
)


def build_dispositions(args: argparse.Namespace) -> tuple[PeriodicFlowKnownSpotDisposition, ...]:
    _, v1_protocol, jam_full, _, remediation, _ = load_parents(args)
    target_by_month = {
        item.month: item
        for item in v1_protocol.targets
        if item.product == "SPOT" and item.month <= "2022-12"
    }
    remediation_gaps = {
        month: tuple(
            item
            for item in remediation.kline_gap_intervals
            if item.month == month
            and item.classification == "PAIRED_SOURCE_OBSERVABILITY_GAP"
            and item.aggregate_covered_minute_count == 0
        )
        for month in target_by_month
    }
    dispositions: list[PeriodicFlowKnownSpotDisposition] = []
    for month_evidence in jam_full.months:
        if month_evidence.month < "2020-01":
            continue
        month = month_evidence.month
        target = target_by_month[month]
        archive = month_evidence.aggregate_trades
        duplicate_exception = month == "2021-12"
        base_structural_pass = archive.archive_pass or (
            duplicate_exception
            and remediation.duplicate_member.month == month
            and remediation.duplicate_member.archive_sha256 == archive.archive_sha256
            and remediation.duplicate_member.policy_pass
            and target.member_policy
            == "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL"
        )
        if (
            archive.archive_sha256 != target.published_archive_sha256
            or archive.archive_bytes <= 0
        ):
            raise ValueError(f"Q1 known Spot target identity changed: {month}")
        coverage = Decimal(archive.unique_minute_count) / Decimal(
            archive.expected_minute_count
        )
        gaps = remediation_gaps[month]
        maximum_event_gap = max(
            (item.missing_minute_count + 1 for item in gaps), default=1
        )
        reasons: list[str] = []
        if not base_structural_pass:
            reasons.append("SPOT_STRUCTURAL_SOURCE_FAILED")
        if coverage < Decimal("0.99"):
            reasons.append("MINUTE_COVERAGE_BELOW_0_99")
        if maximum_event_gap > 15:
            reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
        dispositions.append(
            PeriodicFlowKnownSpotDisposition(
                month=month,
                archive_sha256=archive.archive_sha256,
                archive_bytes=archive.archive_bytes,
                unique_minute_count=archive.unique_minute_count,
                expected_minute_count=archive.expected_minute_count,
                minute_coverage_fraction=coverage,
                maximum_event_gap_minutes=maximum_event_gap,
                duplicate_member_exception_applied=duplicate_exception,
                eligible_for_successor_pairing=not reasons,
                reason_codes=tuple(sorted(reasons)),
            )
        )
    return tuple(dispositions)


def authoritative_result(
    *, args: argparse.Namespace, generated_at: datetime
) -> PeriodicFlowSuccessorSourceQualityResult:
    protocol = PeriodicFlowSuccessorSourceQualityProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorSourceQualityProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_hash(protocol, "protocol_evidence_hash")
        or not audit_hash(protocol_audit, "audit_evidence_hash")
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
    ):
        raise ValueError("Q1 successor source-quality census authority changed")
    return build_successor_source_quality_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(args.protocol_audit),
        protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        known_spot_dispositions=build_dispositions(args),
        limitations=(
            "This result classifies prior Spot source quality only; it establishes no edge.",
            "Twenty-five known months qualify under structural policy, not strategy outcomes.",
            "Eleven known months are excluded whole and may not be silently restored.",
            "All twelve 2023 Spot months remain unknown and require Spot-first qualification.",
            "Maximum network counts are ceilings; they are not authorization to download.",
            "A successor acquisition protocol and execution contract must be frozen first.",
            "No market values, features, parameters, returns, signals, or trades were created.",
            "Validation and holdout outcomes remain sealed.",
            "Paper, Testnet strategy-order, production, and live authority remain false.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_result(path: Path, result: PeriodicFlowSuccessorSourceQualityResult) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor census result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor census transaction: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorSourceQualityResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 successor census result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the no-network Q1 successor source-quality census."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--terminal-audit", type=Path, default=DEFAULT_TERMINAL_AUDIT)
    parser.add_argument("--v1-protocol", type=Path, default=DEFAULT_V1_PROTOCOL)
    parser.add_argument("--jam-full-result", type=Path, default=DEFAULT_JAM_FULL_RESULT)
    parser.add_argument("--jam-full-audit", type=Path, default=DEFAULT_JAM_FULL_AUDIT)
    parser.add_argument(
        "--jam-remediation-result", type=Path, default=DEFAULT_JAM_REMEDIATION_RESULT
    )
    parser.add_argument(
        "--jam-remediation-audit", type=Path, default=DEFAULT_JAM_REMEDIATION_AUDIT
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorSourceQualityResult.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_result(args=args, generated_at=stored.generated_at)
            if stored != expected or not audit_hash(stored, "result_evidence_hash"):
                raise ValueError("Stored Q1 successor census result changed")
            print(
                f"PASS {args.output} {stored.result_evidence_hash} "
                f"eligible={stored.known_eligible_month_count} "
                f"excluded={stored.known_ineligible_month_count} requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        result = authoritative_result(args=args, generated_at=datetime.now(UTC))
        write_result(args.output, result)
        print(
            f"COMPLETE {args.output} {result.result_evidence_hash} "
            f"eligible={result.known_eligible_month_count} "
            f"excluded={result.known_ineligible_month_count} "
            f"max_network={result.maximum_successor_network_archives} "
            "requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
