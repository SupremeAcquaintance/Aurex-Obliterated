from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import (  # noqa: E402
    audit_model,
    build_hashed,
)
from aurex.backtest_engine.s2_bigquery_payload import (  # noqa: E402
    S2_PAYLOAD_NEXT,
    S2_PAYLOAD_PASS,
    S2DevelopmentWeeklyPayload,
)
from aurex.backtest_engine.s2_bigquery_payload_v2 import (  # noqa: E402
    S2BigQueryPayloadAuditV2,
    S2BigQueryPayloadFailureAuditV1,
    S2BigQueryPayloadProtocolAuditV2,
    S2BigQueryPayloadProtocolV2,
    S2BigQueryPayloadResultV2,
)
from scripts.run_s2_bigquery_payload_v2 import runner_contract_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_payload_protocol_v2.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_bigquery_payload_protocol_audit_v2.json")
DEFAULT_PRIOR_AUDIT = Path("data/evidence/s2_bigquery_payload_failure_audit_v1.json")
DEFAULT_PAYLOAD = Path("data/evidence/s2_development_weekly_payload_v1.json")
DEFAULT_RESULT = Path("data/evidence/s2_bigquery_payload_result_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_payload_audit_v2.json")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def auditor_contract_hash() -> str:
    return file_sha256(Path(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S2 development payload v2.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--prior-audit", type=Path, default=DEFAULT_PRIOR_AUDIT)
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 BigQuery payload v2 audit exists: {args.output}")
        protocol = S2BigQueryPayloadProtocolV2.model_validate_json(args.protocol.read_text())
        protocol_audit = S2BigQueryPayloadProtocolAuditV2.model_validate_json(
            args.protocol_audit.read_text()
        )
        prior_audit = S2BigQueryPayloadFailureAuditV1.model_validate_json(
            args.prior_audit.read_text()
        )
        payload = S2DevelopmentWeeklyPayload.model_validate_json(args.payload.read_text())
        result = S2BigQueryPayloadResultV2.model_validate_json(args.result.read_text())
        if (
            file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
            or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
            or protocol.protocol_evidence_hash != payload.protocol_evidence_hash
            or protocol.query_spec.query_sha256 != payload.query_sha256
            or protocol.protocol_evidence_hash != result.protocol_evidence_hash
            or protocol_audit.audit_evidence_hash != result.protocol_audit_evidence_hash
            or protocol.prior_payload_failure_audit_evidence_hash != prior_audit.audit_evidence_hash
            or result.prior_payload_failure_audit_evidence_hash != prior_audit.audit_evidence_hash
            or payload.payload_evidence_hash != result.payload_evidence_hash
            or file_sha256(args.payload) != result.payload_file_sha256
            or args.payload.stat().st_size != result.payload_byte_count
            or runner_contract_hash() != result.runner_contract_hash
            or result.decision != S2_PAYLOAD_PASS
            or result.next_authorization != S2_PAYLOAD_NEXT
            or not audit_model(payload, "payload_evidence_hash")
            or not audit_model(result, "result_evidence_hash")
        ):
            raise ValueError("S2 BigQuery payload v2 lineage changed")
        for binding in protocol.source_bindings:
            path = PROJECT_ROOT / binding.path
            if not path.is_file() or file_sha256(path) != binding.file_sha256:
                raise ValueError("S2 BigQuery payload v2 source binding changed")
        audit = build_hashed(
            S2BigQueryPayloadAuditV2,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "result_file_sha256": file_sha256(args.result),
                "result_evidence_hash": result.result_evidence_hash,
                "protocol_evidence_hash": result.protocol_evidence_hash,
                "protocol_audit_evidence_hash": result.protocol_audit_evidence_hash,
                "feasibility_result_evidence_hash": (result.feasibility_result_evidence_hash),
                "feasibility_result_audit_evidence_hash": (
                    result.feasibility_result_audit_evidence_hash
                ),
                "prior_payload_result_evidence_hash": (result.prior_payload_result_evidence_hash),
                "prior_payload_failure_audit_evidence_hash": (
                    result.prior_payload_failure_audit_evidence_hash
                ),
                "runner_contract_hash": result.runner_contract_hash,
                "auditor_contract_hash": auditor_contract_hash(),
                "payload_file_sha256": result.payload_file_sha256,
                "payload_evidence_hash": payload.payload_evidence_hash,
                "payload_byte_count": result.payload_byte_count,
            },
        )
        args.output.write_text(
            audit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"decision={audit.decision} rows={audit.payload_row_count} "
            "market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
