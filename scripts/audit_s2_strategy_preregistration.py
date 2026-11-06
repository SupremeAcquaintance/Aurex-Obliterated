from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s2_strategy_preregistration import (  # noqa: E402
    S2StrategyPreregistration,
    S2StrategyPreregistrationAudit,
)
from scripts.freeze_s2_strategy_preregistration import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_s2_strategy_preregistration import (  # noqa: E402
    build_protocol,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_OUTPUT = Path("data/evidence/s2_strategy_preregistration_audit_v1.json")


def auditor_contract_hash() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S2 strategy preregistration.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 strategy preregistration audit exists: {args.output}")
        protocol = S2StrategyPreregistration.model_validate_json(args.protocol.read_text())
        if protocol.builder_contract_hash != builder_contract_hash():
            raise ValueError("S2 strategy preregistration builder changed")
        if build_protocol(frozen_at=protocol.frozen_at) != protocol:
            raise ValueError("S2 strategy preregistration did not reconstruct exactly")
        if any(
            not (PROJECT_ROOT / binding.path).is_file()
            or file_sha256(PROJECT_ROOT / binding.path) != binding.file_sha256
            for binding in protocol.source_bindings
        ):
            raise ValueError("S2 strategy preregistration source binding changed")
        audit = build_hashed(
            S2StrategyPreregistrationAudit,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "protocol_file_sha256": file_sha256(args.protocol),
                "protocol_evidence_hash": protocol.protocol_evidence_hash,
                "builder_contract_hash": protocol.builder_contract_hash,
                "measurement_result_evidence_hash": (protocol.measurement_result_evidence_hash),
                "measurement_audit_evidence_hash": (protocol.measurement_audit_evidence_hash),
                "measurement_dataset_file_sha256": (protocol.measurement_dataset_file_sha256),
                "measurement_row_manifest_evidence_hash": (
                    protocol.measurement_row_manifest_evidence_hash
                ),
                "auditor_contract_hash": auditor_contract_hash(),
            },
        )
        args.output.write_text(
            audit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "measurement_rows_parsed=0 market_values=0 returns=0 candidates=1 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
