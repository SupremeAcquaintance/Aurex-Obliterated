from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution_v2 import (  # noqa: E402
    S1BtcSourceExecutionContractV2,
)
from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1BtcSourceAcquisitionProtocolAuditV2,
    S1BtcSourceAcquisitionProtocolV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s1_btc_source_acquisition_v2 import (  # noqa: E402
    V1_RUNNER_PATH,
    runner_contract_hash,
    verify_reuse_artifact,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v2.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_btc_source_acquisition_protocol_audit_v2.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_execution_contract_v2.json")
BUILDER_PATH = Path("scripts/freeze_s1_btc_source_execution_contract_v2.py")
SYNTHETIC_TEST_IDS = (
    "prior-exposure-declaration",
    "midnight-first-available-selection",
    "delayed-first-available-selection",
    "real-2018-gap-10utc-selection",
    "v1-exact-hash-reuse-manifest",
    "partial-checkpoint-prefix-reconstruction",
    "published-checksum-mismatch-rejection",
    "unsafe-zip-member-rejection",
    "twelve-column-kline-enforcement",
    "open-time-uniqueness-enforcement",
    "target-date-boundary-enforcement",
    "positive-finite-selected-price-enforcement",
    "execution-authority-isolation",
)


def build_contract(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    frozen_at: datetime,
    free_disk_bytes_observed: int,
) -> S1BtcSourceExecutionContractV2:
    protocol = S1BtcSourceAcquisitionProtocolV2.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S1BtcSourceAcquisitionProtocolAuditV2.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    if (
        file_sha256(protocol_path) != audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != audit.protocol_evidence_hash
    ):
        raise ValueError("S1.1 execution contract protocol lineage changed")
    for target, reuse in zip(
        protocol.targets[: protocol.reuse_target_count],
        protocol.reuse_artifacts,
        strict=True,
    ):
        verify_reuse_artifact(target, reuse)
    if any(
        (PROJECT_ROOT / target.archive_path).exists()
        or (PROJECT_ROOT / target.checksum_path).exists()
        for target in protocol.targets[protocol.reuse_target_count :]
    ):
        raise ValueError("S1.1 unregistered network-target source file exists")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "v1_transport_dependency_file_sha256": file_sha256(
            PROJECT_ROOT / V1_RUNNER_PATH
        ),
        "free_disk_bytes_observed": free_disk_bytes_observed,
        "synthetic_test_ids": SYNTHETIC_TEST_IDS,
    }
    provisional = S1BtcSourceExecutionContractV2.model_construct(
        **payload,
        contract_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    return S1BtcSourceExecutionContractV2.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S1.1 BTC execution authority.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1.1 execution contract exists: {args.output}")
    contract = build_contract(
        protocol_path=args.protocol,
        protocol_audit_path=args.protocol_audit,
        frozen_at=datetime.now(UTC),
        free_disk_bytes_observed=shutil.disk_usage(PROJECT_ROOT).free,
    )
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(contract.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"runner={contract.runner_contract_hash} tests={len(contract.synthetic_test_ids)} "
        "new_requests=0 new_prices=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
