from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2_FOUNDATION_SCENARIO_IDS,
    V2DerivativesFoundationProtocol,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_DERIVATIVES_FOUNDATION_RESULT_SCHEMA_VERSION = (
    "aurex-v2-synthetic-derivatives-foundation-result-v1"
)
V2_FOUNDATION_PASS_DECISION = "PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER"


class V2DerivativesScenarioResult(BaseModel):
    scenario_id: str
    passed: Literal[True] = True
    assertions: dict[str, bool]
    final_reconciliation_status: Literal["MATCHED"] = "MATCHED"
    final_state: Literal[
        "FLAT",
        "OPENING",
        "HEDGED",
        "CLOSING",
        "ROLLBACK",
        "LIQUIDATED",
        "KILLED",
    ]
    kill_switch_enabled: bool
    final_snapshot: dict[str, str]
    ledger_event_count: int = Field(gt=0)
    ledger_head_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("ledger_head_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_scenario(self) -> V2DerivativesScenarioResult:
        if not self.assertions or not all(self.assertions.values()):
            raise ValueError("V2 synthetic scenario has a failed assertion")
        return self


class V2DerivativesFoundationResult(BaseModel):
    schema_version: Literal[
        "aurex-v2-synthetic-derivatives-foundation-result-v1"
    ] = V2_DERIVATIVES_FOUNDATION_RESULT_SCHEMA_VERSION
    result_id: Literal["v2-synthetic-derivatives-foundation-result-v1"] = (
        "v2-synthetic-derivatives-foundation-result-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    foundation_protocol_evidence_hash: str
    pilot_result_evidence_hash: str
    runner_contract_hash: str
    scenario_results: list[V2DerivativesScenarioResult] = Field(
        min_length=14, max_length=14
    )
    passed_scenario_count: Literal[14] = 14
    failed_scenario_count: Literal[0] = 0
    decision: Literal[
        "PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER"
    ] = V2_FOUNDATION_PASS_DECISION
    pass_creates_strategy_candidate: Literal[False] = False
    authorizes_full_archive_payload_download: Literal[False] = False
    authorizes_real_market_data_import: Literal[False] = False
    authorizes_strategy_return_calculation: Literal[False] = False
    authorizes_mechanism_selection: Literal[False] = False
    creates_strategy_eligibility: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    validation_data_loaded: Literal[False] = False
    holdout_data_loaded: Literal[False] = False
    forward_data_loaded: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=5)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "foundation_protocol_evidence_hash",
        "pilot_result_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("strategy_outcome_fields_inspected", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V2DerivativesFoundationResult:
        scenario_ids = [result.scenario_id for result in self.scenario_results]
        if scenario_ids != V2_FOUNDATION_SCENARIO_IDS:
            raise ValueError("V2 foundation result scenario matrix changed")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("V2 foundation result cannot inspect strategy outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V2 foundation result hash does not match")
        return self


def build_v2_derivatives_foundation_result(
    *,
    generated_at: datetime,
    protocol: V2DerivativesFoundationProtocol,
    runner_contract_hash: str,
    scenario_results: list[V2DerivativesScenarioResult],
    limitations: list[str],
) -> V2DerivativesFoundationResult:
    canonical_results = sorted(
        scenario_results,
        key=lambda item: item.scenario_id,
    )
    if len(canonical_results) != len(protocol.scenarios):
        raise ValueError("V2 foundation scenario result count changed")
    for scenario, result in zip(
        protocol.scenarios,
        canonical_results,
        strict=True,
    ):
        if scenario.scenario_id != result.scenario_id:
            raise ValueError("V2 foundation scenario lineage changed")
        if set(scenario.required_assertions) != set(result.assertions):
            raise ValueError("V2 foundation scenario assertions changed")
        if not all(result.assertions.values()):
            raise ValueError("V2 foundation scenario failed")
    payload = {
        "schema_version": V2_DERIVATIVES_FOUNDATION_RESULT_SCHEMA_VERSION,
        "result_id": "v2-synthetic-derivatives-foundation-result-v1",
        "result_version": "1.0.0",
        "generated_at": normalize_timestamp(generated_at),
        "status": "COMPLETE",
        "foundation_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "pilot_result_evidence_hash": protocol.pilot_result_evidence_hash,
        "runner_contract_hash": normalize_sha256(runner_contract_hash),
        "scenario_results": canonical_results,
        "passed_scenario_count": 14,
        "failed_scenario_count": 0,
        "decision": V2_FOUNDATION_PASS_DECISION,
        "pass_creates_strategy_candidate": False,
        "authorizes_full_archive_payload_download": False,
        "authorizes_real_market_data_import": False,
        "authorizes_strategy_return_calculation": False,
        "authorizes_mechanism_selection": False,
        "creates_strategy_eligibility": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "validation_data_loaded": False,
        "holdout_data_loaded": False,
        "forward_data_loaded": False,
        "strategy_outcome_fields_inspected": [],
        "limitations": sorted(set(limitations)),
    }
    return V2DerivativesFoundationResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_derivatives_foundation_result(
    *,
    result: V2DerivativesFoundationResult,
    protocol: V2DerivativesFoundationProtocol,
    current_runner_contract_hash: str,
) -> dict[str, object]:
    reasons: list[str] = []
    if result.foundation_protocol_evidence_hash != protocol.protocol_evidence_hash:
        reasons.append("foundation protocol binding changed")
    if result.pilot_result_evidence_hash != protocol.pilot_result_evidence_hash:
        reasons.append("pilot-result binding changed")
    if result.runner_contract_hash != normalize_sha256(
        current_runner_contract_hash
    ):
        reasons.append("foundation runner contract changed")
    try:
        rebuilt = build_v2_derivatives_foundation_result(
            generated_at=result.generated_at,
            protocol=protocol,
            runner_contract_hash=result.runner_contract_hash,
            scenario_results=result.scenario_results,
            limitations=result.limitations,
        )
    except ValueError as exc:
        reasons.append(str(exc))
    else:
        if rebuilt != result:
            reasons.append("foundation result is not reproducible")
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "result_evidence_hash": result.result_evidence_hash,
        "passed_scenario_count": result.passed_scenario_count,
        "decision": result.decision,
    }
