from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_metadata_census import (  # noqa: E402
    PeriodicFlowMetadataCensusAudit,
    PeriodicFlowMetadataCensusResult,
    audit_metadata_census_audit,
    audit_metadata_census_result,
    build_metadata_census_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_metadata_census_contract import (  # noqa: E402
    MODULE_PATH,
    builder_contract_hash,
    file_sha256,
)
from scripts.run_periodic_flow_metadata_census import (  # noqa: E402
    DEFAULT_CONTRACT,
    authoritative_result,
    load_contract,
    runner_contract_hash,
)
from scripts.run_periodic_flow_metadata_census import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RESULT,
)

DEFAULT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path("scripts/audit_periodic_flow_metadata_census.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                MODULE_PATH.as_posix(): file_sha256(PROJECT_ROOT / MODULE_PATH),
                AUDIT_SCRIPT_PATH.as_posix(): file_sha256(
                    PROJECT_ROOT / AUDIT_SCRIPT_PATH
                ),
            }
        }
    )


def reconstruct_result(
    *,
    contract_path: Path,
    result_path: Path,
) -> PeriodicFlowMetadataCensusResult:
    contract = load_contract(contract_path)
    stored = PeriodicFlowMetadataCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_metadata_census_result(stored)
        or stored.contract_file_sha256 != file_sha256(contract_path)
        or stored.contract_evidence_hash != contract.contract_evidence_hash
        or stored.runner_contract_hash != runner_contract_hash()
        or contract.builder_contract_hash != builder_contract_hash()
    ):
        raise ValueError("Q1 census result lineage changed")
    reconstructed = authoritative_result(
        generated_at=stored.generated_at,
        contract_path=contract_path,
        contract=contract,
        records=stored.records,
    )
    if reconstructed != stored:
        raise ValueError("Q1 census result differs from exact reconstruction")
    return stored


def authoritative_audit(
    *,
    audited_at: datetime,
    contract_path: Path,
    result_path: Path,
) -> PeriodicFlowMetadataCensusAudit:
    contract = load_contract(contract_path)
    result = reconstruct_result(
        contract_path=contract_path,
        result_path=result_path,
    )
    return build_metadata_census_audit(
        audited_at=audited_at,
        contract_file_sha256=file_sha256(contract_path),
        contract_evidence_hash=contract.contract_evidence_hash,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        builder_contract_hash=contract.builder_contract_hash,
        runner_contract_hash=result.runner_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
        present_count=result.summary.present_count,
        paired_present_month_count=result.summary.paired_present_month_count,
        checksum_get_requests_made=result.checksum_get_requests_made,
        decision=result.decision,
        next_authorization=result.next_authorization,
    )


def write_audit(
    path: Path,
    audit: PeriodicFlowMetadataCensusAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowMetadataCensusAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 census audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 census audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct or verify the Q1 metadata census."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowMetadataCensusAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                audited_at=stored.audited_at,
                contract_path=args.contract,
                result_path=args.result,
            )
            if stored != expected or not audit_metadata_census_audit(stored):
                raise ValueError("Stored Q1 census audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite Q1 census audit: {args.output}")
        audit = authoritative_audit(
            audited_at=datetime.now(UTC),
            contract_path=args.contract,
            result_path=args.result,
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"present={audit.present_count}/144 "
            f"paired={audit.paired_present_month_count}/72 "
            f"decision={audit.decision} payload_requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
