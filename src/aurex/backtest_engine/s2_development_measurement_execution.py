from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s2_bigquery_payload import S2DevelopmentWeeklyPayload
from aurex.backtest_engine.s2_development_measurement_protocol import S2_MEASUREMENT_GATES
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_MEASUREMENT_RUN = "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUN_ONCE"
S2_MEASUREMENT_PASS = "PASS_S2_DEVELOPMENT_MEASUREMENT_CONSTRUCTION"
S2_MEASUREMENT_RESULT_AUDIT_NEXT = "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT_ONLY"
S2_MEASUREMENT_PREREG_NEXT = "AUTHORIZE_S2_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
PPM_SCALE = Decimal(1_000_000)
PPM_QUANTUM = Decimal(1)
DECIMAL_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


def growth_ppm(current: int, prior: int) -> int:
    if current < 0 or prior <= 0:
        raise ValueError("S2 measurement growth requires nonnegative current and positive prior")
    with localcontext(DECIMAL_CONTEXT):
        value = (Decimal(current - prior) * PPM_SCALE) / Decimal(prior)
        return int(value.quantize(PPM_QUANTUM, rounding=ROUND_HALF_EVEN))


def settlement_demand_agreement(
    transaction_growth_ppm: int,
    fee_growth_ppm: int,
) -> Literal["BOTH_BROADENING", "BOTH_CONTRACTING", "FLAT_OR_MIXED"]:
    if transaction_growth_ppm > 0 and fee_growth_ppm > 0:
        return "BOTH_BROADENING"
    if transaction_growth_ppm < 0 and fee_growth_ppm < 0:
        return "BOTH_CONTRACTING"
    return "FLAT_OR_MIXED"


class S2DevelopmentMeasurementRow(BaseModel):
    sequence: int = Field(ge=8, le=280)
    week_start: date
    decision_cutoff_at: date
    earliest_execution_at: date
    source_payload_evidence_hash: str
    confirmed_tx_current_4w: int = Field(gt=0)
    confirmed_tx_prior_4w: int = Field(gt=0)
    confirmed_fee_sats_current_4w: int = Field(ge=0)
    confirmed_fee_sats_prior_4w: int = Field(gt=0)
    confirmed_tx_growth_ppm: int
    confirmed_fee_growth_ppm: int
    settlement_demand_agreement: Literal[
        "BOTH_BROADENING",
        "BOTH_CONTRACTING",
        "FLAT_OR_MIXED",
    ]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("source_payload_evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_row(self) -> S2DevelopmentMeasurementRow:
        if (
            self.week_start.weekday() != 5
            or self.decision_cutoff_at != self.week_start + timedelta(days=7)
            or self.earliest_execution_at != self.week_start + timedelta(days=9)
            or self.confirmed_tx_growth_ppm
            != growth_ppm(self.confirmed_tx_current_4w, self.confirmed_tx_prior_4w)
            or self.confirmed_fee_growth_ppm
            != growth_ppm(
                self.confirmed_fee_sats_current_4w,
                self.confirmed_fee_sats_prior_4w,
            )
            or self.settlement_demand_agreement
            != settlement_demand_agreement(
                self.confirmed_tx_growth_ppm,
                self.confirmed_fee_growth_ppm,
            )
        ):
            raise ValueError("S2 development measurement row changed")
        return self


class S2MeasurementGate(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    reason: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S2DevelopmentMeasurementExecutionAddendum(BaseModel):
    schema_version: Literal["aurex-s2-development-measurement-execution-addendum-v1"] = (
        "aurex-s2-development-measurement-execution-addendum-v1"
    )
    addendum_id: Literal["s2-development-measurement-execution-addendum-v1"] = (
        "s2-development-measurement-execution-addendum-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    payload_result_evidence_hash: str
    payload_result_audit_evidence_hash: str
    payload_file_sha256: str
    payload_evidence_hash: str
    runner_contract_hash: str
    output_path: Literal["data/evidence/s2_development_measurements_v1.jsonl"] = (
        "data/evidence/s2_development_measurements_v1.jsonl"
    )
    result_path: Literal["data/evidence/s2_development_measurement_result_v1.json"] = (
        "data/evidence/s2_development_measurement_result_v1.json"
    )
    output_was_absent: Literal[True] = True
    result_was_absent: Literal[True] = True
    synthetic_test_ids: tuple[str, ...] = Field(min_length=8)
    authorizes_single_measurement_run: Literal[True] = True
    authorizes_payload_value_read: Literal[True] = True
    authorizes_measurement_calculation: Literal[True] = True
    authorizes_strategy_parameter_definition: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_strategy_candidate: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal["AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUN_ONCE"] = (
        S2_MEASUREMENT_RUN
    )
    addendum_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "payload_result_evidence_hash",
        "payload_result_audit_evidence_hash",
        "payload_file_sha256",
        "payload_evidence_hash",
        "runner_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_addendum(self) -> S2DevelopmentMeasurementExecutionAddendum:
        if self.synthetic_test_ids != tuple(sorted(set(self.synthetic_test_ids))):
            raise ValueError("S2 measurement synthetic test IDs changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected:
            raise ValueError("S2 measurement execution addendum hash changed")
        return self


class S2DevelopmentMeasurementExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s2-development-measurement-execution-audit-v1"] = (
        "aurex-s2-development-measurement-execution-audit-v1"
    )
    audit_id: Literal["s2-development-measurement-execution-audit-v1"] = (
        "s2-development-measurement-execution-audit-v1"
    )
    audited_at: datetime
    addendum_file_sha256: str
    addendum_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    payload_value_rows_parsed: Literal[0] = 0
    measurement_rows_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S2_DEVELOPMENT_MEASUREMENT_EXECUTION_AUDIT"] = (
        "PASS_S2_DEVELOPMENT_MEASUREMENT_EXECUTION_AUDIT"
    )
    next_authorization: Literal["AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUN_ONCE"] = (
        S2_MEASUREMENT_RUN
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "addendum_file_sha256",
        "addendum_evidence_hash",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2DevelopmentMeasurementExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 measurement execution audit hash changed")
        return self


class S2DevelopmentMeasurementResult(BaseModel):
    schema_version: Literal["aurex-s2-development-measurement-result-v1"] = (
        "aurex-s2-development-measurement-result-v1"
    )
    result_id: Literal["s2-development-measurement-result-v1"] = (
        "s2-development-measurement-result-v1"
    )
    completed_at: datetime
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_addendum_file_sha256: str
    execution_addendum_evidence_hash: str
    execution_audit_evidence_hash: str
    runner_contract_hash: str
    payload_file_sha256: str
    payload_evidence_hash: str
    measurement_dataset_path: Literal["data/evidence/s2_development_measurements_v1.jsonl"] = (
        "data/evidence/s2_development_measurements_v1.jsonl"
    )
    measurement_dataset_file_sha256: str
    measurement_dataset_bytes: int = Field(gt=0)
    input_row_count: Literal[280] = 280
    measurement_row_count: Literal[273] = 273
    first_measurement_sequence: Literal[8] = 8
    last_measurement_sequence: Literal[280] = 280
    measurement_count: Literal[7] = 7
    row_evidence_hashes: tuple[str, ...] = Field(min_length=273, max_length=273)
    gates: tuple[S2MeasurementGate, ...] = Field(min_length=13, max_length=13)
    market_values_read: Literal[0] = 0
    strategy_parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    signals_generated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S2_DEVELOPMENT_MEASUREMENT_CONSTRUCTION"] = S2_MEASUREMENT_PASS
    next_authorization: Literal["AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT_ONLY"] = (
        S2_MEASUREMENT_RESULT_AUDIT_NEXT
    )
    authorizes_strategy_parameter_definition: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_strategy_candidate: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("completed_at")
    @classmethod
    def normalize_completed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "execution_addendum_file_sha256",
        "execution_addendum_evidence_hash",
        "execution_audit_evidence_hash",
        "runner_contract_hash",
        "payload_file_sha256",
        "payload_evidence_hash",
        "measurement_dataset_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("row_evidence_hashes")
    @classmethod
    def normalize_row_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_result(self) -> S2DevelopmentMeasurementResult:
        if tuple(gate.gate_id for gate in self.gates) != S2_MEASUREMENT_GATES:
            raise ValueError("S2 measurement result gates changed")
        if any(gate.status != "PASS" for gate in self.gates):
            raise ValueError("S2 measurement result contains a failed gate")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S2 measurement result hash changed")
        return self


class S2DevelopmentMeasurementResultAudit(BaseModel):
    schema_version: Literal["aurex-s2-development-measurement-result-audit-v1"] = (
        "aurex-s2-development-measurement-result-audit-v1"
    )
    audit_id: Literal["s2-development-measurement-result-audit-v1"] = (
        "s2-development-measurement-result-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    measurement_dataset_file_sha256: str
    runner_contract_hash: str
    auditor_contract_hash: str
    input_row_count: Literal[280] = 280
    measurement_row_count: Literal[273] = 273
    measurement_row_manifest_evidence_hash: str
    reconstructed_exactly: Literal[True] = True
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S2_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT"] = (
        "PASS_S2_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
    ] = S2_MEASUREMENT_PREREG_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "measurement_dataset_file_sha256",
        "runner_contract_hash",
        "auditor_contract_hash",
        "measurement_row_manifest_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2DevelopmentMeasurementResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 measurement result audit hash changed")
        return self


def build_measurement_rows(
    payload: S2DevelopmentWeeklyPayload,
) -> tuple[S2DevelopmentMeasurementRow, ...]:
    rows: list[S2DevelopmentMeasurementRow] = []
    for index in range(7, len(payload.rows)):
        current = payload.rows[index - 3 : index + 1]
        prior = payload.rows[index - 7 : index - 3]
        current_tx = sum(row.confirmed_non_coinbase_transaction_count for row in current)
        prior_tx = sum(row.confirmed_non_coinbase_transaction_count for row in prior)
        current_fee = sum(row.confirmed_fee_satoshis for row in current)
        prior_fee = sum(row.confirmed_fee_satoshis for row in prior)
        tx_growth = growth_ppm(current_tx, prior_tx)
        fee_growth = growth_ppm(current_fee, prior_fee)
        source = payload.rows[index]
        rows.append(
            S2DevelopmentMeasurementRow(
                sequence=index + 1,
                week_start=source.week_start,
                decision_cutoff_at=source.decision_cutoff_at,
                earliest_execution_at=source.earliest_execution_at,
                source_payload_evidence_hash=payload.payload_evidence_hash,
                confirmed_tx_current_4w=current_tx,
                confirmed_tx_prior_4w=prior_tx,
                confirmed_fee_sats_current_4w=current_fee,
                confirmed_fee_sats_prior_4w=prior_fee,
                confirmed_tx_growth_ppm=tx_growth,
                confirmed_fee_growth_ppm=fee_growth,
                settlement_demand_agreement=settlement_demand_agreement(
                    tx_growth,
                    fee_growth,
                ),
            )
        )
    if len(rows) != 273 or rows[0].sequence != 8 or rows[-1].sequence != 280:
        raise ValueError("S2 development measurement coverage changed")
    return tuple(rows)


def serialize_measurement_rows(rows: tuple[S2DevelopmentMeasurementRow, ...]) -> bytes:
    return ("\n".join(row.model_dump_json() for row in rows) + "\n").encode()


def measurement_row_hashes(
    rows: tuple[S2DevelopmentMeasurementRow, ...],
) -> tuple[str, ...]:
    return tuple(universe_evidence_hash(row.model_dump(mode="json")) for row in rows)
