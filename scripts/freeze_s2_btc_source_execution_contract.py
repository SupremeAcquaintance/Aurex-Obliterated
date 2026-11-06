from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_btc_source_acquisition import (  # noqa: E402
    S2BtcSourceAcquisitionProtocol,
    S2BtcSourceAcquisitionProtocolAudit,
)
from aurex.backtest_engine.s2_btc_source_execution import (  # noqa: E402
    S2BtcSourceExecutionContract,
)
from scripts.run_s2_btc_source_acquisition import (  # noqa: E402
    build_hashed,
    file_sha256,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_btc_source_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s2_btc_source_acquisition_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s2_btc_source_execution_contract_v1.json")
EVIDENCE_ROOT = Path("data/evidence/source_snapshots/s2_btcusdt_monday_1h_v1")
SYNTHETIC_TEST_IDS = (
    "frozen-target-allowlist",
    "checksum-filename-binding",
    "official-shaped-archive-midnight-open-extraction",
    "published-checksum-mismatch-rejection",
    "unsafe-zip-member-rejection",
    "multiple-zip-member-rejection",
    "twelve-column-kline-enforcement",
    "duplicate-open-time-rejection",
    "non-increasing-open-time-rejection",
    "outside-target-date-rejection",
    "missing-exact-midnight-open-no-substitution",
    "positive-finite-target-price-enforcement",
    "exact-hash-local-reuse",
    "atomic-request-response-marker-write",
    "source-identity-drift-rejection",
    "aggregate-network-byte-budget-enforcement",
    "interrupted-partial-terminal-marker-recovery",
    "execution-authority-isolation",
    "deterministic-hash-linked-dataset-bytes",
)


def project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def evidence_root_is_absent_or_empty() -> bool:
    root = PROJECT_ROOT / EVIDENCE_ROOT
    return not root.exists() or not any(root.iterdir())


def build_contract(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    frozen_at: datetime,
    free_disk_bytes_observed: int,
) -> S2BtcSourceExecutionContract:
    resolved_protocol = project_path(protocol_path)
    resolved_audit = project_path(protocol_audit_path)
    protocol = S2BtcSourceAcquisitionProtocol.model_validate_json(
        resolved_protocol.read_text(encoding="utf-8")
    )
    audit = S2BtcSourceAcquisitionProtocolAudit.model_validate_json(
        resolved_audit.read_text(encoding="utf-8")
    )
    if (
        file_sha256(resolved_protocol) != audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != audit.protocol_evidence_hash
        or protocol.next_authorization
        != "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
        or protocol.authorizes_network_acquisition_now
        or not protocol.authorizes_runner_implementation
        or protocol.target_count != 273
        or protocol.maximum_network_requests != 1_638
        or protocol.maximum_total_payload_bytes != 54_739_776
        or free_disk_bytes_observed < protocol.minimum_free_disk_bytes
        or not evidence_root_is_absent_or_empty()
    ):
        raise ValueError("S2 BTC execution-contract freeze boundary changed")
    return build_hashed(
        S2BtcSourceExecutionContract,
        "contract_evidence_hash",
        frozen_at=frozen_at,
        builder_contract_hash=file_sha256(Path(__file__)),
        protocol_file_sha256=file_sha256(resolved_protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(resolved_audit),
        protocol_audit_evidence_hash=audit.audit_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        free_disk_bytes_observed=free_disk_bytes_observed,
        synthetic_test_ids=SYNTHETIC_TEST_IDS,
    )


def write_contract(path: Path, contract: S2BtcSourceExecutionContract) -> None:
    if path.exists():
        raise ValueError(f"S2 BTC execution contract exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S2BtcSourceExecutionContract.model_validate_json(serialized) != contract:
        raise ValueError("S2 BTC execution contract did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 BTC execution contract transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze S2 BTC source execution authority without network access."
    )
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        contract = build_contract(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            frozen_at=datetime.now(UTC),
            free_disk_bytes_observed=shutil.disk_usage(PROJECT_ROOT).free,
        )
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            f"runner={contract.runner_contract_hash} tests={len(contract.synthetic_test_ids)} "
            "network_requests=0 payload_bytes=0 btc_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
