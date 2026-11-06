from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_feature_specification import (  # noqa: E402
    JamSuccessorFeatureSpecification,
    JamSuccessorFeatureSpecificationAudit,
    audit_jam_successor_feature_audit,
    audit_jam_successor_feature_specification,
    build_jam_successor_feature_audit,
)
from scripts.freeze_jam_successor_feature_protocol import (  # noqa: E402
    DEFAULT_CHARTER,
    DEFAULT_CONTAMINATION_LEDGER,
    DEFAULT_QUALITY_AUDIT,
    DEFAULT_QUALITY_PROTOCOL,
    DEFAULT_QUALITY_RESULT,
)
from scripts.freeze_jam_successor_feature_specification import (  # noqa: E402
    DEFAULT_PROTOCOL,
    authoritative_specification,
    load_protocol,
    specification_contract_hash,
)

DEFAULT_SPECIFICATION = Path(
    "data/evidence/jam_successor_feature_specification_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_feature_specification_audit_v1.json"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconstruct_and_verify(args) -> JamSuccessorFeatureSpecification:
    protocol = load_protocol(
        protocol_path=args.protocol,
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    specification = JamSuccessorFeatureSpecification.model_validate_json(
        args.specification.read_text(encoding="utf-8")
    )
    expected = authoritative_specification(
        frozen_at=specification.frozen_at,
        protocol=protocol,
        protocol_path=args.protocol,
    )
    if (
        specification != expected
        or not audit_jam_successor_feature_specification(specification)
        or specification.protocol_evidence_hash
        != protocol.protocol_evidence_hash
        or specification.specification_contract_hash
        != specification_contract_hash()
        or specification.real_market_rows_inspected
        or specification.future_labels_defined
        or specification.decision_thresholds_defined
        or specification.return_metrics_calculated
        or specification.strategy_executions
        or specification.creates_strategy
        or specification.creates_signal
        or specification.creates_candidate
        or specification.creates_paper_eligibility
        or specification.creates_testnet_order_authority
        or specification.creates_production_authority
        or specification.creates_live_eligibility
    ):
        raise ValueError("Jam feature specification lineage or authority changed")
    return specification


def authoritative_audit(
    *,
    audited_at: datetime,
    protocol_path: Path,
    specification_path: Path,
    specification: JamSuccessorFeatureSpecification,
) -> JamSuccessorFeatureSpecificationAudit:
    return build_jam_successor_feature_audit(
        audited_at=audited_at,
        protocol_path=protocol_path.as_posix(),
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=specification.protocol_evidence_hash,
        specification_path=specification_path.as_posix(),
        specification_file_sha256=file_sha256(specification_path),
        specification_evidence_hash=(
            specification.specification_evidence_hash
        ),
        specification_contract_hash=(
            specification.specification_contract_hash
        ),
        conformance_manifest_hash=specification.conformance_manifest_hash,
    )


def write_audit(
    path: Path,
    audit: JamSuccessorFeatureSpecificationAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorFeatureSpecificationAudit.model_validate_json(serialized)
        != audit
    ):
        raise ValueError("Jam feature audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> JamSuccessorFeatureSpecificationAudit:
    if args.output.exists():
        raise ValueError("Jam feature audit exists; use --check")
    specification = reconstruct_and_verify(args)
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        protocol_path=args.protocol,
        specification_path=args.specification,
        specification=specification,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"conformance={audit.conformance_case_count_reconstructed} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> JamSuccessorFeatureSpecificationAudit:
    specification = reconstruct_and_verify(args)
    audit = JamSuccessorFeatureSpecificationAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        protocol_path=args.protocol,
        specification_path=args.specification,
        specification=specification,
    )
    if audit != expected or not audit_jam_successor_feature_audit(audit):
        raise ValueError("Jam feature specification audit is not reproducible")
    print(
        "PASS "
        f"jam_feature_audit={audit.audit_evidence_hash} "
        f"specification={audit.specification_evidence_hash} "
        f"conformance={audit.conformance_manifest_hash} "
        "market_rows=0 returns=False",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit the frozen Jam successor feature specification."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--specification",
        type=Path,
        default=DEFAULT_SPECIFICATION,
    )
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
        run_check(args) if args.check else run_write(args)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
