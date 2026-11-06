from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_alfred_recovery import (  # noqa: E402
    S1NfciAlfredRecoveryAudit,
    S1NfciAlfredRecoveryProtocol,
    S1NfciAlfredRecoveryResult,
)
from aurex.backtest_engine.s1_nfci_full_acquisition import (  # noqa: E402
    S1NfciFullAcquisitionProtocol,
    S1NfciFullAcquisitionTarget,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
RECOVERY_PROTOCOL_PATH = Path("data/evidence/s1_nfci_alfred_recovery_protocol_v1.json")
RECOVERY_RESULT_PATH = Path("data/evidence/s1_nfci_alfred_recovery_result_v1.json")
RECOVERY_AUDIT_PATH = Path("data/evidence/s1_nfci_alfred_recovery_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_full_acquisition.py")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_full_acquisition_protocol.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_targets() -> tuple[S1NfciFullAcquisitionTarget, ...]:
    current = date(2017, 8, 17)
    final = date(2022, 12, 29)
    targets = []
    while current <= final:
        sequence = len(targets) + 1
        targets.append(
            S1NfciFullAcquisitionTarget(
                sequence=sequence,
                target_id=f"{sequence:03d}-nfci-vintage-{current.isoformat()}",
                vintage_date=current,
                url=(
                    "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
                    f"?id=NFCI&vintage_date={current.isoformat()}"
                ),
                expected_value_column=f"NFCI_{current:%Y%m%d}",
                raw_path=(
                    "data/evidence/source_snapshots/s1_nfci_full_acquisition_v1/"
                    f"nfci_vintage_{current.isoformat()}.csv"
                ),
            )
        )
        current += timedelta(days=7)
    return tuple(targets)


def build_protocol(*, frozen_at: datetime) -> S1NfciFullAcquisitionProtocol:
    recovery_protocol = S1NfciAlfredRecoveryProtocol.model_validate_json(
        RECOVERY_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    recovery_result = S1NfciAlfredRecoveryResult.model_validate_json(
        RECOVERY_RESULT_PATH.read_text(encoding="utf-8")
    )
    recovery_audit = S1NfciAlfredRecoveryAudit.model_validate_json(
        RECOVERY_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        recovery_result.decision != "PASS_S1_ALFRED_POINT_IN_TIME_SOURCE_RECOVERY"
        or recovery_result.next_authorization
        != "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY"
        or recovery_audit.result_evidence_hash != recovery_result.result_evidence_hash
    ):
        raise ValueError("S1 ALFRED recovery does not authorize the full protocol")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "recovery_protocol_file_sha256": file_sha256(RECOVERY_PROTOCOL_PATH),
        "recovery_protocol_evidence_hash": recovery_protocol.protocol_evidence_hash,
        "recovery_result_file_sha256": file_sha256(RECOVERY_RESULT_PATH),
        "recovery_result_evidence_hash": recovery_result.result_evidence_hash,
        "recovery_audit_file_sha256": file_sha256(RECOVERY_AUDIT_PATH),
        "recovery_audit_evidence_hash": recovery_audit.audit_evidence_hash,
        "recovery_decision": recovery_result.decision,
        "recovery_next_authorization": recovery_result.next_authorization,
        "targets": build_targets(),
        "quality_gates": (
            "ALL_281_THURSDAY_TARGETS_CLASSIFIED",
            "EVERY_COMPLETE_FILE_WITHIN_BYTE_CAP_AND_HASHED",
            "EXACT_VINTAGE_SUFFIXED_HEADER_PER_TARGET",
            "STRICTLY_INCREASING_UNIQUE_OBSERVATION_DATES_PER_TARGET",
            "NO_POST_VINTAGE_OBSERVATION_PER_TARGET",
            "DEVELOPMENT_START_COVERED_PER_TARGET",
            "LATEST_OBSERVATION_WITHIN_21_DAYS_OF_VINTAGE_PER_TARGET",
            "AT_LEAST_260_DISTINCT_POINT_IN_TIME_PAYLOAD_HASHES",
            "REQUEST_AND_RESPONSE_MARKERS_RECONCILE_EXACTLY",
            "ZERO_BTC_MARKET_VALUES_RETURNS_CANDIDATES_AND_ORDERS",
        ),
    }
    provisional = S1NfciFullAcquisitionProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1NfciFullAcquisitionProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1NfciFullAcquisitionProtocol) -> None:
    if path.exists():
        raise ValueError(f"S1 full-acquisition protocol exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 full-protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1NfciFullAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 full-acquisition protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 NFCI acquisition.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciFullAcquisitionProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 full-acquisition protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "targets=281 requests=0 payload_bytes=0 btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
