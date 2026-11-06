import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3P03SourceAuditContract,
    audit_v3_p03_source_audit_contract,
)
from aurex.backtest_engine.research_v3_p03_stop_result import (
    V3P03FailedAttemptEvidence,
    V3P03SourceAuditStopResult,
    audit_v3_p03_source_audit_stop_result,
    build_v3_p03_source_audit_stop_result,
)
from aurex.backtest_engine.research_v3_p03_transport_amendment import (
    V3P03TransportAmendment,
    audit_v3_p03_transport_amendment,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "data/evidence/v3_p03_source_audit_contract_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/v3_p03_transport_amendment_v1.json"
)
DEFAULT_INITIAL_ATTEMPT = Path(
    "data/evidence/source_snapshots/"
    "v3_p03_source_audit_v1_failed_http_202_attempt/attempt_manifest.json"
)
DEFAULT_EXHAUSTED_ATTEMPT = Path(
    "data/evidence/source_snapshots/"
    "v3_p03_source_audit_v1_failed_http_202_exhausted_attempt/"
    "attempt_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p03_source_audit_stop_result_v1.json"
)


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def source_audit_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p03_source_audit_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
        ]
    )


def amendment_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p03_transport_amendment.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_transport_amendment.py",
        ]
    )


def source_runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p03_source_audit.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
        ]
    )


def finalizer_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "finalize_v3_p03_source_audit_stop.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_stop_result.py",
        ]
    )


def load_inputs(
    contract_path: Path,
    amendment_path: Path,
) -> tuple[V3P03SourceAuditContract, V3P03TransportAmendment]:
    contract = V3P03SourceAuditContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_source_audit_contract(contract)
        or contract.builder_contract_hash != source_audit_builder_hash()
    ):
        raise ValueError("V3P03 source audit contract failed final audit")
    amendment = V3P03TransportAmendment.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_transport_amendment(amendment)
        or amendment.builder_contract_hash != amendment_builder_hash()
        or amendment.original_contract_evidence_hash
        != contract.contract_evidence_hash
    ):
        raise ValueError("V3P03 transport amendment failed final audit")
    return contract, amendment


def load_attempt(
    path: Path,
    attempt_id: str,
    contract: V3P03SourceAuditContract,
    amendment: V3P03TransportAmendment,
) -> V3P03FailedAttemptEvidence:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["original_contract_evidence_hash"] != contract.contract_evidence_hash:
        raise ValueError("V3P03 attempt contract binding changed")
    if attempt_id == "AMENDED_HTTP_202_EXHAUSTED":
        if (
            payload.get("transport_amendment_evidence_hash")
            != amendment.amendment_evidence_hash
        ):
            raise ValueError("V3P03 attempt amendment binding changed")
    for artifact in payload["preserved_source_artifacts"]:
        artifact_path = Path(artifact["path"])
        data = artifact_path.read_bytes()
        if (
            len(data) != artifact["bytes"]
            or hashlib.sha256(data).hexdigest() != artifact["sha256"]
        ):
            raise ValueError(
                f"V3P03 preserved attempt artifact changed: {artifact_path}"
            )
    return V3P03FailedAttemptEvidence(
        attempt_id=attempt_id,
        manifest_path=path.as_posix(),
        manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        started_at=payload["attempt_started_at_utc"],
        status=payload["status"],
        completed_source_count=payload["completed_source_count"],
        http_request_attempt_count=payload["http_request_attempt_count"],
        trigger_source_id=payload["trigger_source_id"],
        trigger_http_statuses=payload["trigger_http_statuses"],
        pending_poll_budget_exhausted=payload[
            "pending_poll_budget_exhausted"
        ],
        authoritative_result_created=payload["authoritative_result_created"],
        market_values_inspected=payload["market_values_inspected"],
        strategy_outcomes_inspected=payload["strategy_outcomes_inspected"],
        return_metrics_calculated=payload["return_metrics_calculated"],
    )


def authoritative_result(
    *,
    generated_at: datetime,
    contract: V3P03SourceAuditContract,
    amendment: V3P03TransportAmendment,
    attempts: list[V3P03FailedAttemptEvidence],
) -> V3P03SourceAuditStopResult:
    return build_v3_p03_source_audit_stop_result(
        generated_at=generated_at,
        source_audit_contract_evidence_hash=contract.contract_evidence_hash,
        transport_amendment_evidence_hash=amendment.amendment_evidence_hash,
        source_runner_contract_hash=source_runner_contract_hash(),
        finalizer_contract_hash=finalizer_contract_hash(),
        attempts=attempts,
        limitations=[
            (
                "The formal V3P03 audit did not complete and therefore evaluated "
                "zero of eight source requirements."
            ),
            (
                "Both bounded runs stopped at the same official schema target after "
                "HTTP 202; neither produced a partial authoritative result."
            ),
            (
                "The transport amendment changed no source target, qualification "
                "threshold, decision rule, or market-value permission."
            ),
            (
                "Unresolved source evidence cannot be assumed available and cannot "
                "support primary selection under the frozen all-or-nothing rule."
            ),
            (
                "This stop result makes no claim that passive liquidity provision is "
                "universally unprofitable; it records that Aurex cannot qualify it "
                "from the frozen source path in this discovery round."
            ),
            (
                "No price, quantity, depth, notional, signal, fill, trade outcome, "
                "PnL, or return value was inspected."
            ),
            (
                "V3P03 is rejected before primary selection and creates no candidate, "
                "validation, holdout, forward, Pine, paper, sandbox, live, or capital "
                "permission."
            ),
        ],
    )


def write_result(path: Path, result: V3P03SourceAuditStopResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V3P03SourceAuditStopResult.model_validate_json(serialized) != result:
        raise ValueError("V3P03 stop result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def load_attempts(args, contract, amendment):
    return [
        load_attempt(
            args.initial_attempt,
            "INITIAL_HTTP_202",
            contract,
            amendment,
        ),
        load_attempt(
            args.exhausted_attempt,
            "AMENDED_HTTP_202_EXHAUSTED",
            contract,
            amendment,
        ),
    ]


def run_finalize(args) -> V3P03SourceAuditStopResult:
    if args.output.exists():
        raise ValueError("Frozen V3P03 stop result exists; use --audit")
    contract, amendment = load_inputs(args.contract, args.amendment)
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        contract=contract,
        amendment=amendment,
        attempts=load_attempts(args, contract, amendment),
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"attempts={result.attempted_run_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return run_audit(args)


def run_audit(args) -> V3P03SourceAuditStopResult:
    contract, amendment = load_inputs(args.contract, args.amendment)
    result = V3P03SourceAuditStopResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if not audit_v3_p03_source_audit_stop_result(result):
        raise ValueError("V3P03 stop result hash audit failed")
    expected = authoritative_result(
        generated_at=result.generated_at,
        contract=contract,
        amendment=amendment,
        attempts=load_attempts(args, contract, amendment),
    )
    if result != expected:
        raise ValueError("V3P03 stop result is not reproducible")
    print(
        "PASS "
        f"v3p03_stop={result.result_evidence_hash} "
        f"attempts={result.attempted_run_count} "
        f"evaluated={len(result.evaluated_requirement_ids)}/8 "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Finalize or audit the V3P03 source-audit stop after bounded "
            "transport exhaustion."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--finalize", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--initial-attempt",
        type=Path,
        default=DEFAULT_INITIAL_ATTEMPT,
    )
    parser.add_argument(
        "--exhausted-attempt",
        type=Path,
        default=DEFAULT_EXHAUSTED_ATTEMPT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.finalize:
            run_finalize(args)
        else:
            run_audit(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
