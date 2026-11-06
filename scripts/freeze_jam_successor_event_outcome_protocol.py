from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_distribution_protocol import (  # noqa: E402
    JamSuccessorDevelopmentDistributionProtocol,
    audit_jam_successor_distribution_protocol,
)
from aurex.backtest_engine.jam_successor_distribution_result import (  # noqa: E402
    JAM_DISTRIBUTION_NEXT_AUTHORIZATION,
    JAM_DISTRIBUTION_PASS_DECISION,
    JamSuccessorDevelopmentDistributionAudit,
    JamSuccessorDevelopmentDistributionResult,
    audit_jam_successor_distribution_audit,
    audit_jam_successor_distribution_result,
)
from aurex.backtest_engine.jam_successor_event_outcome_protocol import (  # noqa: E402
    JAM_EVENT_CONDITION_SPECS,
    JamEventCondition,
    JamEventDefinition,
    JamSuccessorEventOutcomeProtocol,
    audit_jam_successor_event_outcome_protocol,
    build_jam_successor_event_outcome_protocol,
)
from aurex.backtest_engine.jam_successor_feature_specification import (  # noqa: E402
    JamSuccessorFeatureSpecification,
    audit_jam_successor_feature_specification,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_DISTRIBUTION_PROTOCOL = Path(
    "data/evidence/jam_successor_development_distribution_protocol_v1.json"
)
DEFAULT_DISTRIBUTION_RESULT = Path(
    "data/evidence/jam_successor_development_distribution_result_v1.json"
)
DEFAULT_DISTRIBUTION_AUDIT = Path(
    "data/evidence/jam_successor_development_distribution_audit_v1.json"
)
DEFAULT_FEATURE_ROWS = Path("data/evidence/jam_successor_development_feature_rows_v1.parquet")
DEFAULT_FEATURE_SPECIFICATION = Path("data/evidence/jam_successor_feature_specification_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/jam_successor_event_outcome_protocol_v1.json")

EXPECTED_DISTRIBUTION_PROTOCOL_FILE_SHA256 = (
    "f56eff43ca8868786b55b047041ce3d453ec5cb60ac3754ba1c76dfea03cc6d1"
)
EXPECTED_DISTRIBUTION_PROTOCOL_EVIDENCE_HASH = (
    "8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551"
)
EXPECTED_DISTRIBUTION_RESULT_FILE_SHA256 = (
    "be5e863b6a12b8d37646a6899cab3ee1b4808d429dac6ceaf53a693926ff8cc8"
)
EXPECTED_DISTRIBUTION_RESULT_EVIDENCE_HASH = (
    "d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef"
)
EXPECTED_DISTRIBUTION_AUDIT_FILE_SHA256 = (
    "477782c388c8e43adf5da397c640577e3f37b647e4513909c6d68478e7d28840"
)
EXPECTED_DISTRIBUTION_AUDIT_EVIDENCE_HASH = (
    "7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b"
)
EXPECTED_FEATURE_ROWS_FILE_SHA256 = (
    "fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa"
)
EXPECTED_FEATURE_ROWS_SCHEMA_HASH = (
    "15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b"
)
EXPECTED_FEATURE_SPECIFICATION_EVIDENCE_HASH = (
    "8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path) for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_jam_successor_event_outcome_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_event_outcome_protocol.py",
        ]
    )


def load_inputs(
    *,
    distribution_protocol_path: Path,
    distribution_result_path: Path,
    distribution_audit_path: Path,
    feature_rows_path: Path,
    feature_specification_path: Path,
) -> tuple[
    JamSuccessorDevelopmentDistributionProtocol,
    JamSuccessorDevelopmentDistributionResult,
    JamSuccessorDevelopmentDistributionAudit,
    JamSuccessorFeatureSpecification,
]:
    distribution_protocol = JamSuccessorDevelopmentDistributionProtocol.model_validate_json(
        distribution_protocol_path.read_text(encoding="utf-8")
    )
    distribution_result = JamSuccessorDevelopmentDistributionResult.model_validate_json(
        distribution_result_path.read_text(encoding="utf-8")
    )
    distribution_audit = JamSuccessorDevelopmentDistributionAudit.model_validate_json(
        distribution_audit_path.read_text(encoding="utf-8")
    )
    feature_specification = JamSuccessorFeatureSpecification.model_validate_json(
        feature_specification_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_successor_distribution_protocol(distribution_protocol)
        or not audit_jam_successor_distribution_result(distribution_result)
        or not audit_jam_successor_distribution_audit(distribution_audit)
        or not audit_jam_successor_feature_specification(feature_specification)
        or file_sha256(distribution_protocol_path) != EXPECTED_DISTRIBUTION_PROTOCOL_FILE_SHA256
        or distribution_protocol.protocol_evidence_hash
        != EXPECTED_DISTRIBUTION_PROTOCOL_EVIDENCE_HASH
        or file_sha256(distribution_result_path) != EXPECTED_DISTRIBUTION_RESULT_FILE_SHA256
        or distribution_result.result_evidence_hash != EXPECTED_DISTRIBUTION_RESULT_EVIDENCE_HASH
        or file_sha256(distribution_audit_path) != EXPECTED_DISTRIBUTION_AUDIT_FILE_SHA256
        or distribution_audit.audit_evidence_hash != EXPECTED_DISTRIBUTION_AUDIT_EVIDENCE_HASH
        or file_sha256(feature_rows_path) != EXPECTED_FEATURE_ROWS_FILE_SHA256
        or distribution_result.feature_rows_file_sha256 != EXPECTED_FEATURE_ROWS_FILE_SHA256
        or distribution_result.feature_rows_schema_hash != EXPECTED_FEATURE_ROWS_SCHEMA_HASH
        or feature_specification.specification_evidence_hash
        != EXPECTED_FEATURE_SPECIFICATION_EVIDENCE_HASH
        or distribution_result.protocol_evidence_hash
        != distribution_protocol.protocol_evidence_hash
        or distribution_audit.result_evidence_hash != distribution_result.result_evidence_hash
        or distribution_audit.feature_rows_file_sha256
        != distribution_result.feature_rows_file_sha256
        or distribution_result.feature_specification_evidence_hash
        != feature_specification.specification_evidence_hash
        or distribution_result.decision != JAM_DISTRIBUTION_PASS_DECISION
        or distribution_result.next_required_authorization != JAM_DISTRIBUTION_NEXT_AUTHORIZATION
        or distribution_result.sealed_market_periods_opened
        or distribution_result.future_labels_defined
        or distribution_result.event_thresholds_defined
        or distribution_result.return_metrics_calculated
        or distribution_result.strategy_executions
    ):
        raise ValueError("Jam event/outcome parent lineage changed")
    return (
        distribution_protocol,
        distribution_result,
        distribution_audit,
        feature_specification,
    )


def event_definition(
    result: JamSuccessorDevelopmentDistributionResult,
) -> JamEventDefinition:
    distributions = {item.feature_id: item for item in result.feature_distributions}
    roles = {
        "EXTREME_AGGRESSIVE_SELL_FLOW": (
            "Require an unusually intense taker-sell shock relative to its causal baseline."
        ),
        "SELL_SIDE_DOMINANCE": (
            "Require taker sellers to contribute at least the frozen median "
            "share of shock quote flow."
        ),
        "NEGATIVE_SHOCK_PRICE_IMPACT": (
            "Require the shock to have produced negative causal price impact."
        ),
        "CONFIRMATION_FLOW_DECAY": (
            "Require confirmation sell flow to decay relative to shock flow."
        ),
        "CAUSAL_PRICE_RECLAIM": ("Require the confirmation close to reclaim the pre-shock VWAP."),
    }
    conditions = []
    for condition_id, feature_id, comparison, quantile in JAM_EVENT_CONDITION_SPECS:
        metric = distributions[feature_id]
        conditions.append(
            JamEventCondition(
                condition_id=condition_id,
                feature_id=feature_id,
                comparison=comparison,
                source_quantile=quantile,
                frozen_threshold=metric.quantiles[quantile],
                mechanism_role=roles[condition_id],
            )
        )
    return JamEventDefinition(conditions=conditions)


def authoritative_protocol(
    *,
    frozen_at: datetime,
    inputs: tuple,
    distribution_protocol_path: Path,
    distribution_result_path: Path,
    distribution_audit_path: Path,
    feature_rows_path: Path,
) -> JamSuccessorEventOutcomeProtocol:
    distribution_protocol = inputs[0]
    distribution_result = inputs[1]
    distribution_audit = inputs[2]
    feature_specification = inputs[3]
    definition = event_definition(distribution_result)
    return build_jam_successor_event_outcome_protocol(
        frozen_at=frozen_at,
        distribution_protocol_path=distribution_protocol_path.as_posix(),
        distribution_protocol_file_sha256=file_sha256(distribution_protocol_path),
        distribution_protocol_evidence_hash=(distribution_protocol.protocol_evidence_hash),
        distribution_result_path=distribution_result_path.as_posix(),
        distribution_result_file_sha256=file_sha256(distribution_result_path),
        distribution_result_evidence_hash=(distribution_result.result_evidence_hash),
        distribution_audit_path=distribution_audit_path.as_posix(),
        distribution_audit_file_sha256=file_sha256(distribution_audit_path),
        distribution_audit_evidence_hash=(distribution_audit.audit_evidence_hash),
        feature_rows_path=feature_rows_path.as_posix(),
        feature_rows_file_sha256=distribution_result.feature_rows_file_sha256,
        feature_rows_schema_hash=distribution_result.feature_rows_schema_hash,
        feature_rows_bytes=distribution_result.feature_rows_bytes,
        feature_specification_evidence_hash=(feature_specification.specification_evidence_hash),
        builder_contract_hash=builder_contract_hash(),
        event_definition=definition,
        distribution_statistics_accessed=[
            (f"{condition.feature_id}|{condition.source_quantile}|{condition.frozen_threshold}")
            for condition in definition.conditions
        ],
        limitations=[
            (
                "This protocol is frozen after marginal development feature "
                "distributions but before calculating any event flag or outcome."
            ),
            ("Only one long event predicate and one primary thirty-minute horizon are selectable."),
            (
                "The fifteen- and sixty-minute horizons are diagnostics and "
                "cannot replace or rescue the primary."
            ),
            (
                "All five event conditions are conjunctive; no score, rank, "
                "learned model, or threshold variant is permitted."
            ),
            (
                "Event thresholds are fixed numeric values from the accepted "
                "2019-2020 marginal quantiles and may never be re-estimated."
            ),
            (
                "Development event prevalence must pass every frozen gate before "
                "future outcome calculation may be authorized."
            ),
            (
                "A prevalence failure stops the mechanism; thresholds may not be "
                "relaxed to manufacture sample size."
            ),
            (
                "Accepted events are chronological and separated by sixty minutes "
                "so primary and diagnostic outcome windows cannot overlap."
            ),
            (
                "Missing, quarantined, or cross-partition path minutes make an "
                "outcome unavailable; no price or minute may be synthesized."
            ),
            ("Base costs use 0.10 percent commission per side and two adverse ticks per fill."),
            ("Stress costs use 0.15 percent commission per side and ten adverse ticks per fill."),
            (
                "Testnet zero commissions are not evidence for historical or "
                "future economic viability."
            ),
            (
                "Matched controls use feature/time strata only and may not use "
                "future outcomes for selection."
            ),
            (
                "Unmatched events remain in event evidence but cannot enter the "
                "matched-control contrast."
            ),
            (
                "Development gates are conjunctive; no manual waiver, weighted "
                "score, or diagnostic rescue is permitted."
            ),
            (
                "The one-sided confidence bounds use a frozen month-cluster "
                "bootstrap with 10,000 repetitions and fixed seed 20260805."
            ),
            (
                "Development must pass before 2021 validation can be requested, "
                "and 2021 must pass before 2022 holdout can be requested."
            ),
            (
                "Opening validation or holdout requires a new explicit "
                "authorization and an unchanged protocol hash."
            ),
            (
                "A failed development, validation, or holdout decision retires "
                "this event definition rather than allowing in-place redesign."
            ),
            (
                "This protocol creates no strategy, signal, candidate, sizing, "
                "entry order, exit order, stop, target, or paper eligibility."
            ),
            (
                "Exact Pine parity is unavailable because the mechanism depends "
                "on aggregate-trade aggressor identity."
            ),
            (
                "The consumed 2023-2025 Jam decision period and 2026 exploratory "
                "periods cannot support this mechanism's promotion."
            ),
            (
                "No production, live, real-capital, or profit authority is "
                "created; real net profit remains zero."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: JamSuccessorEventOutcomeProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if JamSuccessorEventOutcomeProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Jam event/outcome protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def input_args(args) -> tuple:
    return load_inputs(
        distribution_protocol_path=args.distribution_protocol,
        distribution_result_path=args.distribution_result,
        distribution_audit_path=args.distribution_audit,
        feature_rows_path=args.feature_rows,
        feature_specification_path=args.feature_specification,
    )


def run_freeze(args) -> JamSuccessorEventOutcomeProtocol:
    if args.output.exists():
        raise ValueError("Jam event/outcome protocol exists; use --check")
    inputs = input_args(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        inputs=inputs,
        distribution_protocol_path=args.distribution_protocol,
        distribution_result_path=args.distribution_result,
        distribution_audit_path=args.distribution_audit,
        feature_rows_path=args.feature_rows,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "events=0 labels=0 returns=0 validation=False holdout=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamSuccessorEventOutcomeProtocol:
    inputs = input_args(args)
    protocol = JamSuccessorEventOutcomeProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=inputs,
        distribution_protocol_path=args.distribution_protocol,
        distribution_result_path=args.distribution_result,
        distribution_audit_path=args.distribution_audit,
        feature_rows_path=args.feature_rows,
    )
    if protocol != expected or not audit_jam_successor_event_outcome_protocol(protocol):
        raise ValueError("Jam event/outcome protocol is not reproducible")
    print(
        "PASS "
        f"jam_event_outcome_protocol={protocol.protocol_evidence_hash} "
        f"conditions={len(protocol.event_definition.conditions)} "
        f"primary_horizon={protocol.statistical_plan.primary_horizon_minutes} "
        "events=0 labels=0 returns=0",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the Jam successor event and future-outcome protocol without "
            "calculating an event, label, or return."
        )
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--distribution-protocol",
        type=Path,
        default=DEFAULT_DISTRIBUTION_PROTOCOL,
    )
    parser.add_argument(
        "--distribution-result",
        type=Path,
        default=DEFAULT_DISTRIBUTION_RESULT,
    )
    parser.add_argument(
        "--distribution-audit",
        type=Path,
        default=DEFAULT_DISTRIBUTION_AUDIT,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--feature-specification",
        type=Path,
        default=DEFAULT_FEATURE_SPECIFICATION,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_check(args) if args.check else run_freeze(args)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
