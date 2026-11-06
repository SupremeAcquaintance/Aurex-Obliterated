from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_raw_pilot import (  # noqa: E402
    S1NfciPilotTarget,
    S1NfciRawPilotProtocol,
)
from aurex.backtest_engine.s1_source_transport_v2 import (  # noqa: E402
    S1SourceTransportAuditV2,
    S1SourceTransportResultV2,
)
from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1MacroFinancialConditionsCharter,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_raw_pilot_protocol_v1.json")
CHARTER_PATH = Path("data/evidence/s1_macro_financial_conditions_charter_v1.json")
V2_RESULT_PATH = Path("data/evidence/s1_source_transport_result_v2.json")
V2_AUDIT_PATH = Path("data/evidence/s1_source_transport_audit_v2.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_raw_pilot.py")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_raw_pilot_protocol.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_protocol(*, frozen_at: datetime) -> S1NfciRawPilotProtocol:
    charter = S1MacroFinancialConditionsCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    result = S1SourceTransportResultV2.model_validate_json(
        V2_RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1SourceTransportAuditV2.model_validate_json(
        V2_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if result.next_authorization != "AUTHORIZE_S1_RAW_NFCI_TWO_VINTAGE_PILOT_PROTOCOL_ONLY":
        raise ValueError("S1 v2 did not authorize the raw two-vintage pilot protocol")
    if audit.result_evidence_hash != result.result_evidence_hash:
        raise ValueError("S1 v2 audit does not bind the transport result")
    targets = (
        S1NfciPilotTarget(
            target_id="01-nfci-vintage-2020",
            vintage_date="2020-01-01",
            url=(
                "https://fred.stlouisfed.org/graph/fredgraph.csv"
                "?id=NFCI&vintage_date=2020-01-01"
            ),
            raw_path=(
                "data/evidence/source_snapshots/s1_nfci_raw_pilot_v1/"
                "nfci_vintage_2020-01-01.csv"
            ),
        ),
        S1NfciPilotTarget(
            target_id="02-nfci-vintage-2021",
            vintage_date="2021-01-01",
            url=(
                "https://fred.stlouisfed.org/graph/fredgraph.csv"
                "?id=NFCI&vintage_date=2021-01-01"
            ),
            raw_path=(
                "data/evidence/source_snapshots/s1_nfci_raw_pilot_v1/"
                "nfci_vintage_2021-01-01.csv"
            ),
        ),
    )
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_file_sha256": file_sha256(CHARTER_PATH),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "v2_result_file_sha256": file_sha256(V2_RESULT_PATH),
        "v2_result_evidence_hash": result.result_evidence_hash,
        "v2_audit_file_sha256": file_sha256(V2_AUDIT_PATH),
        "v2_audit_evidence_hash": audit.audit_evidence_hash,
        "v2_decision": result.decision,
        "v2_next_authorization": result.next_authorization,
        "targets": targets,
        "feasibility_gates": (
            "EXACTLY_TWO_FROZEN_PAYLOAD_GETS_WITHIN_BYTE_BUDGET",
            "BOTH_RAW_SNAPSHOTS_COMPLETE_AND_HASHED",
            "OFFICIAL_FINAL_HOSTS_AND_CSV_CONTENT_TYPES_MATCH",
            "EXACT_CSV_SCHEMA_AND_VALID_DECIMAL_ROWS",
            "STRICTLY_INCREASING_UNIQUE_OBSERVATION_DATES",
            "NO_OBSERVATION_AFTER_REQUESTED_VINTAGE",
            "EACH_SNAPSHOT_COVERS_DEVELOPMENT_START_AND_IS_RECENT_TO_VINTAGE",
            "DISTINCT_SNAPSHOTS_WITH_LATER_VINTAGE_EXTENSION",
            "OVERLAP_CONTAINS_AT_LEAST_ONE_POINT_IN_TIME_REVISION",
            "ZERO_BTC_MARKET_VALUES_RETURNS_CANDIDATES_AND_ORDERS",
        ),
    }
    provisional = S1NfciRawPilotProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1NfciRawPilotProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1NfciRawPilotProtocol) -> None:
    if path.exists():
        raise ValueError(f"S1 NFCI raw pilot protocol exists; use --check: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 NFCI protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1NfciRawPilotProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 NFCI raw pilot protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 NFCI raw pilot protocol.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciRawPilotProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 NFCI raw pilot protocol differs from reconstruction")
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
