from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_acquisition import (  # noqa: E402
    S1_BTC_SOURCE_GATES,
    S1BtcSourceAcquisitionProtocol,
    S1BtcSourceTarget,
)
from aurex.backtest_engine.s1_strategy_preregistration import (  # noqa: E402
    S1StrategyPreregistration,
    S1StrategyPreregistrationAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")
PREREGISTRATION_PATH = Path("data/evidence/s1_strategy_preregistration_v1.json")
PREREGISTRATION_AUDIT_PATH = Path(
    "data/evidence/s1_strategy_preregistration_audit_v1.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s1_btc_source_acquisition.py")
SCRIPT_PATH = Path("scripts/freeze_s1_btc_source_acquisition_protocol.py")
BASE_URL = "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_targets() -> tuple[S1BtcSourceTarget, ...]:
    current = date(2017, 9, 15)
    final = date(2022, 12, 30)
    targets = []
    while current <= final:
        sequence = len(targets) + 1
        filename = f"BTCUSDT-1h-{current.isoformat()}.zip"
        relative_root = (
            "data/evidence/source_snapshots/s1_btcusdt_daily_1h_v1/"
            f"{current.isoformat()}"
        )
        targets.append(
            S1BtcSourceTarget(
                sequence=sequence,
                feature_sequence=sequence + 4,
                target_id=f"{sequence:03d}-btcusdt-1h-{current.isoformat()}",
                activation_date=current,
                activation_open_time_ms=int(
                    datetime.combine(current, time(), tzinfo=UTC).timestamp() * 1000
                ),
                archive_url=f"{BASE_URL}/{filename}",
                checksum_url=f"{BASE_URL}/{filename}.CHECKSUM",
                expected_member_name=filename.replace(".zip", ".csv"),
                archive_path=f"{relative_root}/{filename}",
                checksum_path=f"{relative_root}/{filename}.CHECKSUM",
            )
        )
        current += timedelta(days=7)
    return tuple(targets)


def build_protocol(*, frozen_at: datetime) -> S1BtcSourceAcquisitionProtocol:
    preregistration = S1StrategyPreregistration.model_validate_json(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    audit = S1StrategyPreregistrationAudit.model_validate_json(
        PREREGISTRATION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        preregistration.next_authorization
        != "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
        or preregistration.authorizes_btc_market_value_access
        or audit.protocol_file_sha256 != file_sha256(PREREGISTRATION_PATH)
        or audit.protocol_evidence_hash != preregistration.protocol_evidence_hash
    ):
        raise ValueError("S1 preregistration does not authorize BTC source protocol")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "preregistration_file_sha256": file_sha256(PREREGISTRATION_PATH),
        "preregistration_evidence_hash": preregistration.protocol_evidence_hash,
        "preregistration_audit_file_sha256": file_sha256(
            PREREGISTRATION_AUDIT_PATH
        ),
        "preregistration_audit_evidence_hash": audit.audit_evidence_hash,
        "preregistration_decision": audit.decision,
        "preregistration_next_authorization": preregistration.next_authorization,
        "targets": build_targets(),
        "quality_gates": S1_BTC_SOURCE_GATES,
    }
    provisional = S1BtcSourceAcquisitionProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1BtcSourceAcquisitionProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1BtcSourceAcquisitionProtocol) -> None:
    if path.exists():
        raise ValueError(f"S1 BTC source protocol exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 BTC source protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1BtcSourceAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 BTC source protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 BTC source.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1BtcSourceAcquisitionProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 BTC source protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "targets=277 requests=0 payload_bytes=0 btc_values=0 returns=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
