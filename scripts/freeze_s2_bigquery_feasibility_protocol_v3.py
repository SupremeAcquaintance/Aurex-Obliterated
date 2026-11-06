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
    S2FeasibilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (  # noqa: E402
    S2_FEASIBILITY_V2_BLOCK_DRY_RUN,
    S2BigQueryFeasibilityAuditV2,
    S2BigQueryFeasibilityProtocolAuditV2,
    S2BigQueryFeasibilityProtocolV2,
    S2BigQueryFeasibilityResultV2,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (  # noqa: E402
    S2BigQueryFeasibilityProtocolV3,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_protocol_v3.json")
V2_PROTOCOL_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_v2.json")
V2_PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v2.json")
V2_RESULT_PATH = Path("data/evidence/s2_bigquery_feasibility_result_v2.json")
V2_RESULT_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_audit_v2.json")
V2_RUNNER_PATH = Path("scripts/run_s2_bigquery_feasibility_v2.py")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_feasibility_v3.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "builder_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "builder_sha256": file_sha256(Path(__file__)),
        }
    )


def load_v2_lineage():
    protocol = S2BigQueryFeasibilityProtocolV2.model_validate_json(V2_PROTOCOL_PATH.read_text())
    protocol_audit = S2BigQueryFeasibilityProtocolAuditV2.model_validate_json(
        V2_PROTOCOL_AUDIT_PATH.read_text()
    )
    result = S2BigQueryFeasibilityResultV2.model_validate_json(V2_RESULT_PATH.read_text())
    result_audit = S2BigQueryFeasibilityAuditV2.model_validate_json(
        V2_RESULT_AUDIT_PATH.read_text()
    )
    if (
        file_sha256(V2_PROTOCOL_PATH) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != result.protocol_evidence_hash
        or result.result_evidence_hash != result_audit.result_evidence_hash
        or result.decision != S2_FEASIBILITY_V2_BLOCK_DRY_RUN
        or len(result.metadata_attempts) != 3
        or not all(item.error_class == "NONE" for item in result.metadata_attempts)
        or result.dry_run_request_count != 1
        or result.sandbox_without_billing_verified is not True
    ):
        raise ValueError("S2 BigQuery v2 amendment basis did not reconcile")
    return protocol, protocol_audit, result, result_audit


def build_protocol(*, frozen_at: datetime) -> S2BigQueryFeasibilityProtocolV3:
    protocol_v2, protocol_audit_v2, result_v2, result_audit_v2 = load_v2_lineage()
    response_paths = tuple(
        Path(item.response_path)
        for item in result_v2.metadata_attempts
        if item.response_path is not None
    )
    if len(response_paths) != 3:
        raise ValueError("S2 BigQuery v2 metadata artifacts are incomplete")
    source_paths = (
        V2_PROTOCOL_PATH,
        V2_PROTOCOL_AUDIT_PATH,
        V2_RESULT_PATH,
        V2_RESULT_AUDIT_PATH,
        V2_RUNNER_PATH,
        *response_paths,
    )
    if len(source_paths) != 8 or not all(path.is_file() for path in source_paths):
        raise ValueError("S2 BigQuery v3 source set is incomplete")
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": protocol_v2.charter_evidence_hash,
        "prior_protocol_evidence_hash": protocol_v2.protocol_evidence_hash,
        "prior_protocol_audit_evidence_hash": protocol_audit_v2.audit_evidence_hash,
        "prior_result_evidence_hash": result_v2.result_evidence_hash,
        "prior_result_audit_evidence_hash": result_audit_v2.audit_evidence_hash,
        "prior_result_decision": result_v2.decision,
        "source_bindings": tuple(
            S2FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
            for path in sorted(source_paths, key=lambda item: item.as_posix())
        ),
        "dry_run_specs": protocol_v2.dry_run_specs,
        "limitations": tuple(
            sorted(
                (
                    "A feasibility pass cannot establish predictive edge.",
                    "Dry-run byte estimates can differ from later processed bytes.",
                    "No account, project, credential, token, or raw response may enter evidence.",
                    "No numeric query may run without a separately frozen payload protocol.",
                    "The no-billing boundary must be verified before REST dry-runs.",
                    "This amendment preserves the v2 CLI dry-run failure as negative evidence.",
                    "This stage returns no blockchain rows, market values, or outcomes.",
                )
            )
        ),
    }
    return build_hashed(
        S2BigQueryFeasibilityProtocolV3,
        "protocol_evidence_hash",
        values,
    )


def write_protocol(path: Path, protocol: S2BigQueryFeasibilityProtocolV3) -> None:
    if path.exists():
        raise ValueError(f"S2 BigQuery feasibility protocol v3 exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2BigQueryFeasibilityProtocolV3.model_validate_json(serialized) != protocol:
        raise ValueError("S2 BigQuery feasibility protocol v3 did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 BigQuery REST dry-run v3.")
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
            "requests=0 identifiers=0 responses=0 values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
