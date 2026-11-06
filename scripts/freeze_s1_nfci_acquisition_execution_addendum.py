from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_full_acquisition import (  # noqa: E402
    S1NfciFullAcquisitionProtocol,
    S1NfciFullAcquisitionProtocolAudit,
)
from aurex.backtest_engine.s1_nfci_full_execution import (  # noqa: E402
    S1NfciAcquisitionExecutionAddendum,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_full_acquisition import runner_contract_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_acquisition_execution_addendum_v1.json")
PROTOCOL_PATH = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_full_acquisition_protocol_audit_v1.json"
)
EVIDENCE_ROOT = Path("data/evidence/source_snapshots/s1_nfci_full_acquisition_v1")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_full_execution.py")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_acquisition_execution_addendum.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def evidence_root_is_absent_or_empty() -> bool:
    return not EVIDENCE_ROOT.exists() or not any(EVIDENCE_ROOT.iterdir())


def build_addendum(
    *,
    frozen_at: datetime,
    free_disk_bytes_observed: int,
) -> S1NfciAcquisitionExecutionAddendum:
    protocol = S1NfciFullAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFullAcquisitionProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol.next_authorization
        != "AUTHORIZE_S1_NFCI_DEVELOPMENT_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.network_requests_observed != 0
        or audit.payload_bytes_observed != 0
    ):
        raise ValueError("S1 full-acquisition protocol lineage changed")
    if not evidence_root_is_absent_or_empty():
        raise ValueError("S1 full-acquisition evidence root is not empty")
    if free_disk_bytes_observed < protocol.minimum_free_disk_bytes:
        raise ValueError("S1 full-acquisition free disk preflight failed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "protocol_file_sha256": file_sha256(PROTOCOL_PATH),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(PROTOCOL_AUDIT_PATH),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "free_disk_bytes_observed": free_disk_bytes_observed,
        "synthetic_test_ids": (
            "URL_AND_EVIDENCE_ROOT_ALLOWLIST_REJECTION",
            "TRANSIENT_AND_PERMANENT_ERROR_CLASSIFICATION",
            "INTERRUPTED_ATTEMPT_MARKER_RECONCILIATION",
            "POST_VINTAGE_OBSERVATION_REJECTION",
            "CHECKPOINT_COUNT_AND_HASH_RECONSTRUCTION",
            "ZERO_BTC_OUTCOME_AND_TRADING_AUTHORITY",
        ),
    }
    provisional = S1NfciAcquisitionExecutionAddendum.model_construct(
        **payload,
        addendum_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["addendum_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"addendum_evidence_hash"})
    )
    return S1NfciAcquisitionExecutionAddendum.model_validate(complete)


def write_atomic(path: Path, addendum: S1NfciAcquisitionExecutionAddendum) -> None:
    if path.exists():
        raise ValueError(f"S1 execution addendum exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 execution-addendum transaction exists: {temporary}")
    serialized = addendum.model_dump_json(indent=2) + "\n"
    if S1NfciAcquisitionExecutionAddendum.model_validate_json(serialized) != addendum:
        raise ValueError("S1 execution addendum did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze/check S1 execution addendum.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    free_disk = shutil.disk_usage(PROJECT_ROOT).free
    if args.check:
        stored = S1NfciAcquisitionExecutionAddendum.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_addendum(
            frozen_at=stored.frozen_at,
            free_disk_bytes_observed=stored.free_disk_bytes_observed,
        )
        if stored != expected:
            raise SystemExit("Stored S1 execution addendum differs")
        print(f"PASS {stored.addendum_evidence_hash}")
        return 0
    addendum = build_addendum(
        frozen_at=datetime.now(UTC),
        free_disk_bytes_observed=free_disk,
    )
    write_atomic(args.output, addendum)
    print(
        f"FROZEN {args.output} {addendum.addendum_evidence_hash} "
        f"runner={addendum.runner_contract_hash} free_disk={free_disk} requests=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
