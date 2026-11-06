from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5GitHubNormalizationExecutionContract,
    S5GitHubNormalizationExecutionContractAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CONTRACT,
)
from scripts.freeze_s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    build_contract,
    file_sha256,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_audit_v1.json"
)
AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_normalization_execution.py"
)


def build_audit(
    *, contract_path: Path, audited_at: datetime
) -> S5GitHubNormalizationExecutionContractAudit:
    stored = S5GitHubNormalizationExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    expected = build_contract(frozen_at=stored.frozen_at)
    if stored != expected:
        raise ValueError("S5 normalization execution contract differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "contract_file_sha256": file_sha256(contract_path),
        "contract_evidence_hash": stored.contract_evidence_hash,
        "protocol_evidence_hash": stored.protocol_evidence_hash,
        "protocol_audit_evidence_hash": stored.protocol_audit_evidence_hash,
        "runner_contract_hash": stored.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    provisional = S5GitHubNormalizationExecutionContractAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubNormalizationExecutionContractAudit.model_validate(complete)


def write_atomic(
    path: Path, audit: S5GitHubNormalizationExecutionContractAudit
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 normalization execution audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 normalization execution audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubNormalizationExecutionContractAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 normalization execution audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the S5 normalization execution contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5GitHubNormalizationExecutionContractAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(contract_path=args.contract, audited_at=stored.audited_at)
        if stored != expected:
            raise SystemExit("Stored S5 normalization execution audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(contract_path=args.contract, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
