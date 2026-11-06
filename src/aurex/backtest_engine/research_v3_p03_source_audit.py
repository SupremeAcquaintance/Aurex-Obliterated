from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P03_AUDIT_CONTRACT_SCHEMA_VERSION = (
    "aurex-v3-p03-historical-microstructure-source-audit-contract-v1"
)
V3_P03_AUDIT_RESULT_SCHEMA_VERSION = (
    "aurex-v3-p03-historical-microstructure-source-audit-result-v1"
)
V3_P03_PASS_DECISION = "PERMIT_V3P03_PRIMARY_FEASIBILITY_CONSIDERATION"
V3_P03_FAIL_DECISION = (
    "REJECT_V3P03_REQUIRED_HISTORICAL_MICROSTRUCTURE_EVIDENCE_UNAVAILABLE"
)
V3_P03_REQUIREMENT_IDS = [
    "AGGREGATE_TRADES_2023_2024",
    "DATED_MAKER_TAKER_FEES_AND_REBATES_2023_2024",
    "HISTORICAL_MATCHING_QUEUE_STP_RULES_2023_2024",
    "HISTORICAL_TICK_LOT_NOTIONAL_ORDER_LIMITS_2023_2024",
    "MEASURED_ACK_CANCEL_LATENCY_AND_CLOCK_SYNC",
    "OWN_ORDER_EQUIVALENT_ACK_FILL_CANCEL_REJECT",
    "QUEUE_RECONSTRUCTION_PRICE_TIME_PRIORITY",
    "SEQUENCE_COMPLETE_SUBSECOND_L2_2023_2024",
]
V3_P03_REQUIRED_L2_COLUMNS = [
    "event_time",
    "final_update_id",
    "first_update_id",
    "previous_final_update_id",
    "price",
    "quantity",
    "side",
]
V3_P03_SOURCE_TARGETS = [
    {
        "source_id": "BINANCE_PUBLIC_DATA_README",
        "source_kind": "DOCUMENT",
        "url": (
            "https://raw.githubusercontent.com/binance/binance-public-data/"
            "master/README.md"
        ),
        "maximum_response_bytes": 1_000_000,
    },
    {
        "source_id": "BINANCE_USDM_ACCOUNT_REST_SCHEMA",
        "source_kind": "DOCUMENT",
        "url": (
            "https://developers.binance.com/en/docs/catalog/"
            "core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/"
            "1.0.0/schema.yaml"
        ),
        "maximum_response_bytes": 6_000_000,
    },
    {
        "source_id": "BINANCE_USDM_LOCAL_ORDER_BOOK_DOC",
        "source_kind": "DOCUMENT",
        "url": (
            "https://developers.binance.com/en/docs/products/"
            "derivatives-trading-usds-futures/websocket-market-streams/"
            "How-to-manage-a-local-order-book-correctly"
        ),
        "maximum_response_bytes": 2_000_000,
    },
    {
        "source_id": "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_CHECKSUM",
        "source_kind": "CHECKSUM",
        "url": (
            "https://data.binance.vision/data/futures/um/daily/bookDepth/"
            "BTCUSDT/BTCUSDT-bookDepth-2023-01-01.zip.CHECKSUM"
        ),
        "maximum_response_bytes": 4096,
    },
    {
        "source_id": "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE",
        "source_kind": "ARCHIVE",
        "url": (
            "https://data.binance.vision/data/futures/um/daily/bookDepth/"
            "BTCUSDT/BTCUSDT-bookDepth-2023-01-01.zip"
        ),
        "maximum_response_bytes": 20_000_000,
    },
]


class V3P03SourceTarget(BaseModel):
    source_id: str = Field(pattern=r"^[A-Z0-9_]{5,100}$")
    source_kind: Literal["DOCUMENT", "CHECKSUM", "ARCHIVE"]
    url: str = Field(min_length=30, max_length=1000)
    maximum_response_bytes: int = Field(ge=4096, le=20_000_000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_target(self) -> V3P03SourceTarget:
        parsed = urlparse(self.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname
            not in {
                "data.binance.vision",
                "developers.binance.com",
                "raw.githubusercontent.com",
            }
        ):
            raise ValueError("V3P03 source target is not authoritative HTTPS")
        return self


def authoritative_source_targets() -> list[V3P03SourceTarget]:
    return [V3P03SourceTarget(**item) for item in V3_P03_SOURCE_TARGETS]


class V3P03SourceAuditContract(BaseModel):
    schema_version: Literal[
        "aurex-v3-p03-historical-microstructure-source-audit-contract-v1"
    ] = V3_P03_AUDIT_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["v3-p03-historical-microstructure-source-audit-v1"] = (
        "v3-p03-historical-microstructure-source-audit-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FORMAL_SOURCE_OBSERVATION"] = (
        "FROZEN_PRE_FORMAL_SOURCE_OBSERVATION"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    v3p02_census_result_evidence_hash: str
    builder_contract_hash: str
    proposal_id: Literal["V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION"] = (
        "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION"
    )
    development_period: Literal["2023-01-01_2024-12-31"] = (
        "2023-01-01_2024-12-31"
    )
    requirement_ids: list[str] = Field(min_length=8, max_length=8)
    required_l2_columns: list[str] = Field(min_length=7, max_length=7)
    source_targets: list[V3P03SourceTarget] = Field(min_length=5, max_length=5)
    target_manifest_hash: str
    maximum_http_requests: Literal[5] = 5
    maximum_archive_payload_requests: Literal[1] = 1
    request_timeout_seconds: Literal[60] = 60
    maximum_concurrency: Literal[2] = 2
    qualification_rule: Literal[
        "ALL_EIGHT_REQUIREMENTS_MUST_BE_QUALIFIED_IMMUTABLE_2023_2024"
    ] = "ALL_EIGHT_REQUIREMENTS_MUST_BE_QUALIFIED_IMMUTABLE_2023_2024"
    absence_or_insufficiency_action: Literal[
        "REJECT_PROPOSAL_BEFORE_PRIMARY_SELECTION"
    ] = "REJECT_PROPOSAL_BEFORE_PRIMARY_SELECTION"
    document_and_schema_inspection_permitted: Literal[True] = True
    first_column_timestamp_inspection_permitted: Literal[True] = True
    market_numeric_value_inspection_permitted: Literal[False] = False
    strategy_outcome_inspection_permitted: Literal[False] = False
    credentialed_requests_permitted: Literal[False] = False
    source_substitution_after_observation_permitted: Literal[False] = False
    selection_permitted: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "v3p02_census_result_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "requirement_ids",
        "required_l2_columns",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> V3P03SourceAuditContract:
        expected_targets = authoritative_source_targets()
        if self.requirement_ids != V3_P03_REQUIREMENT_IDS:
            raise ValueError("V3P03 requirement matrix changed")
        if self.required_l2_columns != V3_P03_REQUIRED_L2_COLUMNS:
            raise ValueError("V3P03 required L2 schema changed")
        if self.source_targets != expected_targets:
            raise ValueError("V3P03 source target matrix changed")
        expected_manifest_hash = universe_evidence_hash(
            {"source_targets": [item.model_dump() for item in expected_targets]}
        )
        if self.target_manifest_hash != expected_manifest_hash:
            raise ValueError("V3P03 source target manifest changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V3P03 contract hash does not match")
        return self


class V3P03SourceArtifact(BaseModel):
    source_id: str = Field(pattern=r"^[A-Z0-9_]{5,100}$")
    url: str
    local_path: str = Field(min_length=10, max_length=500)
    observed_at: datetime
    http_status: Literal[200] = 200
    response_bytes: int = Field(ge=1, le=20_000_000)
    content_sha256: str
    content_type: str | None
    matched_markers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("content_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("matched_markers")
    @classmethod
    def normalize_markers(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V3P03BookDepthSchemaEvidence(BaseModel):
    source_id: Literal[
        "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE"
    ] = "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE"
    archive_sha256: str
    published_checksum_sha256: str
    checksum_verified: Literal[True] = True
    archive_member_names: list[str] = Field(min_length=1)
    selected_member_name: str
    header_columns: list[str] = Field(min_length=1)
    data_row_count: int = Field(ge=1)
    required_l2_columns_present: list[str]
    required_l2_columns_missing: list[str]
    numeric_market_fields_inspected: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("archive_sha256", "published_checksum_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "archive_member_names",
        "header_columns",
        "required_l2_columns_present",
        "required_l2_columns_missing",
        "numeric_market_fields_inspected",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_schema(self) -> V3P03BookDepthSchemaEvidence:
        if self.archive_sha256 != self.published_checksum_sha256:
            raise ValueError("V3P03 bookDepth checksum does not reconcile")
        if self.selected_member_name not in self.archive_member_names:
            raise ValueError("V3P03 selected ZIP member is absent")
        present = sorted(set(self.header_columns) & set(V3_P03_REQUIRED_L2_COLUMNS))
        missing = sorted(set(V3_P03_REQUIRED_L2_COLUMNS) - set(self.header_columns))
        if (
            self.required_l2_columns_present != present
            or self.required_l2_columns_missing != missing
        ):
            raise ValueError("V3P03 L2 schema classification does not reconcile")
        if self.numeric_market_fields_inspected:
            raise ValueError("V3P03 schema audit may inspect no market values")
        return self


V3P03RequirementStatus = Literal[
    "QUALIFIED_IMMUTABLE_2023_2024",
    "SOURCE_AVAILABLE_PENDING_PAYLOAD_QUALIFICATION",
    "INSUFFICIENT_AGGREGATED_SNAPSHOT",
    "LIVE_ONLY_NOT_HISTORICAL",
    "CURRENT_ONLY_NOT_DATED",
    "OWN_ACCOUNT_ONLY_NOT_COUNTERFACTUAL",
    "MISSING_MEASURED_EVIDENCE",
]


class V3P03RequirementFinding(BaseModel):
    requirement_id: str
    status: V3P03RequirementStatus
    qualified: bool
    evidence_source_ids: list[str] = Field(min_length=1)
    finding: str = Field(min_length=30, max_length=1500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_source_ids")
    @classmethod
    def normalize_sources(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_finding(self) -> V3P03RequirementFinding:
        expected = self.status == "QUALIFIED_IMMUTABLE_2023_2024"
        if self.qualified != expected:
            raise ValueError("V3P03 requirement qualification does not reconcile")
        return self


class V3P03SourceAuditSummary(BaseModel):
    requirement_count: Literal[8] = 8
    qualified_requirement_count: int = Field(ge=0, le=8)
    failed_requirement_count: int = Field(ge=0, le=8)
    qualified_requirement_ids: list[str]
    failed_requirement_ids: list[str]
    fetched_source_count: Literal[5] = 5
    archive_payload_request_count: Literal[1] = 1
    total_response_bytes: int = Field(ge=1, le=30_000_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("qualified_requirement_ids", "failed_requirement_ids")
    @classmethod
    def normalize_requirements(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_summary(self) -> V3P03SourceAuditSummary:
        if (
            self.qualified_requirement_count + self.failed_requirement_count != 8
            or self.qualified_requirement_count
            != len(self.qualified_requirement_ids)
            or self.failed_requirement_count != len(self.failed_requirement_ids)
            or set(self.qualified_requirement_ids)
            | set(self.failed_requirement_ids)
            != set(V3_P03_REQUIREMENT_IDS)
            or set(self.qualified_requirement_ids)
            & set(self.failed_requirement_ids)
        ):
            raise ValueError("V3P03 requirement summary does not reconcile")
        return self


class V3P03SourceAuditResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p03-historical-microstructure-source-audit-result-v1"
    ] = V3_P03_AUDIT_RESULT_SCHEMA_VERSION
    result_id: Literal["v3-p03-historical-microstructure-source-audit-v1"] = (
        "v3-p03-historical-microstructure-source-audit-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE_NO_RETURN_SOURCE_AUDIT"] = (
        "COMPLETE_NO_RETURN_SOURCE_AUDIT"
    )
    contract_evidence_hash: str
    v3p02_census_result_evidence_hash: str
    runner_contract_hash: str
    source_artifacts: list[V3P03SourceArtifact] = Field(
        min_length=5,
        max_length=5,
    )
    bookdepth_schema_evidence: V3P03BookDepthSchemaEvidence
    requirement_findings: list[V3P03RequirementFinding] = Field(
        min_length=8,
        max_length=8,
    )
    summary: V3P03SourceAuditSummary
    decision: Literal[
        "PERMIT_V3P03_PRIMARY_FEASIBILITY_CONSIDERATION",
        "REJECT_V3P03_REQUIRED_HISTORICAL_MICROSTRUCTURE_EVIDENCE_UNAVAILABLE",
    ]
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "v3p02_census_result_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "market_numeric_values_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V3P03SourceAuditResult:
        expected_sources = {
            item["source_id"] for item in V3_P03_SOURCE_TARGETS
        }
        if (
            len({item.source_id for item in self.source_artifacts}) != 5
            or {item.source_id for item in self.source_artifacts}
            != expected_sources
        ):
            raise ValueError("V3P03 source artifact matrix changed")
        if self.requirement_findings != sorted(
            self.requirement_findings,
            key=lambda item: item.requirement_id,
        ):
            raise ValueError("V3P03 requirement findings are not canonical")
        if (
            len({item.requirement_id for item in self.requirement_findings}) != 8
            or {item.requirement_id for item in self.requirement_findings}
            != set(V3_P03_REQUIREMENT_IDS)
        ):
            raise ValueError("V3P03 requirement finding matrix changed")
        qualified = sorted(
            item.requirement_id
            for item in self.requirement_findings
            if item.qualified
        )
        failed = sorted(set(V3_P03_REQUIREMENT_IDS) - set(qualified))
        if (
            self.summary.qualified_requirement_ids != qualified
            or self.summary.failed_requirement_ids != failed
            or self.summary.total_response_bytes
            != sum(item.response_bytes for item in self.source_artifacts)
        ):
            raise ValueError("V3P03 result summary does not match evidence")
        passed = len(qualified) == 8
        expected_decision = (
            V3_P03_PASS_DECISION if passed else V3_P03_FAIL_DECISION
        )
        if self.decision != expected_decision:
            raise ValueError("V3P03 result decision does not reconcile")
        if (
            self.market_numeric_values_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3P03 source audit may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P03 result hash does not match")
        return self


def build_v3_p03_source_audit_contract(
    **values,
) -> V3P03SourceAuditContract:
    targets = authoritative_source_targets()
    payload = {
        "schema_version": V3_P03_AUDIT_CONTRACT_SCHEMA_VERSION,
        "contract_id": "v3-p03-historical-microstructure-source-audit-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_FORMAL_SOURCE_OBSERVATION",
        "proposal_id": "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
        "development_period": "2023-01-01_2024-12-31",
        "requirement_ids": V3_P03_REQUIREMENT_IDS,
        "required_l2_columns": V3_P03_REQUIRED_L2_COLUMNS,
        "source_targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"source_targets": [item.model_dump() for item in targets]}
        ),
        "maximum_http_requests": 5,
        "maximum_archive_payload_requests": 1,
        "request_timeout_seconds": 60,
        "maximum_concurrency": 2,
        "qualification_rule": (
            "ALL_EIGHT_REQUIREMENTS_MUST_BE_QUALIFIED_IMMUTABLE_2023_2024"
        ),
        "absence_or_insufficiency_action": (
            "REJECT_PROPOSAL_BEFORE_PRIMARY_SELECTION"
        ),
        "document_and_schema_inspection_permitted": True,
        "first_column_timestamp_inspection_permitted": True,
        "market_numeric_value_inspection_permitted": False,
        "strategy_outcome_inspection_permitted": False,
        "credentialed_requests_permitted": False,
        "source_substitution_after_observation_permitted": False,
        "selection_permitted": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P03SourceAuditContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def build_v3_p03_source_audit_result(
    **values,
) -> V3P03SourceAuditResult:
    artifacts = sorted(
        values.pop("source_artifacts"),
        key=lambda item: item.source_id,
    )
    findings = sorted(
        values.pop("requirement_findings"),
        key=lambda item: item.requirement_id,
    )
    qualified = sorted(
        item.requirement_id for item in findings if item.qualified
    )
    failed = sorted(set(V3_P03_REQUIREMENT_IDS) - set(qualified))
    summary = V3P03SourceAuditSummary(
        qualified_requirement_count=len(qualified),
        failed_requirement_count=len(failed),
        qualified_requirement_ids=qualified,
        failed_requirement_ids=failed,
        total_response_bytes=sum(item.response_bytes for item in artifacts),
    )
    payload = {
        "schema_version": V3_P03_AUDIT_RESULT_SCHEMA_VERSION,
        "result_id": "v3-p03-historical-microstructure-source-audit-v1",
        "result_version": "1.0.0",
        "status": "COMPLETE_NO_RETURN_SOURCE_AUDIT",
        "source_artifacts": artifacts,
        "bookdepth_schema_evidence": values.pop(
            "bookdepth_schema_evidence"
        ),
        "requirement_findings": findings,
        "summary": summary,
        "decision": (
            V3_P03_PASS_DECISION if len(qualified) == 8 else V3_P03_FAIL_DECISION
        ),
        "selects_primary": False,
        "creates_candidate": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "market_numeric_values_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P03SourceAuditResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p03_source_audit_contract(
    contract: V3P03SourceAuditContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )


def audit_v3_p03_source_audit_result(
    result: V3P03SourceAuditResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
