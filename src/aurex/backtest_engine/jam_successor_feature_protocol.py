from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_archive_quality_remediation import (
    JamQualityEvidencePartition,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_FEATURE_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-successor-feature-specification-protocol-v1"
)
JAM_FEATURE_PROTOCOL_ID = "jam-successor-feature-specification-protocol-v1"
JAM_FEATURE_AUTHORIZATION = (
    "USER_AUTHORIZED_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS"
)
JAM_FEATURE_SELECTED_PROPOSAL_ID = (
    "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
)
JAM_FEATURE_QUESTIONS = (
    "AGGRESSOR_SIDE_AND_NOTIONAL_AGGREGATION",
    "BASELINE_NORMALIZATION",
    "CAUSAL_TEMPORAL_PHASES",
    "FLOW_DECAY_REPRESENTATION",
    "FLOW_SHOCK_REPRESENTATION",
    "PARTITION_AND_ANTI_LEAKAGE_CONFORMANCE",
    "PRICE_IMPACT_AND_RECLAIM_REPRESENTATION",
    "QUALITY_STATE_RESET_AND_WARMUP",
)
JAM_FEATURE_PERMITTED_SOURCE_FIELDS = (
    "aggregate_trade_id",
    "first_trade_id",
    "is_best_match",
    "is_buyer_maker",
    "last_trade_id",
    "price",
    "quantity",
    "transact_time",
)


def frozen_feature_partitions() -> list[JamQualityEvidencePartition]:
    return [
        JamQualityEvidencePartition(
            partition_id="JAM_DEVELOPMENT_2019_2020",
            start_month="2019-01",
            end_month="2020-12",
            role="DEVELOPMENT",
        ),
        JamQualityEvidencePartition(
            partition_id="JAM_SEALED_VALIDATION_2021",
            start_month="2021-01",
            end_month="2021-12",
            role="SEALED_VALIDATION",
        ),
        JamQualityEvidencePartition(
            partition_id="JAM_SEALED_HOLDOUT_2022",
            start_month="2022-01",
            end_month="2022-12",
            role="SEALED_HOLDOUT",
        ),
    ]


class JamSuccessorFeatureProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-feature-specification-protocol-v1"
    ] = JAM_FEATURE_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal[
        "jam-successor-feature-specification-protocol-v1"
    ] = JAM_FEATURE_PROTOCOL_ID
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FEATURE_SPECIFICATION"] = (
        "FROZEN_PRE_FEATURE_SPECIFICATION"
    )
    authorization_record: Literal[
        "USER_AUTHORIZED_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS"
    ] = JAM_FEATURE_AUTHORIZATION
    parent_charter_path: Literal[
        "data/evidence/jam_successor_hypothesis_charter_v1.json"
    ] = "data/evidence/jam_successor_hypothesis_charter_v1.json"
    parent_charter_file_sha256: str
    parent_charter_evidence_hash: str
    quality_protocol_path: Literal[
        "data/evidence/jam_archive_quality_remediation_protocol_v1.json"
    ] = "data/evidence/jam_archive_quality_remediation_protocol_v1.json"
    quality_protocol_file_sha256: str
    quality_protocol_evidence_hash: str
    quality_result_path: Literal[
        "data/evidence/jam_archive_quality_remediation_result_v1.json"
    ] = "data/evidence/jam_archive_quality_remediation_result_v1.json"
    quality_result_file_sha256: str
    quality_result_evidence_hash: str
    quality_audit_path: Literal[
        "data/evidence/jam_archive_quality_remediation_audit_v1.json"
    ] = "data/evidence/jam_archive_quality_remediation_audit_v1.json"
    quality_audit_file_sha256: str
    quality_audit_evidence_hash: str
    contamination_ledger_path: Literal[
        "data/evidence/strategy_contamination_ledger_v2.json"
    ] = "data/evidence/strategy_contamination_ledger_v2.json"
    contamination_ledger_file_sha256: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    selected_proposal_id: Literal[
        "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
    ] = JAM_FEATURE_SELECTED_PROPOSAL_ID
    primary_source: Literal[
        "BINANCE_SPOT_MONTHLY_AGGTRADES"
    ] = "BINANCE_SPOT_MONTHLY_AGGTRADES"
    secondary_source: Literal[
        "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY"
    ] = "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY"
    feature_questions: list[str] = Field(min_length=8, max_length=8)
    permitted_source_fields: list[str] = Field(min_length=8, max_length=8)
    evidence_partitions: list[JamQualityEvidencePartition] = Field(
        min_length=3,
        max_length=3,
    )
    quarantine_manifest_hash: str
    maximum_feature_count: Literal[24] = 24
    maximum_lookback_minutes: Literal[240] = 240
    maximum_temporal_phase_count: Literal[4] = 4
    maximum_synthetic_fixture_rows: Literal[1000] = 1_000
    raw_market_payload_access_permitted: Literal[False] = False
    source_schema_access_permitted: Literal[True] = True
    synthetic_fixture_access_permitted: Literal[True] = True
    causal_feature_definition_permitted: Literal[True] = True
    feature_lookback_definition_permitted: Literal[True] = True
    normalization_constant_definition_permitted: Literal[True] = True
    decision_threshold_definition_permitted: Literal[False] = False
    directional_label_definition_permitted: Literal[False] = False
    future_return_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    outcome_access_permitted: Literal[False] = False
    strategy_creation_permitted: Literal[False] = False
    signal_creation_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_eligibility_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    expected_deliverable: Literal[
        "FROZEN_CAUSAL_FEATURE_SPECIFICATION_AND_SYNTHETIC_CONFORMANCE_NO_RETURNS"
    ] = "FROZEN_CAUSAL_FEATURE_SPECIFICATION_AND_SYNTHETIC_CONFORMANCE_NO_RETURNS"
    limitations: list[str] = Field(min_length=14)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_charter_file_sha256",
        "parent_charter_evidence_hash",
        "quality_protocol_file_sha256",
        "quality_protocol_evidence_hash",
        "quality_result_file_sha256",
        "quality_result_evidence_hash",
        "quality_audit_file_sha256",
        "quality_audit_evidence_hash",
        "contamination_ledger_file_sha256",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "quarantine_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "feature_questions",
        "permitted_source_fields",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> JamSuccessorFeatureProtocol:
        if (
            self.feature_questions != list(JAM_FEATURE_QUESTIONS)
            or self.permitted_source_fields
            != list(JAM_FEATURE_PERMITTED_SOURCE_FIELDS)
            or self.evidence_partitions != frozen_feature_partitions()
        ):
            raise ValueError("Jam feature specification boundary changed")
        if any(
            (
                self.raw_market_payload_access_permitted,
                self.decision_threshold_definition_permitted,
                self.directional_label_definition_permitted,
                self.future_return_definition_permitted,
                self.return_calculation_permitted,
                self.outcome_access_permitted,
                self.strategy_creation_permitted,
                self.signal_creation_permitted,
                self.candidate_creation_permitted,
                self.paper_eligibility_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("Jam feature protocol grants forbidden authority")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam feature protocol hash does not match")
        return self


def build_jam_successor_feature_protocol(
    **values,
) -> JamSuccessorFeatureProtocol:
    payload = {
        "schema_version": JAM_FEATURE_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": JAM_FEATURE_PROTOCOL_ID,
        "status": "FROZEN_PRE_FEATURE_SPECIFICATION",
        "authorization_record": JAM_FEATURE_AUTHORIZATION,
        "parent_charter_path": (
            "data/evidence/jam_successor_hypothesis_charter_v1.json"
        ),
        "quality_protocol_path": (
            "data/evidence/jam_archive_quality_remediation_protocol_v1.json"
        ),
        "quality_result_path": (
            "data/evidence/jam_archive_quality_remediation_result_v1.json"
        ),
        "quality_audit_path": (
            "data/evidence/jam_archive_quality_remediation_audit_v1.json"
        ),
        "contamination_ledger_path": (
            "data/evidence/strategy_contamination_ledger_v2.json"
        ),
        "selected_proposal_id": JAM_FEATURE_SELECTED_PROPOSAL_ID,
        "primary_source": "BINANCE_SPOT_MONTHLY_AGGTRADES",
        "secondary_source": "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY",
        "feature_questions": list(JAM_FEATURE_QUESTIONS),
        "permitted_source_fields": list(JAM_FEATURE_PERMITTED_SOURCE_FIELDS),
        "evidence_partitions": frozen_feature_partitions(),
        "maximum_feature_count": 24,
        "maximum_lookback_minutes": 240,
        "maximum_temporal_phase_count": 4,
        "maximum_synthetic_fixture_rows": 1_000,
        "raw_market_payload_access_permitted": False,
        "source_schema_access_permitted": True,
        "synthetic_fixture_access_permitted": True,
        "causal_feature_definition_permitted": True,
        "feature_lookback_definition_permitted": True,
        "normalization_constant_definition_permitted": True,
        "decision_threshold_definition_permitted": False,
        "directional_label_definition_permitted": False,
        "future_return_definition_permitted": False,
        "return_calculation_permitted": False,
        "outcome_access_permitted": False,
        "strategy_creation_permitted": False,
        "signal_creation_permitted": False,
        "candidate_creation_permitted": False,
        "paper_eligibility_permitted": False,
        "testnet_strategy_orders_permitted": False,
        "production_permitted": False,
        "live_permitted": False,
        "expected_deliverable": (
            "FROZEN_CAUSAL_FEATURE_SPECIFICATION_AND_SYNTHETIC_CONFORMANCE_NO_RETURNS"
        ),
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorFeatureProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_feature_protocol(
    protocol: JamSuccessorFeatureProtocol,
) -> bool:
    try:
        JamSuccessorFeatureProtocol.model_validate(protocol.model_dump())
    except ValueError:
        return False
    return True
