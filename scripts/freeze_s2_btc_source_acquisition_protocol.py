from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s2_btc_source_acquisition import (  # noqa: E402
    S2_BTC_SOURCE_BASE_URL,
    S2_BTC_SOURCE_GATES,
    S2BtcSourceAcquisitionProtocol,
    S2BtcSourceTarget,
)
from aurex.backtest_engine.s2_strategy_preregistration import (  # noqa: E402
    S2StrategyPreregistration,
    S2StrategyPreregistrationAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_btc_source_acquisition_protocol_v1.json")
PREREGISTRATION_PATH = Path("data/evidence/s2_strategy_preregistration_v1.json")
PREREGISTRATION_AUDIT_PATH = Path(
    "data/evidence/s2_strategy_preregistration_audit_v1.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s2_btc_source_acquisition.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "builder_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "builder_sha256": file_sha256(Path(__file__)),
        }
    )


def build_targets() -> tuple[S2BtcSourceTarget, ...]:
    current = date(2017, 10, 16)
    final = date(2023, 1, 2)
    targets = []
    while current <= final:
        sequence = len(targets) + 1
        filename = f"BTCUSDT-1h-{current.isoformat()}.zip"
        relative_root = (
            "data/evidence/source_snapshots/s2_btcusdt_monday_1h_v1/"
            f"{current.isoformat()}"
        )
        targets.append(
            S2BtcSourceTarget(
                sequence=sequence,
                measurement_sequence=sequence + 7,
                target_id=f"{sequence:03d}-btcusdt-1h-{current.isoformat()}",
                activation_date=current,
                activation_open_time_ms=int(
                    datetime.combine(current, time(), tzinfo=UTC).timestamp() * 1000
                ),
                archive_url=f"{S2_BTC_SOURCE_BASE_URL}/{filename}",
                checksum_url=f"{S2_BTC_SOURCE_BASE_URL}/{filename}.CHECKSUM",
                expected_member_name=filename.replace(".zip", ".csv"),
                archive_path=f"{relative_root}/{filename}",
                checksum_path=f"{relative_root}/{filename}.CHECKSUM",
            )
        )
        current += timedelta(days=7)
    return tuple(targets)


def build_protocol(*, frozen_at: datetime) -> S2BtcSourceAcquisitionProtocol:
    preregistration = S2StrategyPreregistration.model_validate_json(
        (PROJECT_ROOT / PREREGISTRATION_PATH).read_text(encoding="utf-8")
    )
    audit = S2StrategyPreregistrationAudit.model_validate_json(
        (PROJECT_ROOT / PREREGISTRATION_AUDIT_PATH).read_text(encoding="utf-8")
    )
    if (
        preregistration.next_authorization
        != "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
        or preregistration.authorizes_btc_source_acquisition_now
        or preregistration.authorizes_btc_market_value_access
        or audit.protocol_file_sha256
        != file_sha256(PROJECT_ROOT / PREREGISTRATION_PATH)
        or audit.protocol_evidence_hash != preregistration.protocol_evidence_hash
        or audit.next_authorization != preregistration.next_authorization
        or preregistration.required_price_date_count != 273
        or preregistration.first_required_price_date != "2017-10-16"
        or preregistration.last_required_price_date != "2023-01-02"
        or preregistration.required_price_weekday != "MONDAY"
        or preregistration.source_base_url != S2_BTC_SOURCE_BASE_URL
        or preregistration.execution_price_rule
        != "EXACT_1H_KLINE_OPEN_AT_MEASUREMENT_EARLIEST_EXECUTION_TIMESTAMP"
        or preregistration.missing_execution_price_policy != "STOP_NO_SUBSTITUTION"
    ):
        raise ValueError("S2 preregistration does not authorize this source protocol")
    return build_hashed(
        S2BtcSourceAcquisitionProtocol,
        "protocol_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "preregistration_file_sha256": file_sha256(
                PROJECT_ROOT / PREREGISTRATION_PATH
            ),
            "preregistration_evidence_hash": preregistration.protocol_evidence_hash,
            "preregistration_audit_file_sha256": file_sha256(
                PROJECT_ROOT / PREREGISTRATION_AUDIT_PATH
            ),
            "preregistration_audit_evidence_hash": audit.audit_evidence_hash,
            "preregistration_decision": preregistration.decision,
            "preregistration_audit_decision": audit.decision,
            "preregistration_next_authorization": preregistration.next_authorization,
            "targets": build_targets(),
            "quality_gates": S2_BTC_SOURCE_GATES,
        },
    )


def write_protocol(path: Path, protocol: S2BtcSourceAcquisitionProtocol) -> None:
    if path.exists():
        raise ValueError(f"S2 BTC source protocol exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2BtcSourceAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S2 BTC source protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 BTC source protocol transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S2 BTC source protocol.")
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "targets=273 requests=0 payload_bytes=0 btc_values=0 returns=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
