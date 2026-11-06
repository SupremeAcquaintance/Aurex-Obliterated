from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution import (  # noqa: E402
    S1BtcSourceExecutionAudit,
    S1BtcSourceExecutionContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_btc_source_execution_contract import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    build_contract,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_CONTRACT = Path("data/evidence/s1_btc_source_execution_contract_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_execution_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_btc_source_execution_contract.py")


def build_audit(
    *,
    contract_path: Path,
    contract: S1BtcSourceExecutionContract,
    audited_at: datetime,
) -> S1BtcSourceExecutionAudit:
    payload = {
        "audited_at": audited_at,
        "contract_file_sha256": file_sha256(contract_path),
        "contract_evidence_hash": contract.contract_evidence_hash,
        "protocol_evidence_hash": contract.protocol_evidence_hash,
        "runner_contract_hash": contract.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "synthetic_test_ids": contract.synthetic_test_ids,
    }
    provisional = S1BtcSourceExecutionAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1BtcSourceExecutionAudit.model_validate(complete)


def write_audit(path: Path, audit: S1BtcSourceExecutionAudit) -> None:
    if path.exists():
        raise ValueError(f"S1 BTC execution audit exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 BTC audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1BtcSourceExecutionAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 BTC execution audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct the S1 BTC execution contract."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = S1BtcSourceExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    reconstructed = build_contract(
        protocol_path=args.protocol,
        protocol_audit_path=args.protocol_audit,
        frozen_at=contract.frozen_at,
        free_disk_bytes_observed=contract.free_disk_bytes_observed,
    )
    if reconstructed != contract:
        raise SystemExit("S1 BTC execution contract did not reconstruct exactly")
    audit = build_audit(
        contract_path=args.contract,
        contract=contract,
        audited_at=datetime.now(UTC),
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"contract={audit.contract_evidence_hash} tests={len(audit.synthetic_test_ids)} "
        "network_requests=0 payload_bytes=0 btc_values=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
