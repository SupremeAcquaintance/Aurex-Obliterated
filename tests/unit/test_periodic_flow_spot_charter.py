import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_spot_charter import (
    PERIODIC_FLOW_BINDING_PATHS,
    PERIODIC_FLOW_FEASIBILITY_GATES,
    PERIODIC_FLOW_NEXT_AUTHORIZATION,
    PERIODIC_FLOW_SOURCE_IDS,
    PeriodicFlowSpotCharter,
    PeriodicFlowSpotCharterAudit,
    audit_periodic_flow_spot_charter,
    audit_periodic_flow_spot_charter_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.audit_periodic_flow_spot_charter import build_audit
from scripts.freeze_periodic_flow_spot_charter import build_charter

CHARTER_PATH = Path("data/evidence/periodic_flow_spot_charter_v1.json")
AUDIT_PATH = Path("data/evidence/periodic_flow_spot_charter_audit_v1.json")


def canonical_charter() -> PeriodicFlowSpotCharter:
    return PeriodicFlowSpotCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def canonical_audit() -> PeriodicFlowSpotCharterAudit:
    return PeriodicFlowSpotCharterAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )


def rehash_charter(payload: dict) -> dict:
    payload["charter_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "charter_evidence_hash"
        }
    )
    return payload


def test_canonical_q1_charter_and_audit_reconstruct_exactly() -> None:
    charter = canonical_charter()
    audit = canonical_audit()

    assert charter == build_charter(frozen_at=charter.frozen_at)
    assert audit == build_audit(
        charter_path=CHARTER_PATH,
        audited_at=audit.audited_at,
    )
    assert audit.charter_evidence_hash == charter.charter_evidence_hash
    assert audit.builder_contract_hash == charter.builder_contract_hash
    assert audit_periodic_flow_spot_charter(charter)
    assert audit_periodic_flow_spot_charter_audit(audit)


def test_q1_charter_has_exact_lineage_sources_and_sealed_partitions() -> None:
    charter = canonical_charter()

    assert tuple(item.path for item in charter.predecessor_bindings) == (
        PERIODIC_FLOW_BINDING_PATHS
    )
    assert tuple(item.source_id for item in charter.research_sources) == (
        PERIODIC_FLOW_SOURCE_IDS
    )
    assert all(source.does_not_prove_edge for source in charter.research_sources)
    assert charter.feasibility_gates == PERIODIC_FLOW_FEASIBILITY_GATES
    assert tuple(partition.role for partition in charter.partitions) == (
        "DEVELOPMENT",
        "VALIDATION",
        "EXCLUDED_WASHOUT",
        "HOLDOUT",
        "FORWARD",
    )
    assert all(
        not partition.outcome_access_permitted for partition in charter.partitions
    )
    assert charter.partitions[3].state == "SEALED_FUTURE"
    assert charter.partitions[4].state == "LOCKED_FORWARD"


def test_q1_preserves_v3p02_stop_and_counts_the_family_predecessor() -> None:
    charter = canonical_charter()
    bindings = {item.path: item for item in charter.predecessor_bindings}

    stop = bindings["data/evidence/v3_p02_payload_pilot_stop_result_v1.json"]
    assert stop.decision == "STOP_V3P02_TRANSPORT_UNRESOLVED_NO_RETRY_NO_SELECTION"
    assert charter.family_predecessor_variant_count == 1
    assert charter.new_parameter_set_budget == 1
    assert charter.project_wide_variant_registry_required is True


def test_q1_grants_metadata_census_only_and_no_trading_authority() -> None:
    charter = canonical_charter()

    assert charter.next_authorization == PERIODIC_FLOW_NEXT_AUTHORIZATION
    assert charter.real_market_values_opened == 0
    assert charter.strategy_candidates_created == 0
    assert charter.strategy_executions == 0
    assert charter.orders_submitted == 0
    assert charter.qualified_strategy_count == 0
    assert charter.market_numeric_fields_inspected == ()
    assert charter.return_metrics_calculated == ()
    assert charter.exact_parameters_defined == ()
    assert charter.mechanism.exact_parameters_defined == ()
    assert charter.mechanism.exact_pine_compatible is False
    authority = (
        charter.authorizes_archive_payload_download,
        charter.authorizes_parameter_definition,
        charter.authorizes_return_testing,
        charter.authorizes_validation_access,
        charter.authorizes_holdout_access,
        charter.authorizes_pine_deployment,
        charter.authorizes_paper_operation,
        charter.authorizes_testnet_strategy_orders,
        charter.authorizes_production,
        charter.authorizes_live,
    )
    assert not any(authority)
    assert charter.real_net_profit_usd == "0"


def test_q1_rejects_rehashed_authority_outcome_and_partition_tampering() -> None:
    payload = canonical_charter().model_dump()
    payload["authorizes_testnet_strategy_orders"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowSpotCharter.model_validate(rehash_charter(payload))

    payload = canonical_charter().model_dump()
    payload["return_metrics_calculated"] = ["net_expectancy"]
    with pytest.raises(ValidationError, match="cannot inspect outcomes"):
        PeriodicFlowSpotCharter.model_validate(rehash_charter(payload))

    payload = canonical_charter().model_dump()
    payload["partitions"][3]["start"] = payload["partitions"][2]["start"]
    with pytest.raises(ValidationError, match="partitions must be contiguous"):
        PeriodicFlowSpotCharter.model_validate(rehash_charter(payload))


@pytest.mark.parametrize(
    ("script", "flag"),
    (
        ("scripts/freeze_periodic_flow_spot_charter.py", "--check"),
        ("scripts/audit_periodic_flow_spot_charter.py", "--check"),
    ),
)
def test_q1_direct_check_commands_pass(script: str, flag: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, flag],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("PASS ")
