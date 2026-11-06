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
from aurex.backtest_engine.s2_development_measurement_protocol import (  # noqa: E402
    S2DevelopmentMeasurementProtocol,
    S2DevelopmentMeasurementProtocolAudit,
)
from scripts.freeze_s2_development_measurement_protocol import (  # noqa: E402
    PAYLOAD_PATH,
    build_protocol,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_development_measurement_protocol_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_development_measurement_protocol_audit_v1.json")


def auditor_contract_hash() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit frozen S2 measurement protocol.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 measurement protocol audit exists: {args.output}")
        protocol = S2DevelopmentMeasurementProtocol.model_validate_json(args.protocol.read_text())
        if protocol.builder_contract_hash != builder_contract_hash():
            raise ValueError("S2 measurement protocol builder changed")
        if build_protocol(frozen_at=protocol.frozen_at) != protocol:
            raise ValueError("S2 measurement protocol did not reconstruct exactly")
        if any(
            not (PROJECT_ROOT / binding.path).is_file()
            or file_sha256(PROJECT_ROOT / binding.path) != binding.file_sha256
            for binding in protocol.source_bindings
        ):
            raise ValueError("S2 measurement protocol source binding changed")
        audit = build_hashed(
            S2DevelopmentMeasurementProtocolAudit,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "protocol_file_sha256": file_sha256(args.protocol),
                "protocol_evidence_hash": protocol.protocol_evidence_hash,
                "builder_contract_hash": protocol.builder_contract_hash,
                "auditor_contract_hash": auditor_contract_hash(),
                "payload_file_sha256": file_sha256(PAYLOAD_PATH),
                "payload_evidence_hash": protocol.payload_evidence_hash,
            },
        )
        args.output.write_text(
            audit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "payload_rows_parsed=0 market_values=0 parameters=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
