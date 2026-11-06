from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_transport import (  # noqa: E402
    S5GitHubTransportDecision,
    S5GitHubTransportDecisionAudit,
    audit_s5_github_transport_decision,
    audit_s5_github_transport_decision_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_bitcoin_core_github_transport_decision import (  # noqa: E402
    MODULE_PATH,
    build_decision,
    builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_DECISION = Path("data/evidence/s5_bitcoin_core_github_transport_decision_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_transport_decision_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_transport_decision.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S5GitHubTransportDecision:
    stored = S5GitHubTransportDecision.model_validate_json(path.read_text(encoding="utf-8"))
    if not audit_s5_github_transport_decision(stored):
        raise ValueError("Frozen S5 GitHub transport decision failed its evidence hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S5 GitHub transport decision builder source changed")
    if stored != build_decision(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S5 GitHub transport decision differs from reconstruction")
    return stored


def build_audit(*, decision_path: Path, audited_at: datetime) -> S5GitHubTransportDecisionAudit:
    decision = reconstruct(decision_path)
    payload = {
        "audited_at": audited_at,
        "decision_file_sha256": file_sha256(decision_path),
        "decision_evidence_hash": decision.decision_evidence_hash,
        "builder_contract_hash": decision.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "passed_gate_count": decision.passed_gate_count,
        "failed_gate_count": decision.failed_gate_count,
    }
    provisional = S5GitHubTransportDecisionAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubTransportDecisionAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubTransportDecisionAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub transport decision audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub transport audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubTransportDecisionAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub transport decision audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S5 GitHub transport decision.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubTransportDecisionAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(decision_path=args.decision, audited_at=stored.audited_at)
            if stored != expected or not audit_s5_github_transport_decision_audit(stored):
                raise ValueError("Stored S5 GitHub transport decision audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(decision_path=args.decision, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"selected={audit.selected_transport} preflight_requests=1 "
            "network=0 metadata=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
