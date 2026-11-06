import json
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UNIVERSE_MANIFEST_SCHEMA_VERSION = "aurex-market-universe-manifest-v1"
UNIVERSE_RULE_SCHEMA_VERSION = "aurex-market-universe-rule-v1"

PartitionName = Literal["DEVELOPMENT", "VALIDATION", "HOLDOUT", "FORWARD"]
PartitionAccess = Literal["OPEN_DEVELOPMENT", "SEALED", "LOCKED_FORWARD"]
UniverseRole = Literal["DECISION_CANDIDATE", "DEVELOPMENT_ONLY", "EXCLUDED"]
ManifestStatus = Literal["READY", "BLOCKED"]
LiquiditySourceMethod = Literal[
    "BINANCE_MARKET_DATA_API",
    "BINANCE_VISION_ARCHIVES",
    "UNAVAILABLE",
]


class ResearchDataPartition(BaseModel):
    name: PartitionName
    start: datetime
    end: datetime | None
    access: PartitionAccess
    strategy_outcomes_may_be_inspected: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("start", "end")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Research partition timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_partition(self) -> "ResearchDataPartition":
        if self.end is not None and self.end <= self.start:
            raise ValueError("Research partition end must be later than its start")
        expected_access = {
            "DEVELOPMENT": "OPEN_DEVELOPMENT",
            "VALIDATION": "SEALED",
            "HOLDOUT": "SEALED",
            "FORWARD": "LOCKED_FORWARD",
        }[self.name]
        if self.access != expected_access:
            raise ValueError(f"{self.name} partition requires access {expected_access}")
        if self.name == "FORWARD" and self.end is not None:
            raise ValueError("Forward partition must be open-ended")
        if self.name != "FORWARD" and self.end is None:
            raise ValueError(f"{self.name} partition requires an end timestamp")
        if self.name != "DEVELOPMENT" and self.strategy_outcomes_may_be_inspected:
            raise ValueError("Sealed and forward partitions cannot expose outcomes")
        return self


class UniverseSelectionRule(BaseModel):
    schema_version: Literal["aurex-market-universe-rule-v1"] = (
        UNIVERSE_RULE_SCHEMA_VERSION
    )
    rule_id: str = Field(min_length=1, max_length=128)
    rule_version: str = Field(min_length=1, max_length=64)
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    quote_asset: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=16)
    selection_start: datetime
    selection_end: datetime
    required_archive_months: list[str] = Field(min_length=1)
    minimum_daily_rows: int = Field(gt=0)
    minimum_active_days: int = Field(gt=0)
    minimum_median_daily_quote_volume: Decimal = Field(ge=0)
    minimum_p10_daily_quote_volume: Decimal = Field(ge=0)
    minimum_decision_markets: int = Field(gt=0)
    liquidity_measure: Literal["DAILY_QUOTE_ASSET_VOLUME"] = (
        "DAILY_QUOTE_ASSET_VOLUME"
    )
    p10_method: Literal["NEAREST_RANK"] = "NEAREST_RANK"
    contamination_ledger_hash: str
    excluded_base_assets: list[str] = Field(default_factory=list)
    excluded_base_suffixes: list[str] = Field(default_factory=list)
    development_only_symbols: list[str] = Field(default_factory=list)
    enumeration_uri: str = Field(min_length=1, max_length=2000)
    archive_base_uri: str = Field(min_length=1, max_length=2000)
    liquidity_api_uri: str = Field(min_length=1, max_length=2000)
    allowed_selection_fields: list[str] = Field(min_length=1)
    forbidden_selection_fields: list[str] = Field(min_length=1)
    use_every_eligible_market: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("quote_asset", "development_only_symbols")
    @classmethod
    def normalize_upper_values(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("excluded_base_assets", "excluded_base_suffixes")
    @classmethod
    def normalize_exclusions(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator("required_archive_months")
    @classmethod
    def validate_months(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(value))
        if len(normalized) != len(value):
            raise ValueError("Required archive months must be unique")
        for month in normalized:
            if len(month) != 7 or month[4] != "-":
                raise ValueError("Archive months must use YYYY-MM format")
            datetime.strptime(month, "%Y-%m")
        return normalized

    @field_validator("selection_start", "selection_end")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Universe rule timestamps must include a timezone")
        return value.astimezone(UTC)

    @field_validator("allowed_selection_fields", "forbidden_selection_fields")
    @classmethod
    def normalize_field_lists(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if not normalized:
            raise ValueError("Universe selection field lists cannot be blank")
        return normalized

    @field_validator("contamination_ledger_hash")
    @classmethod
    def validate_contamination_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_rule(self) -> "UniverseSelectionRule":
        if self.selection_end <= self.selection_start:
            raise ValueError("Universe selection end must be later than its start")
        expected_days = (self.selection_end.date() - self.selection_start.date()).days
        if self.minimum_daily_rows > expected_days:
            raise ValueError("Minimum daily rows cannot exceed selection calendar days")
        if self.minimum_active_days > self.minimum_daily_rows:
            raise ValueError("Minimum active days cannot exceed minimum daily rows")
        if set(self.allowed_selection_fields) & set(self.forbidden_selection_fields):
            raise ValueError("Allowed and forbidden universe fields must not overlap")
        if not self.enumeration_uri.startswith("https://"):
            raise ValueError("Universe enumeration URI must use HTTPS")
        if not self.archive_base_uri.startswith("https://"):
            raise ValueError("Universe archive URI must use HTTPS")
        if not self.liquidity_api_uri.startswith("https://"):
            raise ValueError("Universe liquidity API URI must use HTTPS")
        return self


class UniverseSourceReceipt(BaseModel):
    receipt_id: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=200)
    uri: str = Field(min_length=1, max_length=3000)
    retrieved_at: datetime
    payload_sha256: str
    size_bytes: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Universe source receipt timestamps require a timezone")
        return value.astimezone(UTC)

    @field_validator("payload_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class UniverseSymbolEvidence(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    base_asset: str = Field(min_length=1, max_length=32)
    quote_asset: str = Field(min_length=1, max_length=32)
    archive_listing_evidence_hash: str
    required_archive_months_present: list[str]
    required_checksum_sidecars_present: list[str]
    liquidity_source_method: LiquiditySourceMethod
    liquidity_source_evidence_hash: str | None = None
    daily_quote_volume_evidence_hash: str | None = None
    daily_row_count: int = Field(ge=0)
    active_day_count: int = Field(ge=0)
    duplicate_day_count: int = Field(ge=0)
    missing_day_count: int = Field(ge=0)
    median_daily_quote_volume: Decimal | None = Field(default=None, ge=0)
    p10_daily_quote_volume: Decimal | None = Field(default=None, ge=0)
    source_error: str | None = Field(default=None, max_length=500)
    market_fields_inspected: list[str]
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol", "base_asset", "quote_asset")
    @classmethod
    def normalize_upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("archive_listing_evidence_hash")
    @classmethod
    def validate_required_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("liquidity_source_evidence_hash", "daily_quote_volume_evidence_hash")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @field_validator(
        "required_archive_months_present",
        "required_checksum_sidecars_present",
    )
    @classmethod
    def normalize_months(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @field_validator("market_fields_inspected", "strategy_outcome_fields_inspected")
    @classmethod
    def normalize_fields(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_evidence(self) -> "UniverseSymbolEvidence":
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Universe selection cannot inspect strategy outcomes")
        if self.liquidity_source_method == "UNAVAILABLE":
            if self.source_error is None:
                raise ValueError("Unavailable liquidity evidence requires a source error")
            if any(
                value is not None
                for value in (
                    self.daily_quote_volume_evidence_hash,
                    self.median_daily_quote_volume,
                    self.p10_daily_quote_volume,
                )
            ):
                raise ValueError("Unavailable liquidity evidence cannot contain derived metrics")
        elif (
            self.liquidity_source_evidence_hash is None
            or self.daily_quote_volume_evidence_hash is None
            or self.median_daily_quote_volume is None
            or self.p10_daily_quote_volume is None
        ):
            raise ValueError("Available liquidity evidence requires complete hashes and metrics")
        elif self.source_error is not None:
            raise ValueError("Available liquidity evidence cannot contain a source error")
        elif self.daily_row_count == 0:
            raise ValueError("Available liquidity evidence requires at least one daily row")
        if self.active_day_count > self.daily_row_count:
            raise ValueError("Active liquidity days cannot exceed daily rows")
        return self


class UniverseSymbolAssessment(BaseModel):
    evidence: UniverseSymbolEvidence
    role: UniverseRole
    included: bool
    decision_eligible: bool
    exclusion_reasons: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("exclusion_reasons")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class UniverseManifestSummary(BaseModel):
    enumerated_usdt_markets: int = Field(ge=0)
    decision_market_count: int = Field(ge=0)
    development_only_market_count: int = Field(ge=0)
    excluded_market_count: int = Field(ge=0)
    decision_symbols: list[str]
    development_only_symbols: list[str]

    model_config = ConfigDict(extra="forbid")


class MarketUniverseManifest(BaseModel):
    schema_version: Literal["aurex-market-universe-manifest-v1"] = (
        UNIVERSE_MANIFEST_SCHEMA_VERSION
    )
    generated_at: datetime
    builder_contract_hash: str
    enumeration_bundle_hash: str
    liquidity_input_artifact_hash: str
    rule: UniverseSelectionRule
    partitions: list[ResearchDataPartition]
    source_receipts: list[UniverseSourceReceipt]
    assessments: list[UniverseSymbolAssessment]
    summary: UniverseManifestSummary
    limitations: list[str] = Field(min_length=1)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    status: ManifestStatus
    manifest_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Universe manifest timestamp requires a timezone")
        return value.astimezone(UTC)

    @field_validator(
        "builder_contract_hash",
        "enumeration_bundle_hash",
        "liquidity_input_artifact_hash",
        "manifest_evidence_hash",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("limitations")
    @classmethod
    def normalize_limitations(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if not normalized:
            raise ValueError("Universe limitations cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_manifest_shape(self) -> "MarketUniverseManifest":
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Universe manifest cannot contain inspected strategy outcomes")
        validate_partitions(self.partitions)
        receipt_ids = [receipt.receipt_id for receipt in self.source_receipts]
        if receipt_ids != sorted(receipt_ids) or len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("Universe source receipts must be uniquely sorted")
        symbols = [item.evidence.symbol for item in self.assessments]
        if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
            raise ValueError("Universe assessments must be uniquely sorted by symbol")
        return self


def build_market_universe_manifest(
    *,
    generated_at: datetime,
    builder_contract_hash: str,
    enumeration_bundle_hash: str,
    liquidity_input_artifact_hash: str,
    rule: UniverseSelectionRule,
    partitions: list[ResearchDataPartition],
    source_receipts: list[UniverseSourceReceipt],
    evidence: list[UniverseSymbolEvidence],
    limitations: list[str],
) -> MarketUniverseManifest:
    validate_partitions(partitions)
    assessments = [assess_symbol(rule, item) for item in evidence]
    assessments.sort(key=lambda item: item.evidence.symbol)
    decision_symbols = [
        item.evidence.symbol
        for item in assessments
        if item.role == "DECISION_CANDIDATE"
    ]
    development_symbols = [
        item.evidence.symbol
        for item in assessments
        if item.role == "DEVELOPMENT_ONLY"
    ]
    summary = UniverseManifestSummary(
        enumerated_usdt_markets=len(assessments),
        decision_market_count=len(decision_symbols),
        development_only_market_count=len(development_symbols),
        excluded_market_count=sum(item.role == "EXCLUDED" for item in assessments),
        decision_symbols=decision_symbols,
        development_only_symbols=development_symbols,
    )
    status: ManifestStatus = (
        "READY"
        if summary.decision_market_count >= rule.minimum_decision_markets
        else "BLOCKED"
    )
    payload = {
        "schema_version": UNIVERSE_MANIFEST_SCHEMA_VERSION,
        "generated_at": normalize_timestamp(generated_at),
        "builder_contract_hash": normalize_sha256(builder_contract_hash),
        "enumeration_bundle_hash": normalize_sha256(enumeration_bundle_hash),
        "liquidity_input_artifact_hash": normalize_sha256(
            liquidity_input_artifact_hash
        ),
        "rule": rule,
        "partitions": sorted(partitions, key=lambda item: item.start),
        "source_receipts": sorted(source_receipts, key=lambda item: item.receipt_id),
        "assessments": assessments,
        "summary": summary,
        "limitations": sorted(set(limitations)),
        "strategy_outcome_fields_inspected": [],
        "status": status,
    }
    return MarketUniverseManifest(
        **payload,
        manifest_evidence_hash=universe_evidence_hash(payload),
    )


def assess_symbol(
    rule: UniverseSelectionRule,
    evidence: UniverseSymbolEvidence,
) -> UniverseSymbolAssessment:
    reasons = symbol_exclusion_reasons(rule, evidence)
    if reasons:
        role: UniverseRole = "EXCLUDED"
    elif evidence.symbol in rule.development_only_symbols:
        role = "DEVELOPMENT_ONLY"
    else:
        role = "DECISION_CANDIDATE"
    return UniverseSymbolAssessment(
        evidence=evidence,
        role=role,
        included=role != "EXCLUDED",
        decision_eligible=role == "DECISION_CANDIDATE",
        exclusion_reasons=reasons,
    )


def symbol_exclusion_reasons(
    rule: UniverseSelectionRule,
    evidence: UniverseSymbolEvidence,
) -> list[str]:
    reasons: list[str] = []
    if evidence.quote_asset != rule.quote_asset:
        reasons.append("quote_asset_mismatch")
    if evidence.base_asset in rule.excluded_base_assets:
        reasons.append("excluded_cash_like_base_asset")
    if any(evidence.base_asset.endswith(suffix) for suffix in rule.excluded_base_suffixes):
        reasons.append("excluded_leveraged_token_suffix")
    required_months = set(rule.required_archive_months)
    missing_archives = sorted(
        required_months - set(evidence.required_archive_months_present)
    )
    missing_checksums = sorted(
        required_months - set(evidence.required_checksum_sidecars_present)
    )
    if missing_archives:
        reasons.append(f"required_archives_missing:{','.join(missing_archives)}")
    if missing_checksums:
        reasons.append(f"required_checksum_sidecars_missing:{','.join(missing_checksums)}")
    disallowed_fields = sorted(
        set(evidence.market_fields_inspected) - set(rule.allowed_selection_fields)
    )
    if disallowed_fields:
        reasons.append(f"selection_fields_not_allowed:{','.join(disallowed_fields)}")
    if set(evidence.market_fields_inspected) & set(rule.forbidden_selection_fields):
        reasons.append("forbidden_selection_field_inspected")
    if evidence.liquidity_source_method == "UNAVAILABLE":
        reasons.append("liquidity_source_unavailable")
    if evidence.duplicate_day_count:
        reasons.append("duplicate_liquidity_days")
    if evidence.missing_day_count:
        reasons.append("missing_liquidity_days")
    if evidence.daily_row_count < rule.minimum_daily_rows:
        reasons.append("insufficient_daily_liquidity_rows")
    if evidence.active_day_count < rule.minimum_active_days:
        reasons.append("insufficient_active_liquidity_days")
    if (
        evidence.median_daily_quote_volume is not None
        and evidence.median_daily_quote_volume
        < rule.minimum_median_daily_quote_volume
    ):
        reasons.append("median_daily_quote_volume_below_minimum")
    if (
        evidence.p10_daily_quote_volume is not None
        and evidence.p10_daily_quote_volume < rule.minimum_p10_daily_quote_volume
    ):
        reasons.append("p10_daily_quote_volume_below_minimum")
    return sorted(reasons)


def audit_market_universe_manifest(manifest: MarketUniverseManifest) -> dict[str, object]:
    payload = manifest.model_dump(exclude={"manifest_evidence_hash"})
    hash_matches = manifest.manifest_evidence_hash == universe_evidence_hash(payload)
    assessment_matches = all(
        item == assess_symbol(manifest.rule, item.evidence)
        for item in manifest.assessments
    )
    rebuilt = build_market_universe_manifest(
        generated_at=manifest.generated_at,
        builder_contract_hash=manifest.builder_contract_hash,
        enumeration_bundle_hash=manifest.enumeration_bundle_hash,
        liquidity_input_artifact_hash=manifest.liquidity_input_artifact_hash,
        rule=manifest.rule,
        partitions=manifest.partitions,
        source_receipts=manifest.source_receipts,
        evidence=[item.evidence for item in manifest.assessments],
        limitations=manifest.limitations,
    )
    deterministic_rebuild_matches = rebuilt == manifest
    reasons: list[str] = []
    if not hash_matches:
        reasons.append("manifest_evidence_hash_mismatch")
    if not assessment_matches:
        reasons.append("symbol_assessment_mismatch")
    if not deterministic_rebuild_matches:
        reasons.append("deterministic_manifest_rebuild_mismatch")
    return {
        "status": "PASS" if not reasons else "BLOCKED",
        "manifest_evidence_hash_matches": hash_matches,
        "symbol_assessments_match": assessment_matches,
        "deterministic_rebuild_matches": deterministic_rebuild_matches,
        "recomputed_manifest_evidence_hash": rebuilt.manifest_evidence_hash,
        "reasons": reasons,
    }


def validate_partitions(partitions: list[ResearchDataPartition]) -> None:
    if [item.name for item in partitions] != [
        "DEVELOPMENT",
        "VALIDATION",
        "HOLDOUT",
        "FORWARD",
    ]:
        raise ValueError("Research partitions must use the canonical four-stage order")
    for previous, current in zip(partitions, partitions[1:], strict=False):
        if previous.end != current.start:
            raise ValueError("Research partitions must be contiguous and non-overlapping")


def universe_evidence_hash(payload: object) -> str:
    serialized = json.dumps(
        canonical_value(payload),
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def canonical_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump())
    if isinstance(value, dict):
        return {
            str(key): canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, datetime):
        return normalize_timestamp(value).isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def normalize_timestamp(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("Universe timestamps must include a timezone")
    return value.astimezone(UTC)


def normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError("Universe evidence hashes must be SHA-256 hexadecimal values")
    return normalized
