from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_SUCCESSOR_CHARTER_SCHEMA_VERSION = (
    "aurex-jam-successor-hypothesis-charter-v1"
)
JAM_SUCCESSOR_CHARTER_ID = "jam-successor-hypothesis-charter-v1"
JAM_SELECTED_PROPOSAL_ID = "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
JAM_SUCCESSOR_DECISION = "SELECT_P01_FOR_FUTURE_CAPABILITY_REVIEW_ONLY"
JAM_SUCCESSOR_SOURCE_IDS = (
    "BINANCE-COMMISSION-FAQ",
    "BINANCE-PUBLIC-DATA",
    "BIANCHI-DICKERSON-BABIAK-2022",
    "BTC-LIQUIDITY-RESILIENCY-2026",
    "BTC-MARKET-EFFICIENCY-2026",
)
JAM_SUCCESSOR_PROPOSAL_IDS = (
    JAM_SELECTED_PROPOSAL_ID,
    "J2-P02-CANDLE-PARAMETER-RESCUE",
    "J2-P03-PASSIVE-MAKER-RETEST",
    "J2-P04-LOW-ACTIVITY-CROSS-ASSET-REVERSAL",
)
JAM_SUCCESSOR_FINDINGS_USED = (
    "SAMPLE_TOO_SPARSE_FOR_RELIABILITY",
    "BASE_COSTS_EXCEED_GROSS_PRICE_EDGE",
    "OUT_OF_SAMPLE_EDGE_IS_NEGATIVE",
    "WALK_FORWARD_STABILITY_IS_ABSENT",
)
JAM_SUCCESSOR_FEASIBILITY_GATES = (
    "OFFICIAL_ARCHIVE_METADATA_AND_CHECKSUM_COVERAGE_VERIFIED",
    "AGGTRADE_MILLISECOND_AND_MICROSECOND_TIMESTAMPS_NORMALIZED",
    "AGGRESSOR_SIDE_MAPPING_PROVEN_WITH_SYNTHETIC_AND_ARCHIVE_FIXTURES",
    "AGGTRADE_OHLCV_RECONCILES_TO_OFFICIAL_KLINES",
    "NO_ORDER_BOOK_DEPTH_QUEUE_OR_LIQUIDATION_CLAIM_INFERRED",
    "NO_MAKER_FILL_OR_FEE_DISCOUNT_ASSUMED",
    "FEATURE_AND_THRESHOLD_PROTOCOL_FROZEN_BEFORE_DEVELOPMENT_RETURNS",
    "CONSUMED_AND_FORWARD_PARTITIONS_REMAIN_CLOSED",
)


class JamMechanismSource(BaseModel):
    source_id: str = Field(min_length=1)
    source_type: Literal[
        "OFFICIAL_EXCHANGE_DOCUMENTATION",
        "PEER_REVIEWED_RESEARCH",
    ]
    reference: str = Field(min_length=1)
    bounded_use: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class JamMechanismProposal(BaseModel):
    proposal_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    mechanism_hypothesis: str = Field(min_length=1)
    falsifiable_predictions: tuple[str, ...] = Field(min_length=1)
    required_inputs: tuple[str, ...] = Field(min_length=1)
    exact_pine_compatible: bool
    btcusdt_spot_scope_compatible: bool
    historical_fill_identifiable: bool
    decision: Literal[
        "SELECT_FOR_FUTURE_CAPABILITY_REVIEW_ONLY",
        "REJECT",
        "DEFER",
    ]
    reason: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class JamEvidencePartition(BaseModel):
    partition_id: str = Field(min_length=1)
    start: datetime
    end: datetime | None
    source_types: tuple[str, ...] = Field(min_length=1)
    state: Literal[
        "CONSUMED",
        "EXPLORATORY_CONTAMINATED",
        "PROVISIONAL_UNOPENED_UNVERIFIED",
        "LOCKED_FORWARD",
    ]
    outcome_access_permitted: bool = False
    purpose: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("start", "end")
    @classmethod
    def normalize_partition_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_partition(self) -> JamEvidencePartition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("Jam evidence partition end must follow its start")
        if self.state == "LOCKED_FORWARD" and self.end is not None:
            raise ValueError("Jam forward partition must be open-ended")
        if self.outcome_access_permitted:
            raise ValueError("Jam successor charter cannot open outcome access")
        return self


class JamSuccessorHypothesisCharter(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-hypothesis-charter-v1"
    ] = JAM_SUCCESSOR_CHARTER_SCHEMA_VERSION
    charter_id: Literal[
        "jam-successor-hypothesis-charter-v1"
    ] = JAM_SUCCESSOR_CHARTER_ID
    frozen_at: datetime
    status: Literal[
        "FROZEN_DESIGN_ONLY_NOT_AUTHORIZED_TO_RUN"
    ] = "FROZEN_DESIGN_ONLY_NOT_AUTHORIZED_TO_RUN"
    research_boundary: Literal[
        "NO_NEW_MARKET_DATA_NO_NEW_RETURNS_NO_PARAMETER_DEFINITION"
    ] = "NO_NEW_MARKET_DATA_NO_NEW_RETURNS_NO_PARAMETER_DEFINITION"
    parent_failure_analysis_path: Literal[
        "data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json"
    ] = "data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json"
    parent_failure_analysis_evidence_hash: str
    contamination_ledger_path: Literal[
        "data/evidence/strategy_contamination_ledger_v2.json"
    ] = "data/evidence/strategy_contamination_ledger_v2.json"
    contamination_ledger_evidence_hash: str
    sandbox_profile_path: Literal[
        "data/evidence/binance_spot_testnet_sandbox_profile_v1.json"
    ] = "data/evidence/binance_spot_testnet_sandbox_profile_v1.json"
    sandbox_profile_evidence_hash: str
    phase2_source_file_sha256: str
    phase2_audit_file_sha256: str
    phase2_audit_evidence_hash: str
    parent_findings_used: tuple[str, ...]
    new_outcome_fields_inspected: tuple[str, ...] = ()
    operator_scope: dict[str, object]
    evidence_sources: tuple[JamMechanismSource, ...]
    proposals: tuple[JamMechanismProposal, ...]
    selected_proposal_id: Literal[
        "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
    ] = JAM_SELECTED_PROPOSAL_ID
    selection_decision: Literal[
        "SELECT_P01_FOR_FUTURE_CAPABILITY_REVIEW_ONLY"
    ] = JAM_SUCCESSOR_DECISION
    evidence_partitions: tuple[JamEvidencePartition, ...]
    feasibility_gates: tuple[str, ...]
    next_required_authorization: Literal[
        "AUTHORIZE_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
    ] = "AUTHORIZE_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
    exact_pine_signal_supported: bool = False
    proposed_signal_authority: Literal[
        "AUREX_BACKEND_ONLY_IF_A_LATER_PROTOCOL_QUALIFIES"
    ] = "AUREX_BACKEND_ONLY_IF_A_LATER_PROTOCOL_QUALIFIES"
    pine_role: Literal[
        "OPTIONAL_VISUALIZATION_ONLY_NOT_SIGNAL_SOURCE"
    ] = "OPTIONAL_VISUALIZATION_ONLY_NOT_SIGNAL_SOURCE"
    creates_strategy_version: bool = False
    authorizes_market_data_import: bool = False
    authorizes_parameter_definition: bool = False
    authorizes_return_testing: bool = False
    authorizes_candidate: bool = False
    authorizes_forward_paper: bool = False
    authorizes_testnet_strategy_orders: bool = False
    authorizes_production: bool = False
    authorizes_live: bool = False
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_failure_analysis_evidence_hash",
        "contamination_ledger_evidence_hash",
        "sandbox_profile_evidence_hash",
        "phase2_source_file_sha256",
        "phase2_audit_file_sha256",
        "phase2_audit_evidence_hash",
        "charter_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_charter(self) -> JamSuccessorHypothesisCharter:
        if self.parent_findings_used != JAM_SUCCESSOR_FINDINGS_USED:
            raise ValueError("Jam successor parent findings are fixed")
        if self.new_outcome_fields_inspected:
            raise ValueError("Jam successor charter cannot inspect new outcomes")
        if tuple(source.source_id for source in self.evidence_sources) != (
            JAM_SUCCESSOR_SOURCE_IDS
        ):
            raise ValueError("Jam successor evidence sources are fixed")
        if tuple(proposal.proposal_id for proposal in self.proposals) != (
            JAM_SUCCESSOR_PROPOSAL_IDS
        ):
            raise ValueError("Jam successor proposal register is fixed")
        selected = [
            proposal
            for proposal in self.proposals
            if proposal.decision == "SELECT_FOR_FUTURE_CAPABILITY_REVIEW_ONLY"
        ]
        if len(selected) != 1 or selected[0].proposal_id != self.selected_proposal_id:
            raise ValueError("Jam successor charter requires one selected proposal")
        if selected[0].exact_pine_compatible:
            raise ValueError("The selected flow proposal cannot claim Pine parity")
        if not (
            selected[0].btcusdt_spot_scope_compatible
            and selected[0].historical_fill_identifiable
        ):
            raise ValueError("Selected Jam proposal must fit the executable scope")
        if self.feasibility_gates != JAM_SUCCESSOR_FEASIBILITY_GATES:
            raise ValueError("Jam successor feasibility gates are fixed")
        if tuple(partition.partition_id for partition in self.evidence_partitions) != (
            "JAM-V1-CONSUMED-2023-2025",
            "JAM-V1-EXPLORATORY-2026",
            "JAM-PROVISIONAL-HISTORICAL-POOL-2019-2022",
            "JAM-LOCKED-FORWARD-2026-08-01",
        ):
            raise ValueError("Jam successor evidence map is fixed")
        if any(
            (
                self.creates_strategy_version,
                self.authorizes_market_data_import,
                self.authorizes_parameter_definition,
                self.authorizes_return_testing,
                self.authorizes_candidate,
                self.authorizes_forward_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("Jam successor design charter cannot grant authority")
        if self.exact_pine_signal_supported:
            raise ValueError("Aggregate-trade flow is not exactly available in Pine")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected_hash:
            raise ValueError("Jam successor charter hash does not match its evidence")
        return self


def audit_jam_successor_hypothesis_charter(
    charter: JamSuccessorHypothesisCharter,
) -> bool:
    expected_hash = universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )
    return charter.charter_evidence_hash == expected_hash


def utc_datetime(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)
