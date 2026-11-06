from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (  # noqa: E402
    PeriodicFlowFullDevelopmentProtocol,
    audit_full_development_protocol,
)
from aurex.backtest_engine.periodic_flow_full_development_terminal_audit import (  # noqa: E402
    PeriodicFlowTerminalAcquisitionAudit,
    audit_terminal_acquisition_audit,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    audit_hash,
    build_successor_acquisition_protocol,
)
from aurex.backtest_engine.periodic_flow_successor_source_quality import (  # noqa: E402
    PeriodicFlowSuccessorSourceQualityResult,
    PeriodicFlowSuccessorSourceQualityResultAudit,
)

DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_source_quality_result_v1.json"
)
DEFAULT_CENSUS_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_source_quality_result_audit_v1.json"
)
DEFAULT_V1_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
DEFAULT_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_full_development_terminal_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_parents(args: argparse.Namespace):
    census = PeriodicFlowSuccessorSourceQualityResult.model_validate_json(
        args.census_result.read_text(encoding="utf-8")
    )
    census_audit = PeriodicFlowSuccessorSourceQualityResultAudit.model_validate_json(
        args.census_audit.read_text(encoding="utf-8")
    )
    v1_protocol = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
        args.v1_protocol.read_text(encoding="utf-8")
    )
    terminal = PeriodicFlowTerminalAcquisitionAudit.model_validate_json(
        args.terminal_audit.read_text(encoding="utf-8")
    )
    if (
        census.next_authorization != "FREEZE_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_ONLY"
        or not audit_hash(census, "result_evidence_hash")
        or not audit_hash(census_audit, "audit_evidence_hash")
        or census_audit.result_file_sha256 != file_sha256(args.census_result)
        or census_audit.result_evidence_hash != census.result_evidence_hash
        or not audit_full_development_protocol(v1_protocol)
        or not audit_terminal_acquisition_audit(terminal)
        or terminal.protocol_file_sha256 != file_sha256(args.v1_protocol)
        or terminal.protocol_evidence_hash != v1_protocol.protocol_evidence_hash
    ):
        raise ValueError("Q1 successor acquisition parent lineage changed")
    return census, census_audit, v1_protocol, terminal


def authoritative_protocol(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorAcquisitionProtocol:
    census, census_audit, v1_protocol, terminal = load_parents(args)
    included = set(census.known_eligible_months) | set(census.unknown_spot_first_months)
    targets = tuple(item for item in v1_protocol.targets if item.month in included)
    return build_successor_acquisition_protocol(
        frozen_at=frozen_at,
        parent_census_result_file_sha256=file_sha256(args.census_result),
        parent_census_result_evidence_hash=census.result_evidence_hash,
        parent_census_audit_file_sha256=file_sha256(args.census_audit),
        parent_census_audit_evidence_hash=census_audit.audit_evidence_hash,
        parent_v1_protocol_file_sha256=file_sha256(args.v1_protocol),
        parent_v1_protocol_evidence_hash=v1_protocol.protocol_evidence_hash,
        terminal_audit_file_sha256=file_sha256(args.terminal_audit),
        terminal_audit_evidence_hash=terminal.audit_evidence_hash,
        known_eligible_months=census.known_eligible_months,
        known_excluded_months=census.known_ineligible_months,
        unknown_spot_first_months=census.unknown_spot_first_months,
        targets=targets,
        limitations=(
            "This protocol acquires structural development sources only and cannot establish edge.",
            "Eleven known Spot-failed months are absent from the target manifest.",
            "Unknown 2023 USD-M data is conditional on its matching Spot month qualifying first.",
            "Structural source failures exclude a month and continue; integrity "
            "failures hard-stop.",
            "Excluded months may not be synthesized, interpolated, or silently restored.",
            "At least 30 paired months, six per year, and one per quarter must qualify.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet order, production, or live authority exists.",
            "The v1 terminal evidence remains immutable and is not resumed.",
            "A separate source-bound execution contract is required before any network request.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_protocol(path: Path, protocol: PeriodicFlowSuccessorAcquisitionProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor acquisition protocol: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor acquisition transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 successor acquisition protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the corrected Q1 successor acquisition protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--census-result", type=Path, default=DEFAULT_CENSUS_RESULT)
    parser.add_argument("--census-audit", type=Path, default=DEFAULT_CENSUS_AUDIT)
    parser.add_argument("--v1-protocol", type=Path, default=DEFAULT_V1_PROTOCOL)
    parser.add_argument("--terminal-audit", type=Path, default=DEFAULT_TERMINAL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_protocol(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "protocol_evidence_hash"):
                raise ValueError("Stored Q1 successor acquisition protocol changed")
            print(
                f"PASS {args.output} {stored.protocol_evidence_hash} "
                "targets=74 network_max=48 requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        protocol = authoritative_protocol(args=args, frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "targets=74 reuse=26 network_max=48 requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
