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
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2DevelopmentMeasurementExecutionAddendum,
    S2DevelopmentMeasurementExecutionAudit,
)
from scripts.freeze_s2_development_measurement_execution import (  # noqa: E402
    DEFAULT_ADDENDUM,
    build_addendum,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_OUTPUT = Path("data/evidence/s2_development_measurement_execution_audit_v1.json")


def auditor_contract_hash() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S2 measurement execution authority.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--addendum", type=Path, default=DEFAULT_ADDENDUM)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S2 measurement execution audit exists: {args.output}")
        addendum = S2DevelopmentMeasurementExecutionAddendum.model_validate_json(
            args.addendum.read_text()
        )
        if addendum.builder_contract_hash != builder_contract_hash():
            raise ValueError("S2 measurement execution builder changed")
        if build_addendum(frozen_at=addendum.frozen_at) != addendum:
            raise ValueError("S2 measurement execution addendum did not reconstruct exactly")
        audit = build_hashed(
            S2DevelopmentMeasurementExecutionAudit,
            "audit_evidence_hash",
            {
                "audited_at": datetime.now(UTC),
                "addendum_file_sha256": file_sha256(args.addendum),
                "addendum_evidence_hash": addendum.addendum_evidence_hash,
                "protocol_evidence_hash": addendum.protocol_evidence_hash,
                "runner_contract_hash": addendum.runner_contract_hash,
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
            "payload_rows=0 measurements=0 market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
