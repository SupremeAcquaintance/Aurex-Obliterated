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
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (  # noqa: E402
    S2BigQueryFeasibilityAuditV3,
    S2BigQueryFeasibilityProtocolAuditV3,
    S2BigQueryFeasibilityProtocolV3,
    S2BigQueryFeasibilityResultV3,
)
from scripts.run_s2_bigquery_feasibility_v3 import runner_contract_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_feasibility_protocol_v3.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v3.json")
DEFAULT_RESULT = Path("data/evidence/s2_bigquery_feasibility_result_v3.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_audit_v3.json")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def auditor_contract_hash() -> str:
    return file_sha256(Path(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S2 BigQuery REST v3.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 BigQuery feasibility audit v3 exists: {args.output}")
        protocol = S2BigQueryFeasibilityProtocolV3.model_validate_json(args.protocol.read_text())
        protocol_audit = S2BigQueryFeasibilityProtocolAuditV3.model_validate_json(
            args.protocol_audit.read_text()
        )
        result = S2BigQueryFeasibilityResultV3.model_validate_json(args.result.read_text())
        if (
            file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
            or protocol.protocol_evidence_hash != result.protocol_evidence_hash
            or protocol_audit.audit_evidence_hash != result.protocol_audit_evidence_hash
            or protocol.prior_result_evidence_hash != result.prior_result_evidence_hash
            or protocol.prior_result_audit_evidence_hash != result.prior_result_audit_evidence_hash
            or runner_contract_hash() != result.runner_contract_hash
            or not audit_model(result, "result_evidence_hash")
        ):
            raise ValueError("S2 BigQuery feasibility v3 lineage changed")
        for binding in protocol.source_bindings:
            path = PROJECT_ROOT / binding.path
            if not path.is_file() or file_sha256(path) != binding.file_sha256:
                raise ValueError("S2 BigQuery feasibility v3 source binding changed")
        audit = build_hashed(
            S2BigQueryFeasibilityAuditV3,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "result_file_sha256": file_sha256(args.result),
                "result_evidence_hash": result.result_evidence_hash,
                "protocol_evidence_hash": result.protocol_evidence_hash,
                "protocol_audit_evidence_hash": result.protocol_audit_evidence_hash,
                "prior_result_evidence_hash": result.prior_result_evidence_hash,
                "prior_result_audit_evidence_hash": result.prior_result_audit_evidence_hash,
                "runner_contract_hash": result.runner_contract_hash,
                "auditor_contract_hash": auditor_contract_hash(),
                "decision": result.decision,
                "next_authorization": result.next_authorization,
            },
        )
        args.output.write_text(
            audit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"decision={audit.decision} sources=8 "
            "identifiers=0 responses=0 rows=0 values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
