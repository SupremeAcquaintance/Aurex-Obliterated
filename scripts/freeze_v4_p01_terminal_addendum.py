import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_v4_p01_feasibility_contract import (  # noqa: E402
    V4P01_REQUIRED_GATE_IDS,
)
from aurex.backtest_engine.research_v4_p01_feasibility_runner import (  # noqa: E402
    V4P01ExecutionGateResult,
    V4P01SourceObservation,
)
from aurex.backtest_engine.research_v4_p01_terminal_addendum import (  # noqa: E402
    V4P01TerminalAuditAddendum,
    V4P01TerminalDefectAssessment,
    audit_v4_p01_terminal_audit_addendum,
    build_v4_p01_terminal_audit_addendum,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_p01_continuation_contract import (  # noqa: E402
    DEFAULT_CHARTER,
    DEFAULT_ORIGINAL_CONTRACT,
    DEFAULT_REGISTER,
)
from scripts.freeze_v4_p01_continuation_contract import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CONTINUATION_CONTRACT,
)
from scripts.run_v4_p01_continuation import (  # noqa: E402
    audit_continuation_terminal,
    load_continuation_contract,
    reconstruct_continuation_journal,
    runner_contract_hash,
)
from scripts.run_v4_p01_feasibility import (  # noqa: E402
    _decode_raw_payload,
    _values_for_keys,
    file_sha256,
    load_ndjson,
    safe_project_path,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/v4_p01_terminal_audit_addendum_v1.json"
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


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v4_p01_terminal_addendum.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p01_terminal_addendum.py",
        ]
    )


def inspect_identity_only(
    *,
    continuation,
    terminal,
) -> dict[str, list[str]]:
    journal_path = PROJECT_ROOT / continuation.journal_path
    records = reconstruct_continuation_journal(
        continuation,
        journal_path,
    )
    responses = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    identity_map: dict[str, list[str]] = {}
    for request in continuation.requests:
        response = responses.get(request.request_id)
        if response is None or response.raw_relative_path is None:
            raise ValueError("V4P01 addendum response evidence is incomplete")
        raw_path = safe_project_path(
            PROJECT_ROOT,
            response.raw_relative_path,
        )
        if (
            file_sha256(raw_path) != response.payload_sha256
            or raw_path.stat().st_size != response.byte_count
        ):
            raise ValueError("V4P01 addendum raw response audit failed")
        decoded = _decode_raw_payload(raw_path, response.response_headers)
        identities: set[str] = set()
        for line in decoded.decode("utf-8").splitlines():
            if not line.strip():
                continue
            _, separator, json_text = line.partition(" ")
            if not separator:
                raise ValueError("V4P01 addendum raw line is malformed")
            message = json.loads(json_text)
            if not isinstance(message, dict):
                raise ValueError("V4P01 addendum raw message is not an object")
            identities.update(
                item
                for item in _values_for_keys(
                    message,
                    {"product_id", "productId", "s", "symbol"},
                )
                if isinstance(item, str)
            )
        if not identities or any(
            item.casefold() != request.product_id.casefold()
            for item in identities
        ):
            raise ValueError("V4P01 addendum product identity does not reconcile")
        identity_map[request.request_id] = sorted(identities)
    if (
        terminal.terminal_kind != "REJECT"
        or terminal.decision != "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    ):
        raise ValueError("V4P01 addendum terminal decision changed")
    return identity_map


def corrected_gate_results(
    *,
    terminal,
    payload_observations: list[V4P01SourceObservation],
) -> list[V4P01ExecutionGateResult]:
    original = {
        item.gate_id: item for item in terminal.execution_gate_results
    }
    snapshot_failures = [
        item.request_id
        for item in payload_observations
        if any(
            channel in item.missing_required_schema_keys
            for channel in ("depthSnapshot", "snapshot")
        )
    ]
    if len(snapshot_failures) != 4:
        raise ValueError("V4P01 expected snapshot-schema failures changed")
    if any(item.source_revision_identity for item in payload_observations):
        raise ValueError("V4P01 source revision evidence unexpectedly changed")
    original["COMMON_ETH_BTC_PRODUCT_IDENTITY"] = V4P01ExecutionGateResult(
        gate_id="COMMON_ETH_BTC_PRODUCT_IDENTITY",
        status="PASS",
        evidence_hashes=[
            item.observation_evidence_hash for item in payload_observations
        ],
        reason=(
            "Metadata, frozen request filters, and identity-only raw-wire audit "
            "reconcile Binance ethbtc with wire symbol ETHBTC and preserve exact "
            "Coinbase ETH-BTC identity."
        ),
    )
    original["RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES"] = (
        V4P01ExecutionGateResult(
            gate_id="RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES",
            status="FAIL",
            evidence_hashes=[
                item.observation_evidence_hash for item in payload_observations
            ],
            reason=(
                "After correcting Binance wire-symbol case, four of six frozen "
                "pilots still contain no required depthSnapshot or snapshot "
                "message, so recovery schema coverage is not proven."
            ),
        )
    )
    return [original[gate_id] for gate_id in V4P01_REQUIRED_GATE_IDS]


def load_evidence():
    (
        continuation,
        original,
        original_terminal,
        metadata_observations,
        corrected_gate,
    ) = load_continuation_contract(
        charter_path=DEFAULT_CHARTER,
        register_path=DEFAULT_REGISTER,
        original_contract_path=DEFAULT_ORIGINAL_CONTRACT,
        continuation_contract_path=DEFAULT_CONTINUATION_CONTRACT,
    )
    terminal = audit_continuation_terminal(
        contract=continuation,
        metadata_observations=metadata_observations,
        project_root=PROJECT_ROOT,
    )
    payload_observations = load_ndjson(
        PROJECT_ROOT / continuation.payload_observation_path,
        V4P01SourceObservation,
    )
    if len(payload_observations) != 6:
        raise ValueError("V4P01 addendum payload observation matrix changed")
    return (
        continuation,
        original,
        original_terminal,
        corrected_gate,
        terminal,
        payload_observations,
    )


def authoritative_addendum(
    *,
    audited_at: datetime,
    continuation,
    original,
    original_terminal,
    corrected_gate,
    terminal,
    payload_observations,
) -> V4P01TerminalAuditAddendum:
    identity_map = inspect_identity_only(
        continuation=continuation,
        terminal=terminal,
    )
    gates = corrected_gate_results(
        terminal=terminal,
        payload_observations=payload_observations,
    )
    return build_v4_p01_terminal_audit_addendum(
        audited_at=audited_at,
        original_contract_evidence_hash=original.contract_evidence_hash,
        original_terminal_reject_evidence_hash=(
            original_terminal.result_evidence_hash
        ),
        continuation_contract_evidence_hash=(
            continuation.contract_evidence_hash
        ),
        continuation_terminal_reject_evidence_hash=(
            terminal.result_evidence_hash
        ),
        continuation_runner_contract_hash=runner_contract_hash(),
        corrected_metadata_gate_evidence_hash=(
            corrected_gate.result_evidence_hash
        ),
        payload_observation_hashes=[
            item.observation_evidence_hash for item in payload_observations
        ],
        builder_contract_hash=builder_contract_hash(),
        identity_observations_by_request=identity_map,
        defect_assessments=[
            V4P01TerminalDefectAssessment(
                defect_id="BINANCE_QUERY_ID_VS_WIRE_SYMBOL_CASE",
                defect_class="IDENTITY_NORMALIZATION_DEFECT",
                original_effect=(
                    "The payload parser compared Binance raw wire symbol ETHBTC "
                    "case-sensitively with the Tardis request filter id ethbtc and "
                    "recorded product_identity_matches=false."
                ),
                corrected_interpretation=(
                    "The Tardis filter identity remains lowercase ethbtc while "
                    "Binance exchange-native payloads use uppercase ETHBTC; "
                    "case-normalized identity reconciliation passes."
                ),
            ),
            V4P01TerminalDefectAssessment(
                defect_id="COMMON_PRODUCT_GATE_REASON_STATUS_INCONSISTENCY",
                defect_class="GATE_STATUS_REASON_INCONSISTENCY",
                original_effect=(
                    "The continuation terminal marked common-product identity "
                    "PASS while its reason incorrectly claimed every payload "
                    "already matched the frozen identifier."
                ),
                corrected_interpretation=(
                    "Common-product identity passes only after the explicit "
                    "identity-only wire audit; the original reason is superseded "
                    "by this addendum without changing the terminal rejection."
                ),
            ),
        ],
        corrected_execution_gate_results=gates,
        decisive_rejection_gate_ids=[
            "POINT_IN_TIME_FEES_AND_FEE_CURRENCY",
            "POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE",
            "RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES",
            "SOURCE_REVISION_AND_BYTE_INTEGRITY",
        ],
        limitations=[
            (
                "This addendum reads only product identity strings from verified "
                "raw bytes and does not inspect numeric market values."
            ),
            (
                "The original and continuation terminal artifacts remain "
                "immutable and independently auditable."
            ),
            (
                "Correcting Binance symbol case does not supply the four missing "
                "recovery snapshots."
            ),
            (
                "Correcting one gate reason does not provide upstream source "
                "revision identifiers."
            ),
            (
                "Point-in-time fees, filters, product state, venue state, account "
                "access, inventory, and two-leg execution remain unproven."
            ),
            (
                "No request, retry, new sample, market-value analysis, return "
                "test, candidate, or trading permission is authorized."
            ),
            (
                "V4P01 remains rejected before primary selection on four "
                "independent decisive hard gates."
            ),
        ],
    )


def write_addendum(path: Path, addendum: V4P01TerminalAuditAddendum) -> None:
    serialized = (addendum.model_dump_json(indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V4P01 addendum output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def run_check(args) -> V4P01TerminalAuditAddendum:
    evidence = load_evidence()
    stored = V4P01TerminalAuditAddendum.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_addendum(
        audited_at=stored.audited_at,
        continuation=evidence[0],
        original=evidence[1],
        original_terminal=evidence[2],
        corrected_gate=evidence[3],
        terminal=evidence[4],
        payload_observations=evidence[5],
    )
    if stored != expected or not audit_v4_p01_terminal_audit_addendum(stored):
        raise ValueError("Frozen V4P01 terminal addendum audit failed")
    print(
        f"PASS v4p01_addendum={stored.addendum_evidence_hash} "
        f"decision={stored.invariant_decision} "
        f"decisive_failures={len(stored.decisive_rejection_gate_ids)} "
        f"network={stored.authorizes_network_requests} "
        f"returns={stored.calculates_signals_trades_pnl_or_returns}",
        flush=True,
    )
    return stored


def run_freeze(args) -> V4P01TerminalAuditAddendum:
    if args.output.exists():
        raise ValueError("V4P01 terminal addendum exists; use --check")
    evidence = load_evidence()
    addendum = authoritative_addendum(
        audited_at=datetime.now(UTC),
        continuation=evidence[0],
        original=evidence[1],
        original_terminal=evidence[2],
        corrected_gate=evidence[3],
        terminal=evidence[4],
        payload_observations=evidence[5],
    )
    write_addendum(args.output, addendum)
    return run_check(args)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or audit the non-authorizing V4P01 terminal explanation "
            "correction."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            run_check(args)
        else:
            run_freeze(args)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
