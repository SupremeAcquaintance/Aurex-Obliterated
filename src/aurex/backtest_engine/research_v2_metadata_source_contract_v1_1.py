from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2P01MetadataSourceContract,
    audit_v2_p01_metadata_source_contract,
    build_v2_p01_metadata_source_contract,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    universe_evidence_hash,
)

V2_METADATA_SOURCE_CONTRACT_V1_1_SCHEMA_VERSION = (
    "aurex-v2-p01-metadata-source-contract-v1.1"
)
V2_METADATA_REPLACED_SOURCE_IDS = [
    "BINANCE_USD_M_ACCOUNT_DOCS",
    "BINANCE_USD_M_MARKET_DATA_DOCS",
]
V2_METADATA_SUPERSESSION_REASON = (
    "V1_BINANCE_CATALOG_HTTP_202_EMPTY_BODY"
)


class V2P01MetadataSourceContractV1_1(V2P01MetadataSourceContract):
    schema_version: Literal[
        "aurex-v2-p01-metadata-source-contract-v1.1"
    ] = V2_METADATA_SOURCE_CONTRACT_V1_1_SCHEMA_VERSION
    contract_id: Literal["v2-p01-metadata-source-contract-v1.1"] = (
        "v2-p01-metadata-source-contract-v1.1"
    )
    contract_version: Literal["1.1.0"] = "1.1.0"
    status: Literal["FROZEN_PRE_REVISED_METADATA_OBSERVATION"] = (
        "FROZEN_PRE_REVISED_METADATA_OBSERVATION"
    )
    supersedes_contract_evidence_hash: str
    supersession_reason_code: Literal[
        "V1_BINANCE_CATALOG_HTTP_202_EMPTY_BODY"
    ] = V2_METADATA_SUPERSESSION_REASON
    replaced_source_ids: list[str] = Field(min_length=2, max_length=2)
    supersession_notes: list[str] = Field(min_length=3)

    @field_validator("supersedes_contract_evidence_hash")
    @classmethod
    def normalize_superseded_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("replaced_source_ids", "supersession_notes")
    @classmethod
    def normalize_v1_1_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_v1_1_contract(self) -> V2P01MetadataSourceContractV1_1:
        if self.replaced_source_ids != sorted(
            V2_METADATA_REPLACED_SOURCE_IDS
        ):
            raise ValueError("V2 metadata superseded source set changed")
        targets = {target.source_id: target for target in self.source_targets}
        for source_id in V2_METADATA_REPLACED_SOURCE_IDS:
            target = targets[source_id]
            if (
                target.source_kind
                != "OFFICIAL_BINANCE_GITHUB_DOCUMENTATION"
                or target.allowed_final_domains != ["raw.githubusercontent.com"]
            ):
                raise ValueError(
                    "V2 metadata replacement must use official Binance GitHub"
                )
        return self


def build_v2_p01_metadata_source_contract_v1_1(
    *,
    supersedes_contract_evidence_hash: str,
    replaced_source_ids: list[str],
    supersession_notes: list[str],
    **values,
) -> V2P01MetadataSourceContractV1_1:
    base = build_v2_p01_metadata_source_contract(**values)
    payload = base.model_dump(exclude={"contract_evidence_hash"})
    payload.update(
        {
            "schema_version": V2_METADATA_SOURCE_CONTRACT_V1_1_SCHEMA_VERSION,
            "contract_id": "v2-p01-metadata-source-contract-v1.1",
            "contract_version": "1.1.0",
            "status": "FROZEN_PRE_REVISED_METADATA_OBSERVATION",
            "supersedes_contract_evidence_hash": normalize_sha256(
                supersedes_contract_evidence_hash
            ),
            "supersession_reason_code": V2_METADATA_SUPERSESSION_REASON,
            "replaced_source_ids": sorted(set(replaced_source_ids)),
            "supersession_notes": sorted(set(supersession_notes)),
        }
    )
    return V2P01MetadataSourceContractV1_1(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_p01_metadata_source_contract_v1_1(
    *,
    contract: V2P01MetadataSourceContractV1_1,
    superseded_contract: V2P01MetadataSourceContract,
) -> dict[str, object]:
    reasons: list[str] = []
    if not audit_v2_p01_metadata_source_contract(contract):
        reasons.append("CONTRACT_HASH_MISMATCH")
    if contract.supersedes_contract_evidence_hash != (
        superseded_contract.contract_evidence_hash
    ):
        reasons.append("SUPERSEDED_CONTRACT_HASH_MISMATCH")
    if contract.frozen_at < superseded_contract.frozen_at:
        reasons.append("SUPERSESSION_PREDATES_V1")

    permitted_contract_changes = {
        "schema_version",
        "contract_id",
        "contract_version",
        "status",
        "frozen_at",
        "builder_contract_hash",
        "source_targets",
        "contract_evidence_hash",
    }
    for field_name in V2P01MetadataSourceContract.model_fields:
        if field_name in permitted_contract_changes:
            continue
        if getattr(contract, field_name) != getattr(
            superseded_contract, field_name
        ):
            reasons.append(f"BOUNDARY_DRIFT:{field_name}")

    old_targets = {
        target.source_id: target for target in superseded_contract.source_targets
    }
    new_targets = {
        target.source_id: target for target in contract.source_targets
    }
    if old_targets.keys() != new_targets.keys():
        reasons.append("SOURCE_SET_DRIFT")
    else:
        permitted_target_changes = {
            "source_kind",
            "requested_url",
            "allowed_final_domains",
        }
        for source_id in old_targets:
            old_target = old_targets[source_id]
            new_target = new_targets[source_id]
            if source_id not in contract.replaced_source_ids:
                if old_target != new_target:
                    reasons.append(f"UNDECLARED_SOURCE_CHANGE:{source_id}")
                continue
            old_payload = old_target.model_dump(
                exclude=permitted_target_changes
            )
            new_payload = new_target.model_dump(
                exclude=permitted_target_changes
            )
            if old_payload != new_payload:
                reasons.append(f"SOURCE_SEMANTIC_DRIFT:{source_id}")
            if old_target.requested_url == new_target.requested_url:
                reasons.append(f"SOURCE_URL_NOT_REPLACED:{source_id}")

    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "contract_evidence_hash": contract.contract_evidence_hash,
    }
