from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_REQUIRED_FAMILY_IDS,
    V2SourceCensusContract,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_SOURCE_CENSUS_RESULT_SCHEMA_VERSION = (
    "aurex-v2-derivatives-source-census-result-v1"
)
V2_CENSUS_PASS_DECISION = "PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL"
V2_CENSUS_FAIL_DECISION = "STOP_BINANCE_ARCHIVE_DERIVATIVES_FOUNDATION"


@dataclass(frozen=True, slots=True)
class V2SourceCensusTarget:
    symbol: str
    month: str
    family_id: str
    archive_url: str
    checksum_url: str
    archive_name: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.symbol, self.month, self.family_id


class V2SourceCensusRecord(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    family_id: str = Field(min_length=1, max_length=128)
    archive_url: str = Field(min_length=50, max_length=1000)
    checksum_url: str = Field(min_length=50, max_length=1100)
    checked_at: datetime
    checksum_http_status: Literal[200, 404]
    checksum_text: str | None = Field(default=None, max_length=256)
    checksum_sha256: str | None = None
    archive_http_status: int | None = None
    archive_content_length: int | None = Field(default=None, ge=0)
    archive_last_modified: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_observation(self) -> V2SourceCensusRecord:
        if self.checksum_url != f"{self.archive_url}.CHECKSUM":
            raise ValueError("V2 census checksum URL must match the archive URL")
        if not self.archive_url.startswith("https://data.binance.vision/data/"):
            raise ValueError("V2 census record is not from the official archive")
        if any(
            value is not None
            for value in (
                self.archive_http_status,
                self.archive_content_length,
                self.archive_last_modified,
            )
        ):
            raise ValueError("V2 checksum-only census cannot request archive payloads")
        archive_name = PurePosixPath(urlsplit(self.archive_url).path).name
        if self.checksum_http_status == 200:
            if self.checksum_text is None or self.checksum_sha256 is None:
                raise ValueError("Present checksum observation is incomplete")
            parsed = parse_v2_checksum_text(self.checksum_text, archive_name)
            if parsed != self.checksum_sha256:
                raise ValueError("Stored V2 checksum fields disagree")
        elif self.checksum_text is not None or self.checksum_sha256 is not None:
            raise ValueError("Missing checksum observation cannot contain a checksum")
        return self

    @property
    def is_present(self) -> bool:
        return self.checksum_http_status == 200

    @property
    def key(self) -> tuple[str, str, str]:
        return self.symbol, self.month, self.family_id


class V2SourceCensusFamilySummary(BaseModel):
    family_id: str
    expected_observations: int = Field(ge=1)
    present_observations: int = Field(ge=0)
    missing_observations: int = Field(ge=0)
    complete_symbols: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("complete_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_counts(self) -> V2SourceCensusFamilySummary:
        if (
            self.present_observations + self.missing_observations
            != self.expected_observations
        ):
            raise ValueError("V2 family census counts do not reconcile")
        return self


class V2SourceCensusSummary(BaseModel):
    expected_observations: Literal[5040] = 5040
    completed_observations: Literal[5040] = 5040
    present_observations: int = Field(ge=0, le=5040)
    missing_observations: int = Field(ge=0, le=5040)
    complete_symbols: list[str]
    incomplete_symbols: list[str]
    complete_symbol_count: int = Field(ge=0, le=35)
    family_summaries: list[V2SourceCensusFamilySummary] = Field(
        min_length=6, max_length=6
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("complete_symbols", "incomplete_symbols")
    @classmethod
    def normalize_symbol_lists(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_summary(self) -> V2SourceCensusSummary:
        if (
            self.present_observations + self.missing_observations
            != self.expected_observations
        ):
            raise ValueError("V2 census summary counts do not reconcile")
        if self.complete_symbol_count != len(self.complete_symbols):
            raise ValueError("V2 complete-symbol count does not reconcile")
        if set(self.complete_symbols) & set(self.incomplete_symbols):
            raise ValueError("V2 symbol coverage groups overlap")
        if [item.family_id for item in self.family_summaries] != (
            V2_REQUIRED_FAMILY_IDS
        ):
            raise ValueError("V2 family summaries are not the frozen families")
        return self


class V2SourceCensusResult(BaseModel):
    schema_version: Literal[
        "aurex-v2-derivatives-source-census-result-v1"
    ] = V2_SOURCE_CENSUS_RESULT_SCHEMA_VERSION
    result_id: Literal["v2-derivatives-source-census-result-v1"] = (
        "v2-derivatives-source-census-result-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    source_census_contract_evidence_hash: str
    capability_audit_evidence_hash: str
    predecessor_u1_result_evidence_hash: str
    universe_manifest_evidence_hash: str
    contamination_ledger_evidence_hash: str
    runner_contract_hash: str
    expected_checksum_checks: Literal[5040] = 5040
    completed_checksum_checks: Literal[5040] = 5040
    unresolved_request_count: Literal[0] = 0
    archive_payload_request_count: Literal[0] = 0
    archive_payload_bytes_downloaded: Literal[0] = 0
    records: list[V2SourceCensusRecord] = Field(min_length=5040, max_length=5040)
    summary: V2SourceCensusSummary
    decision: Literal[
        "PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL",
        "STOP_BINANCE_ARCHIVE_DERIVATIVES_FOUNDATION",
    ]
    authorizes_archive_payload_download: Literal[False] = False
    authorizes_market_data_import: Literal[False] = False
    authorizes_strategy_return_calculation: Literal[False] = False
    authorizes_mechanism_selection: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_strategy_eligibility: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    validation_data_loaded: Literal[False] = False
    holdout_data_loaded: Literal[False] = False
    forward_data_loaded: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=4)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "source_census_contract_evidence_hash",
        "capability_audit_evidence_hash",
        "predecessor_u1_result_evidence_hash",
        "universe_manifest_evidence_hash",
        "contamination_ledger_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("strategy_outcome_fields_inspected", "limitations")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V2SourceCensusResult:
        if self.strategy_outcome_fields_inspected:
            raise ValueError("V2 source census cannot inspect strategy outcomes")
        expected_decision = (
            V2_CENSUS_PASS_DECISION
            if self.summary.complete_symbol_count >= 20
            else V2_CENSUS_FAIL_DECISION
        )
        if self.decision != expected_decision:
            raise ValueError("V2 census decision does not follow its threshold")
        if self.records != sorted(self.records, key=lambda item: item.key):
            raise ValueError("V2 census records must use canonical ordering")
        if len({record.key for record in self.records}) != len(self.records):
            raise ValueError("V2 census records contain duplicate keys")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V2 census result hash does not match its evidence")
        return self


def parse_v2_checksum_text(checksum_text: str, archive_name: str) -> str:
    if len(checksum_text.encode("utf-8")) > 4096:
        raise ValueError("V2 checksum response exceeds 4096 bytes")
    value = checksum_text.strip()
    match = re.fullmatch(r"([0-9a-fA-F]{64})(?: {2}|\s+\*)([^\s/\\]+)", value)
    if match is None or match.group(2) != archive_name:
        raise ValueError(f"Malformed V2 checksum for {archive_name}")
    return match.group(1).lower()


def render_v2_source_census_targets(
    contract: V2SourceCensusContract,
) -> list[V2SourceCensusTarget]:
    targets = [
        V2SourceCensusTarget(
            symbol=symbol,
            month=month,
            family_id=family.family_id,
            archive_url=family.archive_url_template.format(
                symbol=symbol,
                month=month,
            ),
            checksum_url=family.checksum_url_template.format(
                symbol=symbol,
                month=month,
            ),
            archive_name=PurePosixPath(
                urlsplit(
                    family.archive_url_template.format(
                        symbol=symbol,
                        month=month,
                    )
                ).path
            ).name,
        )
        for symbol in contract.symbols
        for month in contract.months
        for family in contract.families
    ]
    targets.sort(key=lambda item: item.key)
    if len(targets) != contract.expected_checksum_checks:
        raise ValueError("V2 source census target count changed")
    if len({target.key for target in targets}) != len(targets):
        raise ValueError("V2 source census target matrix contains duplicates")
    return targets


def _build_summary(
    *,
    contract: V2SourceCensusContract,
    records: list[V2SourceCensusRecord],
) -> V2SourceCensusSummary:
    present_keys = {record.key for record in records if record.is_present}
    complete_symbols = [
        symbol
        for symbol in contract.symbols
        if all(
            (symbol, month, family.family_id) in present_keys
            for month in contract.months
            for family in contract.families
        )
    ]
    family_summaries = []
    for family in contract.families:
        family_records = [
            record for record in records if record.family_id == family.family_id
        ]
        family_complete = [
            symbol
            for symbol in contract.symbols
            if all(
                (symbol, month, family.family_id) in present_keys
                for month in contract.months
            )
        ]
        family_present = sum(record.is_present for record in family_records)
        family_summaries.append(
            V2SourceCensusFamilySummary(
                family_id=family.family_id,
                expected_observations=len(contract.symbols) * len(contract.months),
                present_observations=family_present,
                missing_observations=len(family_records) - family_present,
                complete_symbols=family_complete,
            )
        )
    present_count = len(present_keys)
    return V2SourceCensusSummary(
        present_observations=present_count,
        missing_observations=len(records) - present_count,
        complete_symbols=complete_symbols,
        incomplete_symbols=sorted(set(contract.symbols) - set(complete_symbols)),
        complete_symbol_count=len(complete_symbols),
        family_summaries=family_summaries,
    )


def build_v2_source_census_result(
    *,
    generated_at: datetime,
    contract: V2SourceCensusContract,
    runner_contract_hash: str,
    records: list[V2SourceCensusRecord],
    limitations: list[str],
) -> V2SourceCensusResult:
    canonical_records = sorted(records, key=lambda item: item.key)
    targets = render_v2_source_census_targets(contract)
    if len(canonical_records) != len(targets):
        raise ValueError("V2 source census is incomplete")
    for target, record in zip(targets, canonical_records, strict=True):
        if (
            record.key != target.key
            or record.archive_url != target.archive_url
            or record.checksum_url != target.checksum_url
        ):
            raise ValueError("V2 source census record matrix changed")
    summary = _build_summary(contract=contract, records=canonical_records)
    decision = (
        V2_CENSUS_PASS_DECISION
        if summary.complete_symbol_count
        >= contract.decision_rule.minimum_complete_symbols
        else V2_CENSUS_FAIL_DECISION
    )
    payload = {
        "schema_version": V2_SOURCE_CENSUS_RESULT_SCHEMA_VERSION,
        "result_id": "v2-derivatives-source-census-result-v1",
        "result_version": "1.0.0",
        "generated_at": normalize_timestamp(generated_at),
        "status": "COMPLETE",
        "source_census_contract_evidence_hash": contract.contract_evidence_hash,
        "capability_audit_evidence_hash": (
            contract.capability_audit_evidence_hash
        ),
        "predecessor_u1_result_evidence_hash": (
            contract.predecessor_u1_result_evidence_hash
        ),
        "universe_manifest_evidence_hash": (
            contract.universe_manifest_evidence_hash
        ),
        "contamination_ledger_evidence_hash": (
            contract.contamination_ledger_evidence_hash
        ),
        "runner_contract_hash": normalize_sha256(runner_contract_hash),
        "expected_checksum_checks": contract.expected_checksum_checks,
        "completed_checksum_checks": len(canonical_records),
        "unresolved_request_count": 0,
        "archive_payload_request_count": 0,
        "archive_payload_bytes_downloaded": 0,
        "records": canonical_records,
        "summary": summary,
        "decision": decision,
        "authorizes_archive_payload_download": False,
        "authorizes_market_data_import": False,
        "authorizes_strategy_return_calculation": False,
        "authorizes_mechanism_selection": False,
        "creates_candidate": False,
        "creates_strategy_eligibility": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "validation_data_loaded": False,
        "holdout_data_loaded": False,
        "forward_data_loaded": False,
        "strategy_outcome_fields_inspected": [],
        "limitations": sorted(set(limitations)),
    }
    return V2SourceCensusResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_source_census_result(
    *,
    result: V2SourceCensusResult,
    contract: V2SourceCensusContract,
    current_runner_contract_hash: str,
) -> dict[str, object]:
    reasons: list[str] = []
    if result.source_census_contract_evidence_hash != (
        contract.contract_evidence_hash
    ):
        reasons.append("source census contract binding changed")
    if result.capability_audit_evidence_hash != (
        contract.capability_audit_evidence_hash
    ):
        reasons.append("capability-audit binding changed")
    if result.runner_contract_hash != normalize_sha256(
        current_runner_contract_hash
    ):
        reasons.append("source census runner contract changed")
    try:
        rebuilt = build_v2_source_census_result(
            generated_at=result.generated_at,
            contract=contract,
            runner_contract_hash=result.runner_contract_hash,
            records=result.records,
            limitations=result.limitations,
        )
    except ValueError as exc:
        reasons.append(str(exc))
    else:
        if rebuilt != result:
            reasons.append("source census result is not reproducible")
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "result_evidence_hash": result.result_evidence_hash,
        "complete_symbol_count": result.summary.complete_symbol_count,
        "decision": result.decision,
    }
