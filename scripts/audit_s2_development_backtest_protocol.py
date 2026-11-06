from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2DevelopmentBacktestProtocol,
    S2DevelopmentBacktestProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s2_development_backtest_protocol import (  # noqa: E402
    build_protocol,
    file_sha256,
    rooted,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_development_backtest_protocol_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_development_backtest_protocol_audit_v1.json")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "auditor_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "auditor_sha256": file_sha256(Path(__file__)),
        }
    )


def build_audit(
    *, protocol_path: Path, audited_at: datetime
) -> S2DevelopmentBacktestProtocolAudit:
    resolved = rooted(protocol_path)
    protocol = S2DevelopmentBacktestProtocol.model_validate_json(
        resolved.read_text(encoding="utf-8")
    )
    if protocol != build_protocol(frozen_at=protocol.frozen_at):
        raise ValueError("S2 development backtest protocol did not reconstruct")
    return build_hashed(
        S2DevelopmentBacktestProtocolAudit,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "protocol_file_sha256": file_sha256(resolved),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "builder_contract_hash": protocol.builder_contract_hash,
            "preregistration_evidence_hash": protocol.preregistration_evidence_hash,
            "measurement_result_evidence_hash": (
                protocol.measurement_result_evidence_hash
            ),
            "source_result_evidence_hash": protocol.source_result_evidence_hash,
            "source_audit_evidence_hash": protocol.source_audit_evidence_hash,
            "measurement_dataset_file_sha256": (
                protocol.measurement_dataset_file_sha256
            ),
            "price_dataset_file_sha256": protocol.price_dataset_file_sha256,
            "auditor_contract_hash": auditor_contract_hash(),
        },
    )


def write_audit(path: Path, audit: S2DevelopmentBacktestProtocolAudit) -> None:
    if path.exists():
        raise ValueError(f"S2 development backtest protocol audit exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S2DevelopmentBacktestProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("S2 backtest protocol audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 backtest protocol audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S2 development backtest protocol.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        audit = build_audit(protocol_path=args.protocol, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "measurements_parsed=0 prices_parsed=0 returns=0 outcomes=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
