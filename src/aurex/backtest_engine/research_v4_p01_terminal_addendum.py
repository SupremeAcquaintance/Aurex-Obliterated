from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v4_p01_feasibility_contract import (
    V4P01_REQUIRED_GATE_IDS,
)
from aurex.backtest_engine.research_v4_p01_feasibility_runner import (
    V4P01ExecutionGateResult,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class V4P01TerminalDefectAssessment(BaseModel):
    defect_id: str = Field(pattern=r"^[A-Z0-9_]{8,100}$")
    defect_class: Literal[
        "IDENTITY_NORMALIZATION_DEFECT",
        "GATE_STATUS_REASON_INCONSISTENCY",
    ]
    original_effect: str = Field(min_length=40, max_length=1200)
    corrected_interpretation: str = Field(min_length=40, max_length=1200)
    corrected_decision_changes: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V4P01TerminalAuditAddendum(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-terminal-audit-addendum-v1"
    ] = "aurex-v4-p01-terminal-audit-addendum-v1"
    addendum_id: Literal["v4-p01-terminal-audit-addendum-v1"] = (
        "v4-p01-terminal-audit-addendum-v1"
    )
    audited_at: datetime
    original_contract_evidence_hash: str
    original_terminal_reject_evidence_hash: str
    continuation_contract_evidence_hash: str
    continuation_terminal_reject_evidence_hash: str
    continuation_runner_contract_hash: str
    corrected_metadata_gate_evidence_hash: str
    payload_observation_hashes: list[str] = Field(min_length=6, max_length=6)
    builder_contract_hash: str
    identity_observations_by_request: dict[str, list[str]]
    defect_assessments: list[V4P01TerminalDefectAssessment] = Field(
        min_length=2,
        max_length=2,
    )
    corrected_execution_gate_results: list[V4P01ExecutionGateResult] = Field(
        min_length=14,
        max_length=14,
    )
    invariant_decision: Literal[
        "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    ] = "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    decisive_rejection_gate_ids: list[str] = Field(min_length=4)
    authorizes_network_requests: Literal[False] = False
    authorizes_retries_or_new_samples: Literal[False] = False
    inspects_market_numeric_values: Literal[False] = False
    calculates_signals_trades_pnl_or_returns: Literal[False] = False
    rewrites_prior_artifacts: Literal[False] = False
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    addendum_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "original_contract_evidence_hash",
        "original_terminal_reject_evidence_hash",
        "continuation_contract_evidence_hash",
        "continuation_terminal_reject_evidence_hash",
        "continuation_runner_contract_hash",
        "corrected_metadata_gate_evidence_hash",
        "payload_observation_hashes",
        "builder_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(
        cls,
        value: str | list[str],
    ) -> str | list[str]:
        if isinstance(value, list):
            return [normalize_sha256(item) for item in value]
        return normalize_sha256(value)

    @field_validator("identity_observations_by_request")
    @classmethod
    def normalize_identity_map(
        cls,
        value: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        return {
            key: sorted({item.strip() for item in identities if item.strip()})
            for key, identities in sorted(value.items())
        }

    @field_validator("decisive_rejection_gate_ids", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_addendum(self) -> V4P01TerminalAuditAddendum:
        if [item.gate_id for item in self.corrected_execution_gate_results] != (
            V4P01_REQUIRED_GATE_IDS
        ):
            raise ValueError("V4P01 addendum gate order changed")
        statuses = {
            item.gate_id: item.status
            for item in self.corrected_execution_gate_results
        }
        if any(
            statuses.get(gate_id) != "FAIL"
            for gate_id in self.decisive_rejection_gate_ids
        ):
            raise ValueError("V4P01 decisive rejection gate is not failed")
        if statuses["COMMON_ETH_BTC_PRODUCT_IDENTITY"] != "PASS":
            raise ValueError("V4P01 corrected common-product gate must pass")
        if statuses["RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES"] != "FAIL":
            raise ValueError("V4P01 corrected raw-schema gate must still fail")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected_hash:
            raise ValueError("V4P01 addendum hash does not match")
        return self


def build_v4_p01_terminal_audit_addendum(
    **values,
) -> V4P01TerminalAuditAddendum:
    payload = {
        "schema_version": "aurex-v4-p01-terminal-audit-addendum-v1",
        "addendum_id": "v4-p01-terminal-audit-addendum-v1",
        "invariant_decision": "REJECT_V4P01_BEFORE_PRIMARY_SELECTION",
        "authorizes_network_requests": False,
        "authorizes_retries_or_new_samples": False,
        "inspects_market_numeric_values": False,
        "calculates_signals_trades_pnl_or_returns": False,
        "rewrites_prior_artifacts": False,
        "selects_primary": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["audited_at"] = normalize_timestamp(payload["audited_at"])
    payload["identity_observations_by_request"] = {
        key: sorted(set(identities))
        for key, identities in sorted(
            payload["identity_observations_by_request"].items()
        )
    }
    for field_name in ("decisive_rejection_gate_ids", "limitations"):
        payload[field_name] = sorted(set(payload[field_name]))
    return V4P01TerminalAuditAddendum(
        **payload,
        addendum_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_p01_terminal_audit_addendum(
    addendum: V4P01TerminalAuditAddendum,
) -> bool:
    return addendum.addendum_evidence_hash == universe_evidence_hash(
        addendum.model_dump(exclude={"addendum_evidence_hash"})
    )
