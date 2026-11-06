from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

READINESS_PROTOCOL_SCHEMA_VERSION = "aurex-strategy-factory-readiness-protocol-v1"
READINESS_RESULT_SCHEMA_VERSION = "aurex-strategy-factory-readiness-result-v1"
READINESS_AUDIT_SCHEMA_VERSION = "aurex-strategy-factory-readiness-audit-v1"

READINESS_PASS_DECISION = (
    "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY"
)
READINESS_FAIL_DECISION = "BLOCK_AUREX_STRATEGY_FACTORY_READINESS_GAPS_REMAIN"
READINESS_PASS_NEXT_ACTION = "DESIGN_ONE_NEW_UNRELATED_MECHANISM_CHARTER_ONLY"
READINESS_FAIL_NEXT_ACTION = "CLOSE_AUREX_STRATEGY_FACTORY_READINESS_BLOCKERS"

READINESS_GATE_IDS = (
    "CANONICAL_PROGRAM_TRUTH",
    "IMMUTABLE_EVIDENCE_INTEGRITY",
    "MARKET_DATA_LINEAGE_AND_QUALITY",
    "CONTAMINATION_AND_PARTITION_ISOLATION",
    "PREREGISTRATION_BEFORE_OUTCOMES",
    "DETERMINISTIC_REPLAY_AND_RECONCILIATION",
    "UNIVERSAL_COST_STRESS_AND_INFERENCE",
    "CANDIDATE_LIFECYCLE_AND_RETIREMENT",
    "FAIL_CLOSED_PAPER_PROMOTION",
    "AUTHENTICATED_SIGNAL_DELIVERY",
    "EVIDENCE_GRADE_PAPER_EXECUTION",
    "RISK_LIMITS_AND_KILL_SWITCH",
    "EXCHANGE_SANDBOX_QUALIFICATION",
    "LIVE_EXECUTION_ISOLATION",
    "OPERATOR_READINESS_VISIBILITY",
)


class StrategyFactoryReadinessGateSpec(BaseModel):
    gate_id: str = Field(pattern="^[A-Z0-9_]+$")
    domain: str = Field(min_length=1, max_length=80)
    requirement: str = Field(min_length=1)
    required_for_research: bool
    required_for_paper: bool
    required_for_sandbox_strategy_use: bool
    required_for_live: bool

    model_config = ConfigDict(extra="forbid", frozen=True)


class StrategyFactoryReadinessProtocol(BaseModel):
    schema_version: Literal[
        "aurex-strategy-factory-readiness-protocol-v1"
    ] = READINESS_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["aurex-strategy-factory-readiness-v1"] = (
        "aurex-strategy-factory-readiness-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_READINESS_SCORING"] = (
        "FROZEN_PRE_READINESS_SCORING"
    )
    authorization_record: str
    purpose: str
    source_scope: list[str]
    gate_specs: list[StrategyFactoryReadinessGateSpec]
    scoring_rule: Literal[
        "RESEARCH_READY_ONLY_WHEN_EVERY_RESEARCH_REQUIRED_GATE_PASSES"
    ] = "RESEARCH_READY_ONLY_WHEN_EVERY_RESEARCH_REQUIRED_GATE_PASSES"
    partial_is_pass: Literal[False] = False
    code_presence_is_operational_proof: Literal[False] = False
    no_strategy_design_permitted: Literal[True] = True
    no_market_outcome_access_permitted: Literal[True] = True
    no_paper_campaign_permitted: Literal[True] = True
    no_testnet_strategy_order_permitted: Literal[True] = True
    no_production_or_live_permitted: Literal[True] = True
    real_market_values_opened: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    limitations: list[str]
    builder_contract_hash: str
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "protocol_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> StrategyFactoryReadinessProtocol:
        if tuple(item.gate_id for item in self.gate_specs) != READINESS_GATE_IDS:
            raise ValueError("Strategy-factory readiness gate matrix changed")
        if len({item.gate_id for item in self.gate_specs}) != len(self.gate_specs):
            raise ValueError("Strategy-factory readiness gates must be unique")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Strategy-factory readiness protocol hash changed")
        return self


class StrategyFactorySourceEvidence(BaseModel):
    path: str
    file_sha256: str
    byte_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class StrategyFactoryReadinessGateResult(BaseModel):
    gate_id: str
    status: Literal["PASS", "PARTIAL", "FAIL"]
    summary: str
    checks: list[str]
    blockers: list[str]
    source_evidence: list[StrategyFactorySourceEvidence]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_result(self) -> StrategyFactoryReadinessGateResult:
        if self.status == "PASS" and self.blockers:
            raise ValueError("Passing readiness gate cannot contain blockers")
        if self.status != "PASS" and not self.blockers:
            raise ValueError("Non-passing readiness gate requires blockers")
        if not self.checks or not self.source_evidence:
            raise ValueError("Readiness gate requires checks and source evidence")
        paths = [item.path for item in self.source_evidence]
        if paths != sorted(set(paths)):
            raise ValueError("Readiness source evidence must be sorted and unique")
        return self


class StrategyFactoryReadinessResult(BaseModel):
    schema_version: Literal[
        "aurex-strategy-factory-readiness-result-v1"
    ] = READINESS_RESULT_SCHEMA_VERSION
    result_id: Literal["aurex-strategy-factory-readiness-baseline-v1"] = (
        "aurex-strategy-factory-readiness-baseline-v1"
    )
    evaluated_at: datetime
    protocol_evidence_hash: str
    runner_contract_hash: str
    gate_results: list[StrategyFactoryReadinessGateResult]
    passed_gate_count: int = Field(ge=0)
    partial_gate_count: int = Field(ge=0)
    failed_gate_count: int = Field(ge=0)
    research_required_gate_count: int = Field(ge=0)
    research_blocking_gate_ids: list[str]
    strategy_research_ready: bool
    paper_operation_ready: Literal[False] = False
    sandbox_strategy_use_ready: Literal[False] = False
    production_ready: Literal[False] = False
    live_ready: Literal[False] = False
    decision: Literal[
        "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY",
        "BLOCK_AUREX_STRATEGY_FACTORY_READINESS_GAPS_REMAIN",
    ]
    next_action: Literal[
        "DESIGN_ONE_NEW_UNRELATED_MECHANISM_CHARTER_ONLY",
        "CLOSE_AUREX_STRATEGY_FACTORY_READINESS_BLOCKERS",
    ]
    external_tradingview_proof_present: bool
    qualified_strategy_count: Literal[0] = 0
    real_market_values_opened: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    real_net_profit_usd: Literal["0"] = "0"
    limitations: list[str]
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash", "runner_contract_hash", "result_evidence_hash"
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> StrategyFactoryReadinessResult:
        if tuple(item.gate_id for item in self.gate_results) != READINESS_GATE_IDS:
            raise ValueError("Strategy-factory readiness result gates changed")
        statuses = [item.status for item in self.gate_results]
        if (
            self.passed_gate_count != statuses.count("PASS")
            or self.partial_gate_count != statuses.count("PARTIAL")
            or self.failed_gate_count != statuses.count("FAIL")
        ):
            raise ValueError("Strategy-factory readiness gate counts changed")
        expected_ready = not self.research_blocking_gate_ids
        if self.strategy_research_ready != expected_ready:
            raise ValueError("Strategy-factory research readiness changed")
        expected_decision = (
            READINESS_PASS_DECISION if expected_ready else READINESS_FAIL_DECISION
        )
        expected_next = (
            READINESS_PASS_NEXT_ACTION if expected_ready else READINESS_FAIL_NEXT_ACTION
        )
        if self.decision != expected_decision or self.next_action != expected_next:
            raise ValueError("Strategy-factory readiness decision changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Strategy-factory readiness result hash changed")
        return self


class StrategyFactoryReadinessAudit(BaseModel):
    schema_version: Literal[
        "aurex-strategy-factory-readiness-audit-v1"
    ] = READINESS_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_contract_hash: str
    reconstructed_result_matches: Literal[True] = True
    reconstructed_gate_count: Literal[15] = 15
    strategy_research_ready: bool
    decision: Literal[
        "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY",
        "BLOCK_AUREX_STRATEGY_FACTORY_READINESS_GAPS_REMAIN",
    ]
    real_market_values_opened: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "runner_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> StrategyFactoryReadinessAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Strategy-factory readiness audit hash changed")
        return self


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_readiness_protocol(**values) -> StrategyFactoryReadinessProtocol:
    payload = {
        "schema_version": READINESS_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "aurex-strategy-factory-readiness-v1",
        "status": "FROZEN_PRE_READINESS_SCORING",
        "scoring_rule": (
            "RESEARCH_READY_ONLY_WHEN_EVERY_RESEARCH_REQUIRED_GATE_PASSES"
        ),
        "partial_is_pass": False,
        "code_presence_is_operational_proof": False,
        "no_strategy_design_permitted": True,
        "no_market_outcome_access_permitted": True,
        "no_paper_campaign_permitted": True,
        "no_testnet_strategy_order_permitted": True,
        "no_production_or_live_permitted": True,
        "real_market_values_opened": 0,
        "strategy_candidates_created": 0,
        "strategy_executions": 0,
        "orders_submitted": 0,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return StrategyFactoryReadinessProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_readiness_result(
    *,
    protocol: StrategyFactoryReadinessProtocol,
    **values,
) -> StrategyFactoryReadinessResult:
    gate_results = values["gate_results"]
    specs = {item.gate_id: item for item in protocol.gate_specs}
    blocking = [
        item.gate_id
        for item in gate_results
        if specs[item.gate_id].required_for_research and item.status != "PASS"
    ]
    ready = not blocking
    statuses = [item.status for item in gate_results]
    payload = {
        "schema_version": READINESS_RESULT_SCHEMA_VERSION,
        "result_id": "aurex-strategy-factory-readiness-baseline-v1",
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "passed_gate_count": statuses.count("PASS"),
        "partial_gate_count": statuses.count("PARTIAL"),
        "failed_gate_count": statuses.count("FAIL"),
        "research_required_gate_count": sum(
            item.required_for_research for item in protocol.gate_specs
        ),
        "research_blocking_gate_ids": blocking,
        "strategy_research_ready": ready,
        "paper_operation_ready": False,
        "sandbox_strategy_use_ready": False,
        "production_ready": False,
        "live_ready": False,
        "decision": READINESS_PASS_DECISION if ready else READINESS_FAIL_DECISION,
        "next_action": (
            READINESS_PASS_NEXT_ACTION if ready else READINESS_FAIL_NEXT_ACTION
        ),
        "qualified_strategy_count": 0,
        "real_market_values_opened": 0,
        "strategy_candidates_created": 0,
        "strategy_executions": 0,
        "orders_submitted": 0,
        "real_net_profit_usd": "0",
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return StrategyFactoryReadinessResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_readiness_audit(**values) -> StrategyFactoryReadinessAudit:
    payload = {
        "schema_version": READINESS_AUDIT_SCHEMA_VERSION,
        "reconstructed_result_matches": True,
        "reconstructed_gate_count": len(READINESS_GATE_IDS),
        "real_market_values_opened": 0,
        "strategy_candidates_created": 0,
        "strategy_executions": 0,
        "orders_submitted": 0,
        **values,
    }
    return StrategyFactoryReadinessAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_readiness_protocol(protocol: StrategyFactoryReadinessProtocol) -> bool:
    try:
        StrategyFactoryReadinessProtocol.model_validate(protocol.model_dump())
    except ValueError:
        return False
    return True


def audit_readiness_result(result: StrategyFactoryReadinessResult) -> bool:
    try:
        StrategyFactoryReadinessResult.model_validate(result.model_dump())
    except ValueError:
        return False
    return True


def audit_readiness_audit(audit: StrategyFactoryReadinessAudit) -> bool:
    try:
        StrategyFactoryReadinessAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True


def contamination_artifact_valid(path: Path) -> bool:
    try:
        ledger = StrategyContaminationLedger.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return False
    return audit_contamination_ledger(ledger)
