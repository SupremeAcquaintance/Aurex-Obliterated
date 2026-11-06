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
    S4ViabilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_source_feasibility import (  # noqa: E402
    S4_FEASIBILITY_GATE_IDS,
    S4EtpSourceFeasibilityProtocol,
    S4EtpSourceFeasibilityProtocolAudit,
    audit_s4_feasibility_protocol,
    audit_s4_feasibility_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s4_etp_source_feasibility_viability_review_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s4_etp_source_feasibility_viability.py"
)
SCRIPT_PATH = Path("scripts/record_s4_etp_source_feasibility_viability.py")
PROTOCOL_PATH = Path("data/evidence/s4_etp_source_feasibility_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s4_etp_source_feasibility_protocol_audit_v1.json"
)


def reviewer_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def bindings() -> tuple[S4ViabilityBinding, ...]:
    return tuple(
        S4ViabilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(
            (PROTOCOL_PATH, PROTOCOL_AUDIT_PATH),
            key=lambda item: item.as_posix(),
        )
    )


def build_review(*, reviewed_at: datetime) -> S4EtpSourceFeasibilityViabilityReview:
    protocol = S4EtpSourceFeasibilityProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S4EtpSourceFeasibilityProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    required_unreachable = {
        "ACTUAL_PUBLICATION_TIMING_RECONSTRUCTABLE",
        "DAILY_BITCOIN_HOLDINGS_HISTORY_DESCRIPTOR_COMPLETE",
        "DAILY_SHARES_OUTSTANDING_HISTORY_DESCRIPTOR_COMPLETE",
        "FEES_SPLITS_MERGERS_AND_NON_CREATION_CHANGES_RECONSTRUCTABLE",
        "OFFICIAL_ISSUER_DATA_ENDPOINT_CATALOG_COMPLETE",
        "PER_FUND_CASH_IN_KIND_REGIME_DATES_RECONSTRUCTABLE",
    }
    if (
        not audit_s4_feasibility_protocol(protocol)
        or not audit_s4_feasibility_protocol_audit(audit)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not required_unreachable.issubset(protocol.required_gate_ids)
        or set(protocol.required_gate_ids) != set(S4_FEASIBILITY_GATE_IDS)
        or protocol.issuer_page_response_bodies_permitted is not False
        or protocol.sec_filing_document_bodies_permitted is not False
        or protocol.xbrl_fact_endpoints_permitted is not False
        or protocol.etp_numeric_values_permitted is not False
    ):
        raise ValueError("S4 viability review input or proof surface changed")
    return build_hashed(
        S4EtpSourceFeasibilityViabilityReview,
        "review_evidence_hash",
        {
            "reviewed_at": reviewed_at,
            "reviewer_contract_hash": reviewer_contract_hash(),
            "source_bindings": bindings(),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_evidence_hash": audit.audit_evidence_hash,
            "unreachable_gate_ids": tuple(sorted(required_unreachable)),
            "proof": tuple(
                sorted(
                    (
                        "Daily shares and Bitcoin history descriptors are not present "
                        "in the permitted SEC identity fields.",
                        "Exact issuer data endpoints cannot be discovered when issuer "
                        "page bodies and filing bodies are both forbidden.",
                        "Filing acceptance metadata cannot establish the publication "
                        "time of a separate issuer data record.",
                        "Per-fund cash or in-kind operating dates require filing content "
                        "that the protocol forbids.",
                        "The permitted ticker catalogs identify entities but explicitly "
                        "do not guarantee scope.",
                        "The permitted website field is only a URL and cannot prove an "
                        "official daily archive or its history.",
                        "Without issuer records, fees, splits, mergers, and non-creation "
                        "holding changes cannot be reconciled.",
                    )
                )
            ),
            "limitations": tuple(
                sorted(
                    (
                        "This review establishes a protocol-design contradiction only.",
                        "It does not establish that official ETP data is unavailable.",
                        "It does not evaluate S4 predictive edge or any return.",
                        "No network request was made and the one-run authority remains unused.",
                        "No amendment is authorized because it would change the frozen "
                        "source surface after the charter boundary.",
                        "A future distinct mechanism must freeze a reachable source path "
                        "before any request or outcome access.",
                    )
                )
            ),
        },
    )


def write_atomic(path: Path, review: S4EtpSourceFeasibilityViabilityReview) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S4 viability review: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S4 viability transaction exists: {temporary}")
    serialized = review.model_dump_json(indent=2) + "\n"
    if S4EtpSourceFeasibilityViabilityReview.model_validate_json(serialized) != review:
        raise ValueError("S4 viability review did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record or check S4 protocol viability.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--record", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S4EtpSourceFeasibilityViabilityReview.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_review(reviewed_at=stored.reviewed_at):
                raise ValueError("Stored S4 viability review differs from reconstruction")
            print(f"PASS {stored.review_evidence_hash}")
            return 0
        review = build_review(reviewed_at=datetime.now(UTC))
        write_atomic(args.output, review)
        print(
            f"RECORDED {args.output} {review.review_evidence_hash} "
            "network=0 run_consumed=false etp_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
