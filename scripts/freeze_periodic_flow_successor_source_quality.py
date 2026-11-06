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
    PeriodicFlowFullDevelopmentProtocol,
    audit_full_development_protocol,
)
from aurex.backtest_engine.periodic_flow_full_development_terminal_audit import (  # noqa: E402
    PeriodicFlowTerminalAcquisitionAudit,
    audit_terminal_acquisition_audit,
)
from aurex.backtest_engine.periodic_flow_successor_source_quality import (  # noqa: E402
    PeriodicFlowSuccessorSourceQualityProtocol,
    audit_hash,
    build_successor_source_quality_protocol,
)

DEFAULT_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_full_development_terminal_audit_v1.json"
)
DEFAULT_V1_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
DEFAULT_JAM_FULL_RESULT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_JAM_FULL_AUDIT = Path(
    "data/evidence/jam_archive_full_acquisition_audit_v1.json"
)
DEFAULT_JAM_REMEDIATION_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_JAM_REMEDIATION_AUDIT = Path(
    "data/evidence/jam_archive_quality_remediation_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_source_quality_protocol_v1.json"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_parents(args: argparse.Namespace):
    terminal = PeriodicFlowTerminalAcquisitionAudit.model_validate_json(
        args.terminal_audit.read_text(encoding="utf-8")
    )
    v1_protocol = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
        args.v1_protocol.read_text(encoding="utf-8")
    )
    jam_full = JamFullAcquisitionResult.model_validate_json(
        args.jam_full_result.read_text(encoding="utf-8")
    )
    jam_full_audit = JamFullAcquisitionAudit.model_validate_json(
        args.jam_full_audit.read_text(encoding="utf-8")
    )
    remediation = JamArchiveQualityResult.model_validate_json(
        args.jam_remediation_result.read_text(encoding="utf-8")
    )
    remediation_audit = JamArchiveQualityAudit.model_validate_json(
        args.jam_remediation_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_terminal_acquisition_audit(terminal)
        or terminal.next_authorization
        != "FREEZE_Q1_SUCCESSOR_SOURCE_QUALITY_CENSUS_PROTOCOL_ONLY"
        or not audit_full_development_protocol(v1_protocol)
        or terminal.protocol_file_sha256 != file_sha256(args.v1_protocol)
        or terminal.protocol_evidence_hash != v1_protocol.protocol_evidence_hash
        or not audit_jam_full_acquisition_result(jam_full)
        or not audit_jam_full_acquisition_audit(jam_full_audit)
        or jam_full_audit.result_file_sha256 != file_sha256(args.jam_full_result)
        or jam_full_audit.result_evidence_hash != jam_full.result_evidence_hash
        or not audit_jam_archive_quality_result(remediation)
        or not audit_jam_archive_quality_audit(remediation_audit)
        or remediation_audit.result_file_sha256
        != file_sha256(args.jam_remediation_result)
        or remediation_audit.result_evidence_hash != remediation.result_evidence_hash
    ):
        raise ValueError("Q1 successor source-quality parent lineage changed")
    return terminal, v1_protocol, jam_full, jam_full_audit, remediation, remediation_audit


def authoritative_protocol(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorSourceQualityProtocol:
    terminal, v1_protocol, jam_full, jam_full_audit, remediation, remediation_audit = (
        load_parents(args)
    )
    return build_successor_source_quality_protocol(
        frozen_at=frozen_at,
        parent_terminal_audit_file_sha256=file_sha256(args.terminal_audit),
        parent_terminal_audit_evidence_hash=terminal.audit_evidence_hash,
        parent_v1_protocol_file_sha256=file_sha256(args.v1_protocol),
        parent_v1_protocol_evidence_hash=v1_protocol.protocol_evidence_hash,
        jam_full_result_file_sha256=file_sha256(args.jam_full_result),
        jam_full_result_evidence_hash=jam_full.result_evidence_hash,
        jam_full_audit_file_sha256=file_sha256(args.jam_full_audit),
        jam_full_audit_evidence_hash=jam_full_audit.audit_evidence_hash,
        jam_remediation_result_file_sha256=file_sha256(args.jam_remediation_result),
        jam_remediation_result_evidence_hash=remediation.result_evidence_hash,
        jam_remediation_audit_file_sha256=file_sha256(args.jam_remediation_audit),
        jam_remediation_audit_evidence_hash=remediation_audit.audit_evidence_hash,
        limitations=(
            "This protocol adjudicates source sufficiency only and cannot establish edge.",
            "Known 2020-2022 decisions must come only from prior independently audited evidence.",
            "Unknown 2023 Spot quality remains unresolved until a successor acquisition runs.",
            "A matching USD-M archive may be requested only after its Spot month qualifies.",
            "Failed months are excluded whole; missing minutes may not be synthesized.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet order, production, or live authority exists.",
            "The v1 terminal result, checkpoint, protocol, and runner remain immutable.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_protocol(path: Path, protocol: PeriodicFlowSuccessorSourceQualityProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor protocol: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorSourceQualityProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 successor protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the no-network Q1 successor source-quality census protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorSourceQualityProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_protocol(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "protocol_evidence_hash"):
                raise ValueError("Stored Q1 successor protocol changed")
            print(
                f"PASS {args.output} {stored.protocol_evidence_hash} "
                "requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        protocol = authoritative_protocol(args=args, frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
