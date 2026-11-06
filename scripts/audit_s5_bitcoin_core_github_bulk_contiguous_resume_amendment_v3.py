# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5GitHubBulkContiguousResumeAmendmentAuditV3,
    S5GitHubBulkContiguousResumeAmendmentV3,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3 import (
    MODULE_PATH,
    build_amendment,
    builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256

DEFAULT_AMENDMENT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_audit_v3.json"
)
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S5GitHubBulkContiguousResumeAmendmentV3:
    stored = S5GitHubBulkContiguousResumeAmendmentV3.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not evidence_hash_valid(stored, "amendment_evidence_hash"):
        raise ValueError("Frozen S5 GitHub resume amendment failed its evidence hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S5 GitHub resume amendment builder source changed")
    if stored != build_amendment(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S5 GitHub resume amendment differs from reconstruction")
    return stored


def build_audit(
    *, amendment_path: Path, audited_at: datetime
) -> S5GitHubBulkContiguousResumeAmendmentAuditV3:
    amendment = reconstruct(amendment_path)
    payload = {
        "audited_at": audited_at,
        "amendment_file_sha256": file_sha256(amendment_path),
        "amendment_evidence_hash": amendment.amendment_evidence_hash,
        "suspension_failure_audit_evidence_hash": (
            amendment.suspension_failure_audit_evidence_hash
        ),
        "builder_contract_hash": amendment.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S5GitHubBulkContiguousResumeAmendmentAuditV3.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkContiguousResumeAmendmentAuditV3.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkContiguousResumeAmendmentAuditV3) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub resume amendment audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub resume-amendment audit exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkContiguousResumeAmendmentAuditV3.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub resume amendment audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S5 GitHub resume amendment v3.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkContiguousResumeAmendmentAuditV3.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(amendment_path=args.amendment, audited_at=stored.audited_at)
            if stored != expected or not evidence_hash_valid(stored, "audit_evidence_hash"):
                raise ValueError("Stored S5 GitHub resume amendment audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(amendment_path=args.amendment, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "additional_requests=0 preserved_pages=117 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
