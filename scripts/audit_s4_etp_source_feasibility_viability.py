from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s4_etp_source_feasibility_viability import (  # noqa: E402
    S4EtpSourceFeasibilityViabilityReview,
    S4EtpSourceFeasibilityViabilityReviewAudit,
    audit_s4_viability_review,
    audit_s4_viability_review_audit,
    build_hashed,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.record_s4_etp_source_feasibility_viability import (  # noqa: E402
    MODULE_PATH,
    build_review,
    reviewer_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_REVIEW = Path(
    "data/evidence/s4_etp_source_feasibility_viability_review_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s4_etp_source_feasibility_viability_review_audit_v1.json"
)
SCRIPT_PATH = Path("scripts/audit_s4_etp_source_feasibility_viability.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_audit(
    *, review_path: Path, audited_at: datetime
) -> S4EtpSourceFeasibilityViabilityReviewAudit:
    review = S4EtpSourceFeasibilityViabilityReview.model_validate_json(
        review_path.read_text(encoding="utf-8")
    )
    if (
        not audit_s4_viability_review(review)
        or review.reviewer_contract_hash != reviewer_contract_hash()
        or review != build_review(reviewed_at=review.reviewed_at)
    ):
        raise ValueError("Frozen S4 viability review changed")
    return build_hashed(
        S4EtpSourceFeasibilityViabilityReviewAudit,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "review_file_sha256": file_sha256(review_path),
            "review_evidence_hash": review.review_evidence_hash,
            "protocol_evidence_hash": review.protocol_evidence_hash,
            "protocol_audit_evidence_hash": review.protocol_audit_evidence_hash,
            "reviewer_contract_hash": review.reviewer_contract_hash,
            "auditor_contract_hash": auditor_contract_hash(),
        },
    )


def write_atomic(
    path: Path, audit: S4EtpSourceFeasibilityViabilityReviewAudit
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S4 viability audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S4 viability-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if (
        S4EtpSourceFeasibilityViabilityReviewAudit.model_validate_json(serialized)
        != audit
    ):
        raise ValueError("S4 viability review audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S4 viability review.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S4EtpSourceFeasibilityViabilityReviewAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                review_path=args.review,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_s4_viability_review_audit(stored):
                raise ValueError("Stored S4 viability audit differs from reconstruction")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(review_path=args.review, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "network=0 etp_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
