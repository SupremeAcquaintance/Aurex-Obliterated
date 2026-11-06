from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_acquisition import (  # noqa: E402
    S1BtcSourceAcquisitionProtocol,
    S1BtcSourceAcquisitionProtocolAudit,
)
from aurex.backtest_engine.s1_btc_source_execution import (  # noqa: E402
    S1BtcSourceExecutionContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import (  # noqa: E402
    file_sha256,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_btc_source_acquisition_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_execution_contract_v1.json")
EVIDENCE_ROOT = Path("data/evidence/source_snapshots/s1_btcusdt_daily_1h_v1")
BUILDER_PATH = Path("scripts/freeze_s1_btc_source_execution_contract.py")
SYNTHETIC_TEST_IDS = (
    "frozen-target-allowlist",
    "checksum-filename-binding",
    "official-shaped-archive-open-extraction",
    "published-checksum-mismatch-rejection",
    "unsafe-zip-member-rejection",
    "multiple-zip-member-rejection",
    "twelve-column-kline-enforcement",
    "open-time-chronology-and-date-enforcement",
    "positive-finite-target-price-enforcement",
    "atomic-resource-marker-write",
    "aggregate-network-byte-budget-enforcement",
    "interrupted-partial-byte-rejection",
    "execution-authority-isolation",
)


def evidence_root_is_absent_or_empty() -> bool:
    root = PROJECT_ROOT / EVIDENCE_ROOT
    return not root.exists() or not any(root.iterdir())


def build_contract(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    frozen_at: datetime,
    free_disk_bytes_observed: int,
) -> S1BtcSourceExecutionContract:
    protocol = S1BtcSourceAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S1BtcSourceAcquisitionProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    if (
        file_sha256(protocol_path) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or not evidence_root_is_absent_or_empty()
    ):
        raise ValueError("S1 BTC execution-contract freeze boundary changed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "free_disk_bytes_observed": free_disk_bytes_observed,
        "synthetic_test_ids": SYNTHETIC_TEST_IDS,
    }
    provisional = S1BtcSourceExecutionContract.model_construct(
        **payload,
        contract_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    return S1BtcSourceExecutionContract.model_validate(complete)


def write_contract(path: Path, contract: S1BtcSourceExecutionContract) -> None:
    if path.exists():
        raise ValueError(f"S1 BTC execution contract exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 BTC contract transaction exists: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S1BtcSourceExecutionContract.model_validate_json(serialized) != contract:
        raise ValueError("S1 BTC execution contract did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze S1 BTC source execution authority without network access."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    free_disk = shutil.disk_usage(PROJECT_ROOT).free
    contract = build_contract(
        protocol_path=args.protocol,
        protocol_audit_path=args.protocol_audit,
        frozen_at=datetime.now(UTC),
        free_disk_bytes_observed=free_disk,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"runner={contract.runner_contract_hash} tests={len(contract.synthetic_test_ids)} "
        "network_requests=0 payload_bytes=0 btc_values=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
