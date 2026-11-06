from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_alfred_recovery import (  # noqa: E402
    S1NfciAlfredRecoveryProtocol,
    S1NfciAlfredTarget,
)
from aurex.backtest_engine.s1_nfci_raw_pilot import (  # noqa: E402
    S1NfciRawPilotAudit,
    S1NfciRawPilotProtocol,
    S1NfciRawPilotResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_alfred_recovery_protocol_v1.json")
FAILED_PROTOCOL_PATH = Path("data/evidence/s1_nfci_raw_pilot_protocol_v1.json")
FAILED_RESULT_PATH = Path("data/evidence/s1_nfci_raw_pilot_result_v1.json")
FAILED_AUDIT_PATH = Path("data/evidence/s1_nfci_raw_pilot_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_alfred_recovery.py")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_alfred_recovery_protocol.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_protocol(*, frozen_at: datetime) -> S1NfciAlfredRecoveryProtocol:
    failed_protocol = S1NfciRawPilotProtocol.model_validate_json(
        FAILED_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    failed_result = S1NfciRawPilotResult.model_validate_json(
        FAILED_RESULT_PATH.read_text(encoding="utf-8")
    )
    failed_audit = S1NfciRawPilotAudit.model_validate_json(
        FAILED_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        failed_result.decision != "STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED"
        or failed_result.downloads[0].payload_sha256
        != failed_result.downloads[1].payload_sha256
        or any(
            download.summary is None
            or download.summary.post_vintage_observation_count == 0
            for download in failed_result.downloads
        )
        or failed_audit.result_evidence_hash != failed_result.result_evidence_hash
    ):
        raise ValueError("S1 failed FRED pilot classification changed")
    targets = tuple(
        S1NfciAlfredTarget(
            target_id=target.target_id,
            vintage_date=target.vintage_date,
            url=(
                "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
                f"?id=NFCI&vintage_date={target.vintage_date.isoformat()}"
            ),
            expected_value_column=f"NFCI_{target.vintage_date:%Y%m%d}",
            raw_path=(
                "data/evidence/source_snapshots/s1_nfci_alfred_recovery_v1/"
                f"nfci_vintage_{target.vintage_date.isoformat()}.csv"
            ),
        )
        for target in failed_protocol.targets
    )
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "failed_pilot_protocol_file_sha256": file_sha256(FAILED_PROTOCOL_PATH),
        "failed_pilot_protocol_evidence_hash": failed_protocol.protocol_evidence_hash,
        "failed_pilot_result_file_sha256": file_sha256(FAILED_RESULT_PATH),
        "failed_pilot_result_evidence_hash": failed_result.result_evidence_hash,
        "failed_pilot_audit_file_sha256": file_sha256(FAILED_AUDIT_PATH),
        "failed_pilot_audit_evidence_hash": failed_audit.audit_evidence_hash,
        "failed_pilot_decision": failed_result.decision,
        "failure_classification": (
            "FREDGRAPH_IGNORED_VINTAGE_DATE_AND_RETURNED_IDENTICAL_CURRENT_DATA"
        ),
        "remediation_scope": (
            "REPLACE_FREDGRAPH_CURRENT_TRANSPORT_WITH_ALFREDGRAPH_VINTAGE_TRANSPORT_ONLY"
        ),
        "source_documentation_urls": (
            "https://alfred.stlouisfed.org/series/downloaddata?seid=NFCI",
            "https://alfred.stlouisfed.org/help/downloaddata",
            "https://fred.stlouisfed.org/docs/api/fred/fred_vs_alfred.html",
        ),
        "targets": targets,
        "feasibility_gates": (
            "EXACTLY_TWO_FROZEN_ALFRED_GETS_WITHIN_BYTE_BUDGET",
            "BOTH_ALFRED_SNAPSHOTS_COMPLETE_AND_HASHED",
            "OFFICIAL_ALFRED_FINAL_HOSTS_AND_CSV_CONTENT_TYPES_MATCH",
            "VINTAGE_SUFFIXED_CSV_HEADERS_AND_VALID_DECIMAL_ROWS",
            "STRICTLY_INCREASING_UNIQUE_OBSERVATION_DATES",
            "NO_OBSERVATION_AFTER_REQUESTED_VINTAGE",
            "EACH_SNAPSHOT_COVERS_DEVELOPMENT_START_AND_IS_RECENT_TO_VINTAGE",
            "DISTINCT_SNAPSHOTS_WITH_LATER_VINTAGE_EXTENSION",
            "OVERLAP_CONTAINS_AT_LEAST_ONE_POINT_IN_TIME_REVISION",
            "ZERO_BTC_MARKET_VALUES_RETURNS_CANDIDATES_AND_ORDERS",
        ),
    }
    provisional = S1NfciAlfredRecoveryProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1NfciAlfredRecoveryProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1NfciAlfredRecoveryProtocol) -> None:
    if path.exists():
        raise ValueError(f"S1 ALFRED recovery protocol exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 ALFRED protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1NfciAlfredRecoveryProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 ALFRED recovery protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 ALFRED recovery.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciAlfredRecoveryProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 ALFRED protocol differs from reconstruction")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "requests=0 payload_bytes=0 btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
