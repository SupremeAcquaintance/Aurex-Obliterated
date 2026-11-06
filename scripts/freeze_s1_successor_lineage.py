from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.contamination import (  # noqa: E402
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1LineageRecord,
    S1SourceBinding,
    S1SuccessorLineageLedger,
    audit_s1_lineage,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_successor_charter.py")
SCRIPT_PATH = Path("scripts/freeze_s1_successor_lineage.py")

LINEAGE_DEFINITIONS = (
    {
        "lineage_id": "01-legacy-candle-strategies",
        "mechanism_families": (
            "intraday_trend_pullback",
            "intraday_volatility_breakout",
            "jam_reversal",
            "slow_trend_breakout_spot",
        ),
        "terminal_decision": "PARENT_CONTAMINATION_LEDGER_7_RECORDS",
        "terminal_stage": "MIXED_RETIRED_SET",
        "paths": ("data/evidence/strategy_contamination_ledger_v2.json",),
        "decision_field": None,
        "outcomes_opened": True,
        "successor_policy": "RETIRED_NO_RESCUE",
        "reason": (
            "Seven frozen strategy/window records preserve every inspected "
            "candle-strategy outcome and prevent renamed or nearby variants from "
            "being treated as fresh evidence."
        ),
    },
    {
        "lineage_id": "02-cross-sectional-momentum-path-quality",
        "mechanism_families": ("cross_sectional_momentum", "path_quality_momentum"),
        "terminal_decision": "RETIRE_R4_CANDIDATE",
        "terminal_stage": "OUTCOME_REJECTED",
        "paths": (
            "data/evidence/r31_path_quality_result_v1.json",
            "data/evidence/r3_cross_sectional_momentum_result_v1.json",
            "data/evidence/r4_path_quality_result_v1.json",
        ),
        "decision_field": "verdict",
        "decision_path": "data/evidence/r4_path_quality_result_v1.json",
        "outcomes_opened": True,
        "successor_policy": "RETIRED_NO_RESCUE",
        "reason": (
            "R3, R3.1, and R4 consumed the cross-sectional momentum and "
            "path-quality continuation family through development and validation, "
            "ending in candidate retirement."
        ),
    },
    {
        "lineage_id": "03-volatility-managed-broad-spot-beta",
        "mechanism_families": ("volatility_managed_broad_spot_beta",),
        "terminal_decision": "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA",
        "terminal_stage": "OUTCOME_REJECTED",
        "paths": ("data/evidence/u1_primary_mechanism_result_v1.json",),
        "decision_field": "verdict",
        "outcomes_opened": True,
        "successor_policy": "RETIRED_NO_RESCUE",
        "reason": (
            "The volatility-managed broad spot beta primary opened development "
            "returns and failed its frozen decision contract despite positive "
            "aggregate performance."
        ),
    },
    {
        "lineage_id": "04-positive-funding-carry",
        "mechanism_families": ("delta_neutral_positive_funding_carry",),
        "terminal_decision": "STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA",
        "terminal_stage": "SOURCE_REJECTED",
        "paths": ("data/evidence/v2_p01_full_acquisition_result_v1.json",),
        "decision_field": "decision",
        "outcomes_opened": False,
        "successor_policy": "CLOSED_COUNTS_FOR_MULTIPLICITY",
        "reason": (
            "The delta-neutral funding-carry source path failed its predeclared "
            "historical data sufficiency gate before any return was calculated."
        ),
    },
    {
        "lineage_id": "05-v3-independent-mechanisms",
        "mechanism_families": (
            "clock_phase_intraday_predictability",
            "cross_asset_cointegration_relative_value",
            "passive_limit_order_liquidity_provision",
        ),
        "terminal_decision": "SELECT_ZERO_V3_PRIMARY_MECHANISMS",
        "terminal_stage": "FEASIBILITY_REJECTED",
        "paths": ("data/evidence/v3_mechanism_feasibility_screen_v1.json",),
        "decision_field": "decision",
        "outcomes_opened": False,
        "successor_policy": "CLOSED_COUNTS_FOR_MULTIPLICITY",
        "reason": (
            "All three V3 mechanisms failed source or execution feasibility before "
            "primary selection, parameters, or returns."
        ),
    },
    {
        "lineage_id": "06-v4-independent-mechanisms",
        "mechanism_families": (
            "delta_hedged_crypto_variance_risk_premium",
            "inventory_backed_cross_venue_arbitrage",
        ),
        "terminal_decision": "SELECT_ZERO_V4_PRIMARY_MECHANISMS",
        "terminal_stage": "FEASIBILITY_REJECTED",
        "paths": ("data/evidence/v4_mechanism_feasibility_screen_v1.json",),
        "decision_field": "decision",
        "outcomes_opened": False,
        "successor_policy": "CLOSED_COUNTS_FOR_MULTIPLICITY",
        "reason": (
            "Both V4 mechanisms failed crash-safe source and execution feasibility "
            "before any market value or return was opened."
        ),
    },
    {
        "lineage_id": "07-jam-aggressive-flow-exhaustion",
        "mechanism_families": ("aggressive_sell_flow_exhaustion_reclaim",),
        "terminal_decision": "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED",
        "terminal_stage": "OUTCOME_REJECTED",
        "paths": (
            "data/evidence/jam_successor_development_outcome_result_v1.json",
        ),
        "decision_field": "decision",
        "outcomes_opened": True,
        "successor_policy": "RETIRED_NO_RESCUE",
        "reason": (
            "The preregistered aggregate-flow exhaustion event failed fee-net "
            "development economics and all temporal robustness gates."
        ),
    },
    {
        "lineage_id": "08-periodic-perpetual-flow",
        "mechanism_families": ("periodic_perpetual_order_flow_spot_continuation",),
        "terminal_decision": "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED",
        "terminal_stage": "SOURCE_REJECTED",
        "paths": (
            "data/evidence/q1_periodic_flow_successor_acquisition_result_v7.json",
        ),
        "decision_field": "decision",
        "outcomes_opened": False,
        "successor_policy": "CLOSED_COUNTS_FOR_MULTIPLICITY",
        "reason": (
            "Q1 classified every source month but failed the frozen paired-month, "
            "per-year, and quarter sufficiency gates before measurement."
        ),
    },
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_json(path: str) -> dict:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def validate_parent_ledger() -> None:
    path = PROJECT_ROOT / "data/evidence/strategy_contamination_ledger_v2.json"
    ledger = StrategyContaminationLedger.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_contamination_ledger(ledger) or len(ledger.records) != 7:
        raise ValueError("The frozen parent contamination ledger is invalid")


def build_ledger(*, frozen_at: datetime) -> S1SuccessorLineageLedger:
    validate_parent_ledger()
    records: list[S1LineageRecord] = []
    for definition in LINEAGE_DEFINITIONS:
        decision_field = definition.get("decision_field")
        if decision_field:
            decision_path = str(
                definition.get("decision_path") or definition["paths"][0]
            )
            observed = load_json(decision_path).get(str(decision_field))
            if observed != definition["terminal_decision"]:
                raise ValueError(
                    f"S1 terminal decision changed for {definition['lineage_id']}"
                )
        bindings = tuple(
            S1SourceBinding(
                path=path,
                file_sha256=file_sha256(PROJECT_ROOT / path),
            )
            for path in sorted(definition["paths"])
        )
        records.append(
            S1LineageRecord(
                lineage_id=definition["lineage_id"],
                mechanism_families=tuple(sorted(definition["mechanism_families"])),
                terminal_decision=definition["terminal_decision"],
                terminal_stage=definition["terminal_stage"],
                source_bindings=bindings,
                outcomes_opened=definition["outcomes_opened"],
                successor_policy=definition["successor_policy"],
                reason=definition["reason"],
            )
        )
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "records": tuple(records),
    }
    provisional = S1SuccessorLineageLedger.model_construct(
        **payload,
        ledger_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["ledger_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"ledger_evidence_hash"})
    )
    return S1SuccessorLineageLedger.model_validate(complete)


def write_atomic(path: Path, ledger: S1SuccessorLineageLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 lineage transaction exists: {temporary}")
    serialized = ledger.model_dump_json(indent=2) + "\n"
    if S1SuccessorLineageLedger.model_validate_json(serialized) != ledger:
        raise ValueError("S1 lineage ledger did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check the S1 lineage ledger.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1SuccessorLineageLedger.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_ledger(frozen_at=stored.frozen_at)
        if stored != expected or not audit_s1_lineage(stored):
            raise SystemExit("Stored S1 lineage ledger differs from reconstruction")
        print(f"PASS {stored.ledger_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S1 lineage ledger: {args.output}")
    ledger = build_ledger(frozen_at=datetime.now(UTC))
    write_atomic(args.output, ledger)
    print(
        f"FROZEN {args.output} {ledger.ledger_evidence_hash} "
        "market_values=0 returns=0 candidates=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
