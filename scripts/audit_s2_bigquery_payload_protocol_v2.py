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
from aurex.backtest_engine.s2_bigquery_payload_v2 import (  # noqa: E402
    S2BigQueryPayloadProtocolAuditV2,
    S2BigQueryPayloadProtocolV2,
)
from scripts.freeze_s2_bigquery_payload_protocol_v2 import (  # noqa: E402
    build_protocol,
    builder_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_payload_protocol_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_payload_protocol_audit_v2.json")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def auditor_contract_hash() -> str:
    return file_sha256(Path(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit frozen S2 payload v2.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 payload protocol v2 audit exists: {args.output}")
        protocol = S2BigQueryPayloadProtocolV2.model_validate_json(args.protocol.read_text())
        if protocol.builder_contract_hash != builder_contract_hash():
            raise ValueError("S2 payload protocol v2 builder changed")
        if build_protocol(frozen_at=protocol.frozen_at) != protocol:
            raise ValueError("S2 payload protocol v2 did not reconstruct exactly")
        audit = build_hashed(
            S2BigQueryPayloadProtocolAuditV2,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "protocol_file_sha256": file_sha256(args.protocol),
                "protocol_evidence_hash": protocol.protocol_evidence_hash,
                "feasibility_result_evidence_hash": (protocol.feasibility_result_evidence_hash),
                "builder_contract_hash": protocol.builder_contract_hash,
                "auditor_contract_hash": auditor_contract_hash(),
                "prior_payload_result_evidence_hash": (protocol.prior_payload_result_evidence_hash),
                "prior_payload_failure_audit_evidence_hash": (
                    protocol.prior_payload_failure_audit_evidence_hash
                ),
            },
        )
        args.output.write_text(
            audit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "queries=0 rows=0 market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
