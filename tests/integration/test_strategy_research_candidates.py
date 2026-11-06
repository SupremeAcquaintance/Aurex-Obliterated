import os
import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base
from aurex.db.models import (
    StrategyConfig,
    StrategyResearchBacktestRun,
    StrategyResearchCandidate,
    StrategyResearchObservation,
)
from aurex.domain.enums import StrategyResearchStatus


@pytest.fixture()
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_mkt_candidate_registration_forces_research_only_disabled_strategy(
    client: TestClient,
) -> None:
    response = client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": "mkt_whale_research_candidate",
            "strategy": "mkt_whale_research_candidate",
            "display_name": "MKT Whale Research Candidate",
            "hypothesis": "Large Kalshi trades may reveal followable prediction-market pressure.",
            "status": "PAPER_ELIGIBLE",
            "source_reference": "My-Krypt-Trader/python/scanner.py",
            "raw_payload": {"scanner": "whale"},
            "normalized_payload": {"requires_revalidation": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == StrategyResearchStatus.BACKTEST_REQUIRED
    assert body["trade_eligible"] is False
    assert body["observation_count"] == 0
    assert body["required_evidence"]["walk_forward"] == "required"
    assert "backtest" in body["eligibility_reason"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        candidate = session.execute(select(StrategyResearchCandidate)).scalar_one()
        config = session.execute(
            select(StrategyConfig).where(
                StrategyConfig.strategy == "mkt_whale_research_candidate"
            )
        ).scalar_one()
        assert candidate.trade_eligible is False
        assert config.is_enabled is False
        assert config.parameters["research_candidate"] is True
        assert config.parameters["trade_eligible"] is False


def test_mkt_observation_intake_creates_candidate_and_dedupes_source_event(
    client: TestClient,
) -> None:
    payload = {
        "candidate_key": "mkt_momentum_research_candidate",
        "source": "MY_KRYPT_TRADER",
        "strategy": "mkt_momentum_research_candidate",
        "display_name": "MKT Momentum Research Candidate",
        "hypothesis": "Clustered Kalshi prints may predict short-term continuation.",
        "observation_type": "MOMENTUM_CLUSTER",
        "source_event_id": "momentum-fixture-1",
        "symbol": "btcusdt",
        "contract_ticker": "KXBTCD-26JUN25-B62500",
        "side": "YES",
        "confidence": "0.64",
        "implied_probability": "0.59",
        "expected_edge": "0.05",
        "observation_snapshot": {"cluster_count": 8, "fixed_window": False},
        "raw_payload": {"source": "scanner.scan_momentum"},
        "observed_at": datetime.now(UTC).isoformat(),
    }

    first = client.post("/strategies/research-candidates/observations", json=payload)
    second = client.post("/strategies/research-candidates/observations", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["symbol"] == "BTCUSDT"
    assert first.json()["side"] == "YES"
    assert first.json()["evidence_hash"]

    candidates = client.get("/strategies/research-candidates").json()
    assert len(candidates) == 1
    assert candidates[0]["status"] == StrategyResearchStatus.BACKTEST_REQUIRED
    assert candidates[0]["trade_eligible"] is False
    assert candidates[0]["observation_count"] == 1

    observations = client.get("/strategies/research-candidates/observations").json()
    assert len(observations) == 1
    assert observations[0]["observation_snapshot"]["fixed_window"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchObservation)).scalar_one().symbol == "BTCUSDT"


def test_research_backtest_promotes_candidate_to_paper_only_eligibility(
    client: TestClient,
) -> None:
    client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": "mkt_resolved_whale_gate",
            "strategy": "mkt_resolved_whale_gate",
            "display_name": "MKT Resolved Whale Gate",
            "hypothesis": "Resolved whale pressure can remain profitable after fees.",
            "status": "RESEARCH_ONLY",
        },
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(120):
        is_win = index % 4 != 3
        observed_at = start + timedelta(days=index // 4, minutes=index % 4)
        response = client.post(
            "/strategies/research-candidates/observations",
            json={
                "candidate_key": "mkt_resolved_whale_gate",
                "source": "MY_KRYPT_TRADER",
                "strategy": "mkt_resolved_whale_gate",
                "display_name": "MKT Resolved Whale Gate",
                "hypothesis": "Resolved whale pressure can remain profitable after fees.",
                "observation_type": "WHALE_TRADE",
                "source_event_id": f"resolved-whale-{index}",
                "symbol": "BTCUSDT",
                "contract_ticker": f"KXBTCD-26JAN01-{index}",
                "side": "YES",
                "confidence": "0.70",
                "implied_probability": "0.40",
                "expected_edge": "0.10",
                "observation_snapshot": {
                    "category": "CRYPTO" if index % 2 == 0 else "MACRO",
                    "variant_key": "base",
                },
                "observed_at": observed_at.isoformat(),
                "resolved_at": (observed_at + timedelta(days=1)).isoformat(),
                "outcome_snapshot": {"settlement_value": "1" if is_win else "0"},
            },
        )
        assert response.status_code == 200

    candidate_id = client.get("/strategies/research-candidates").json()[0]["id"]
    response = client.post(
        f"/strategies/research-candidates/{candidate_id}/backtest",
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["backtest_run_id"]
    assert body["accepted"] is True
    assert body["decision"] == StrategyResearchStatus.PAPER_ELIGIBLE
    assert body["reasons"] == []
    assert body["metrics"]["total_trades"] == 120
    assert body["metrics"]["out_of_sample"]["total_trades"] >= 30
    assert body["metrics"]["walk_forward"]["passed_windows"] == 3
    assert body["metrics"]["regime_breakdown"]["missing_regime_count"] == 0
    assert body["metrics"]["regime_breakdown"]["passed_group_count"] == 2
    assert body["metrics"]["regime_diagnostics"]["status"] == "PASS"
    assert body["metrics"]["regime_diagnostics"]["thin_group_count"] == 0
    assert body["metrics"]["regime_diagnostics"]["weak_group_count"] == 0
    assert body["metrics"]["regime_diagnostics"]["unknown_regime_rows"] == 0
    assert {
        group["regime"]: group["status"]
        for group in body["metrics"]["regime_diagnostics"]["group_diagnostics"]
    } == {"CRYPTO": "PASS", "MACRO": "PASS"}
    assert body["metrics"]["multiple_testing"]["effective_tested_variant_count"] == 1
    assert body["metrics"]["variant_diagnostics"]["status"] == "PASS"
    assert body["metrics"]["variant_diagnostics"]["actual_variant_count"] == 1
    assert body["metrics"]["variant_diagnostics"]["effective_tested_variant_count"] == 1
    assert body["metrics"]["variant_diagnostics"]["thin_group_count"] == 0
    assert body["metrics"]["variant_diagnostics"]["weak_group_count"] == 0
    assert body["metrics"]["variant_diagnostics"]["group_diagnostics"] == [
        {
            "variant": "base",
            "status": "PASS",
            "total_trades": 120,
            "expectancy": "0.33320000",
            "profit_factor": "4.1977",
            "profit_factor_infinite": False,
            "max_drawdown": "0.41680000",
            "reason": "Variant has positive expectancy and passes profit-factor threshold.",
        }
    ]
    assert body["metrics"]["statistical_significance"]["passed"] is True
    assert body["metrics"]["statistical_significance"]["method"] == (
        "one_sided_binomial_survival_bonferroni"
    )

    evidence = client.get(f"/strategies/research-candidates/{candidate_id}/evidence")
    assert evidence.status_code == 200
    evidence_body = evidence.json()
    assert evidence_body["candidate"]["id"] == candidate_id
    assert evidence_body["latest_backtest"]["id"] == body["backtest_run_id"]
    assert evidence_body["latest_backtest"]["evidence_hash"] == body["evidence_hash"]
    assert evidence_body["evidence_summary"]["observation_count"] == 120
    assert evidence_body["evidence_summary"]["resolved_observation_count"] == 120
    assert evidence_body["evidence_summary"]["backtest_run_count"] == 1
    assert evidence_body["evidence_summary"]["accepted_backtest_run_count"] == 1
    assert len(evidence_body["backtest_runs"]) == 1
    assert len(evidence_body["observations"]) == 50

    with next(client.app.dependency_overrides[get_db]()) as session:
        run = session.execute(select(StrategyResearchBacktestRun)).scalar_one()
        candidate = session.execute(
            select(StrategyResearchCandidate).where(
                StrategyResearchCandidate.candidate_key == "mkt_resolved_whale_gate"
            )
        ).scalar_one()
        config = session.execute(
            select(StrategyConfig).where(
                StrategyConfig.strategy == "mkt_resolved_whale_gate"
            )
        ).scalar_one()
        assert candidate.status == StrategyResearchStatus.PAPER_ELIGIBLE
        assert candidate.trade_eligible is True
        assert candidate.normalized_payload["latest_research_backtest_run_id"] == run.id
        assert run.accepted is True
        assert run.metrics["total_trades"] == 120
        assert config.is_enabled is False
        assert config.parameters["paper_eligible"] is True
        assert config.parameters["live_eligible"] is False
        assert config.parameters["trade_eligible"] is False


def test_research_backtest_blocks_unresolved_or_thin_evidence(
    client: TestClient,
) -> None:
    candidate = client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": "mkt_thin_gate",
            "strategy": "mkt_thin_gate",
            "display_name": "MKT Thin Gate",
            "hypothesis": "A thin sample is not enough for Aurex paper eligibility.",
            "status": "RESEARCH_ONLY",
        },
    ).json()

    response = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["decision"] == StrategyResearchStatus.BACKTEST_REQUIRED
    assert "prediction_research_resolved_observations_missing" in body["reasons"]
    assert "prediction_research_minimum_trades_not_met" in body["reasons"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        config = session.execute(
            select(StrategyConfig).where(StrategyConfig.strategy == "mkt_thin_gate")
        ).scalar_one()
        assert config.is_enabled is False
        assert config.parameters["paper_eligible"] is False
        assert config.parameters["live_eligible"] is False


def test_research_backtest_blocks_missing_regime_coverage(
    client: TestClient,
) -> None:
    candidate = create_resolved_research_candidate(
        client,
        candidate_key="mkt_missing_regime_gate",
        trade_count=24,
        wins_every=1,
        snapshot_for_index=lambda _index: {"variant_key": "base"},
    )

    response = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 20,
            "minimum_oos_trades": 6,
            "minimum_active_days": 12,
            "maximum_single_day_share": "0.10",
            "minimum_walk_forward_windows": 2,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert "prediction_research_regime_missing" in body["reasons"]
    assert "prediction_research_regime_coverage_not_met" in body["reasons"]
    diagnostics = body["metrics"]["regime_diagnostics"]
    assert diagnostics["status"] == "BLOCKED"
    assert diagnostics["blocking_reasons"] == [
        "unknown_regime_rows",
        "insufficient_regime_coverage",
    ]
    assert diagnostics["unknown_regime_rows"] == 24
    assert diagnostics["group_diagnostics"][0]["regime"] == "UNKNOWN"
    assert diagnostics["group_diagnostics"][0]["status"] == "UNKNOWN_REGIME"
    assert diagnostics["next_action"] == (
        "Label MKT observations with regime/category before trusting the gate."
    )


def test_research_backtest_blocks_too_many_tested_variants(
    client: TestClient,
) -> None:
    candidate = create_resolved_research_candidate(
        client,
        candidate_key="mkt_variant_overfit_gate",
        trade_count=24,
        wins_every=1,
        snapshot_for_index=lambda index: {
            "category": "CRYPTO",
            "variant_key": f"threshold_{index}",
        },
    )

    response = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 20,
            "minimum_oos_trades": 6,
            "minimum_active_days": 12,
            "maximum_single_day_share": "0.10",
            "minimum_walk_forward_windows": 2,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 10,
            "maximum_tested_variants": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["metrics"]["multiple_testing"]["effective_tested_variant_count"] == 24
    diagnostics = body["metrics"]["variant_diagnostics"]
    assert diagnostics["status"] == "BLOCKED"
    assert diagnostics["blocking_reasons"] == ["too_many_tested_variants"]
    assert diagnostics["thin_group_count"] == 24
    assert diagnostics["group_diagnostics"][0]["status"] == "THIN_SAMPLE"
    assert diagnostics["next_action"] == (
        "Reduce tested variants or collect new evidence before paper-demo use."
    )
    assert "prediction_research_too_many_tested_variants" in body["reasons"]


def test_research_backtest_blocks_statistically_weak_oos_edge(
    client: TestClient,
) -> None:
    candidate = create_resolved_research_candidate(
        client,
        candidate_key="mkt_weak_statistical_edge",
        trade_count=20,
        wins_every=3,
        snapshot_for_index=lambda _index: {
            "category": "CRYPTO",
            "variant_key": "base",
        },
    )

    response = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 20,
            "minimum_oos_trades": 10,
            "minimum_active_days": 20,
            "maximum_single_day_share": "0.10",
            "minimum_walk_forward_windows": 2,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 10,
            "minimum_statistical_oos_trades": 10,
            "oos_fraction": "0.5",
            "fee_rate": "0",
        },
    )

    assert response.status_code == 200
    body = response.json()
    significance = body["metrics"]["statistical_significance"]
    assert body["accepted"] is False
    assert Decimal(body["metrics"]["out_of_sample"]["expectancy"]) > Decimal("0")
    assert significance["oos_trades"] == 10
    assert significance["wins"] == 7
    assert significance["passed"] is False
    assert significance["adjusted_p_value"] == "0.17187500"
    assert "prediction_research_statistical_significance_not_met" in body["reasons"]


def test_research_backtest_evidence_keeps_every_gate_run(
    client: TestClient,
) -> None:
    candidate = create_resolved_research_candidate(
        client,
        candidate_key="mkt_gate_history",
        trade_count=24,
        wins_every=1,
        snapshot_for_index=lambda _index: {
            "category": "CRYPTO",
            "variant_key": "base",
        },
    )

    accepted = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 20,
            "minimum_oos_trades": 6,
            "minimum_active_days": 12,
            "maximum_single_day_share": "0.10",
            "minimum_walk_forward_windows": 2,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 10,
            "minimum_statistical_oos_trades": 6,
        },
    )
    blocked = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 20,
            "minimum_oos_trades": 6,
            "minimum_active_days": 12,
            "maximum_single_day_share": "0.10",
            "minimum_walk_forward_windows": 2,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 10,
            "minimum_statistical_oos_trades": 6,
            "tested_variant_count": 20,
            "maximum_tested_variants": 3,
        },
    )

    assert accepted.status_code == 200
    assert blocked.status_code == 200
    assert accepted.json()["accepted"] is True
    assert blocked.json()["accepted"] is False

    evidence = client.get(
        f"/strategies/research-candidates/{candidate['id']}/evidence",
        params={"observation_limit": 5, "backtest_limit": 5},
    ).json()

    assert evidence["latest_backtest"]["id"] == blocked.json()["backtest_run_id"]
    assert evidence["evidence_summary"]["backtest_run_count"] == 2
    assert evidence["evidence_summary"]["accepted_backtest_run_count"] == 1
    assert evidence["evidence_summary"]["blocked_backtest_run_count"] == 1
    assert [run["id"] for run in evidence["backtest_runs"]] == [
        blocked.json()["backtest_run_id"],
        accepted.json()["backtest_run_id"],
    ]
    assert evidence["candidate"]["trade_eligible"] is False


def test_research_readiness_queue_ranks_candidates_by_evidence_state(
    client: TestClient,
) -> None:
    accepted = create_resolved_research_candidate(
        client,
        candidate_key="mkt_queue_accepted",
        trade_count=24,
        wins_every=1,
        snapshot_for_index=lambda _index: {
            "category": "CRYPTO",
            "variant_key": "base",
        },
    )
    blocked = create_resolved_research_candidate(
        client,
        candidate_key="mkt_queue_blocked",
        trade_count=24,
        wins_every=1,
        snapshot_for_index=lambda index: {
            "category": "CRYPTO",
            "variant_key": f"variant_{index}",
        },
    )
    client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": "mkt_queue_needs_resolution",
            "strategy": "mkt_queue_needs_resolution",
            "display_name": "MKT Queue Needs Resolution",
            "hypothesis": "Unresolved observations cannot be ranked as ready.",
            "status": "RESEARCH_ONLY",
        },
    )

    base_gate = {
        "minimum_trades": 20,
        "minimum_oos_trades": 6,
        "minimum_active_days": 12,
        "maximum_single_day_share": "0.10",
        "minimum_walk_forward_windows": 2,
        "minimum_walk_forward_pass_rate": "1",
        "minimum_regime_trades": 10,
        "minimum_statistical_oos_trades": 6,
    }
    accepted_gate = client.post(
        f"/strategies/research-candidates/{accepted['id']}/backtest",
        json=base_gate,
    )
    blocked_gate = client.post(
        f"/strategies/research-candidates/{blocked['id']}/backtest",
        json={
            **base_gate,
            "tested_variant_count": 20,
            "maximum_tested_variants": 3,
        },
    )

    assert accepted_gate.status_code == 200
    assert blocked_gate.status_code == 200
    assert accepted_gate.json()["accepted"] is True
    assert blocked_gate.json()["accepted"] is False

    queue = client.get("/strategies/research-candidates/readiness-queue").json()

    assert queue["candidate_count"] == 3
    assert queue["summary"]["paper_research_eligible"] == 1
    assert queue["summary"]["gate_blocked"] == 1
    assert queue["summary"]["needs_resolved_observations"] == 1
    assert [item["candidate_key"] for item in queue["items"]] == [
        "mkt_queue_accepted",
        "mkt_queue_blocked",
        "mkt_queue_needs_resolution",
    ]
    states = {item["candidate_key"]: item for item in queue["items"]}
    assert states["mkt_queue_accepted"]["readiness_state"] == "PAPER_RESEARCH_ELIGIBLE"
    assert states["mkt_queue_accepted"]["latest_backtest_accepted"] is True
    assert states["mkt_queue_accepted"]["oos_trades"] == 8
    assert states["mkt_queue_accepted"]["statistical_significance"].startswith("pass")
    assert states["mkt_queue_accepted"]["regime_diagnostics"] == (
        "PASS: 0 thin, 0 weak, 0 unknown"
    )
    assert states["mkt_queue_accepted"]["variant_diagnostics"] == (
        "PASS: 1/12 tested, 0 thin, 0 weak"
    )
    assert "Paper-demo only" in states["mkt_queue_accepted"]["next_action"]
    assert states["mkt_queue_blocked"]["readiness_state"] == "GATE_BLOCKED"
    assert states["mkt_queue_blocked"]["first_blocker"]
    assert states["mkt_queue_blocked"]["variant_diagnostics"].startswith("BLOCKED:")
    assert states["mkt_queue_needs_resolution"]["readiness_state"] == (
        "NEEDS_RESOLVED_OBSERVATIONS"
    )


def test_mkt_sqlite_preflight_reports_quality_without_mutating_research_ledger(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_db = tmp_path / "krypt-trader.db"
    create_mkt_fixture_db(mkt_db)

    response = client.post(
        "/strategies/research-candidates/preflight-mkt",
        json={"db_path": str(mkt_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 3
    assert body["candidate_ids"] == []
    assert body["processed_observations"] == 3
    assert body["resolved_observations"] == 3
    assert body["quality_status"] == "IMPORT_SPARSE_RESOLVED_SAMPLE"
    assert body["preflight_only"] is True
    assert body["mutates_research_ledger"] is False
    assert body["live_execution_enabled"] is False
    assert "mkt_research_backtest_depth_missing" in body["blockers"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_research_intake_readiness_reports_missing_db_without_mutating(
    client: TestClient,
    tmp_path,
) -> None:
    missing_db = tmp_path / "missing-krypt-trader.db"

    response = client.post(
        "/strategies/research-candidates/mkt-intake-readiness",
        json={"db_path": str(missing_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESEARCH_INTAKE_DB_MISSING"
    assert body["db_exists"] is False
    assert body["db_file_size_bytes"] is None
    assert body["db_modified_at"] is None
    assert body["db_age_seconds"] is None
    assert body["db_freshness_status"] == "RESEARCH_DB_MISSING"
    assert body["logs_dir"] == str(tmp_path / "logs")
    assert body["logs_dir_exists"] is False
    assert body["latest_log_modified_at"] is None
    assert body["log_files"] == []
    assert body["collection_activity_status"] == "RESEARCH_COLLECTION_WAITING_FOR_DB"
    assert body["preflight"] is None
    assert body["safe_to_import_research"] is False
    assert body["ready_for_research_backtest"] is False
    assert "mkt_research_db_missing" in body["blockers"]
    assert body["command_hints"][0]["label"] == "Start MKT scoped demo collection"
    assert "KRYPT_TRADER_USERDATA" in body["command_hints"][0]["command"]
    assert "demo/dry-run" in body["command_hints"][0]["live_execution"]
    assert body["collection_health"]["status"] == "COLLECTION_HEALTH_WAITING_FOR_DB"
    assert body["collection_health"]["processed_observations"] == 0
    assert body["collection_health"]["backtest_depth_progress_pct"] == 0
    assert "mkt_research_db_missing" in body["collection_health"]["blockers"]
    assert body["live_execution_enabled"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_research_intake_runbook_guides_missing_collection_without_mutating(
    client: TestClient,
    tmp_path,
) -> None:
    missing_db = tmp_path / "missing-krypt-trader.db"

    response = client.post(
        "/strategies/research-candidates/mkt-intake-runbook",
        json={"db_path": str(missing_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RUNBOOK_WAITING_FOR_COLLECTION"
    assert body["readiness_status"] == "RESEARCH_INTAKE_DB_MISSING"
    assert body["db_freshness_status"] == "RESEARCH_DB_MISSING"
    assert body["db_file_size_bytes"] is None
    assert body["db_modified_at"] is None
    assert body["processed_observations"] == 0
    assert body["resolved_observations"] == 0
    assert body["unresolved_observations"] == 0
    assert body["backtest_depth_progress_pct"] == 0
    assert body["collection_activity_status"] == "RESEARCH_COLLECTION_WAITING_FOR_DB"
    assert body["collection_health_status"] == "COLLECTION_HEALTH_WAITING_FOR_DB"
    assert body["collection_health"]["status"] == "COLLECTION_HEALTH_WAITING_FOR_DB"
    assert body["preflight_quality_status"] is None
    assert body["current_step"]["key"] == "collector_activity"
    assert body["current_step"]["status"] == "BLOCKED"
    assert body["current_command"] == body["current_step"]["command"]
    assert "KRYPT_TRADER_USERDATA" in body["current_command"]
    assert body["completed_step_count"] == 2
    assert body["total_step_count"] == 8
    assert body["progress_pct"] == 25
    thresholds = {threshold["key"]: threshold for threshold in body["thresholds"]}
    assert thresholds["parseable_research_rows"]["current_count"] == 0
    assert thresholds["parseable_research_rows"]["target_count"] == 1
    assert thresholds["parseable_research_rows"]["remaining_count"] == 1
    assert thresholds["resolved_research_rows"]["remaining_count"] == 1
    assert thresholds["backtest_depth_resolved_rows"]["remaining_count"] == 100
    assert body["live_execution_enabled"] is False
    steps = {step["key"]: step for step in body["steps"]}
    assert steps["scoped_launch_command"]["status"] == "PASSED"
    assert "KRYPT_TRADER_USERDATA" in steps["scoped_launch_command"]["command"]
    assert steps["collector_activity"]["status"] == "BLOCKED"
    assert steps["research_only_import_boundary"]["writes_research_ledger"] is True
    assert steps["research_only_import_boundary"]["status"] == "BLOCKED"
    assert steps["live_execution_boundary"]["status"] == "PASSED"
    assert "collector_activity" in body["blockers"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_research_intake_readiness_reports_starting_from_recent_log(
    client: TestClient,
    tmp_path,
) -> None:
    missing_db = tmp_path / ".aurex-demo-userdata" / "data" / "krypt-trader.db"
    logs_dir = tmp_path / ".aurex-demo-userdata" / "logs"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "service.log"
    log_file.write_text("demo collector started\n", encoding="utf-8")

    response = client.post(
        "/strategies/research-candidates/mkt-intake-readiness",
        json={"db_path": str(missing_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESEARCH_INTAKE_DB_MISSING"
    assert body["logs_dir"] == str(logs_dir)
    assert body["logs_dir_exists"] is True
    assert body["latest_log_modified_at"] is not None
    assert body["log_files"][0]["name"] == "service.log"
    assert body["collection_activity_status"] == "RESEARCH_COLLECTION_STARTING"
    assert body["collection_health"]["status"] == "COLLECTION_HEALTH_STARTING"
    assert "recent_research_db_activity" not in body["collection_health"]["blockers"]
    assert body["live_execution_enabled"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_research_intake_readiness_reports_inactive_empty_db(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_db = tmp_path / "krypt-trader.db"
    create_mkt_fixture_db(mkt_db)
    with sqlite3.connect(mkt_db) as conn:
        conn.executescript(
            """
            DELETE FROM whale_trades;
            DELETE FROM alerts;
            DELETE FROM crypto15m_signals;
            """
        )
    old_timestamp = (datetime.now(UTC) - timedelta(hours=1)).timestamp()
    os.utime(mkt_db, (old_timestamp, old_timestamp))

    response = client.post(
        "/strategies/research-candidates/mkt-intake-readiness",
        json={"db_path": str(mkt_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESEARCH_INTAKE_COLLECTION_INACTIVE"
    assert body["db_freshness_status"] == "RESEARCH_DB_STALE"
    assert body["collection_activity_status"] == "RESEARCH_COLLECTION_INACTIVE"
    assert body["preflight"]["quality_status"] == "IMPORT_EMPTY"
    assert body["collection_health"]["status"] == "COLLECTION_HEALTH_INACTIVE"
    assert body["collection_health"]["processed_observations"] == 0
    assert body["collection_health"]["resolved_observations"] == 0
    assert body["collection_health"]["backtest_depth_progress_pct"] == 0
    assert "recent_research_db_activity" in body["collection_health"]["blockers"]
    assert "research_rows_present" in body["collection_health"]["blockers"]
    assert body["live_execution_enabled"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_research_intake_readiness_separates_import_from_backtest_depth(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_db = tmp_path / "krypt-trader.db"
    create_mkt_fixture_db(mkt_db)

    response = client.post(
        "/strategies/research-candidates/mkt-intake-readiness",
        json={"db_path": str(mkt_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESEARCH_INTAKE_READY_FOR_RESEARCH_IMPORT"
    assert body["db_exists"] is True
    assert body["db_file_size_bytes"] > 0
    assert body["db_modified_at"] is not None
    assert body["db_age_seconds"] is not None
    assert body["db_freshness_status"] == "RESEARCH_DB_RECENT"
    assert body["collection_activity_status"] == "RESEARCH_COLLECTION_DB_RECENT"
    assert body["command_hints"][0]["label"] == "Start MKT scoped demo collection"
    assert str(mkt_db.parent) in body["command_hints"][0]["command"]
    assert body["safe_to_import_research"] is True
    assert body["ready_for_research_backtest"] is False
    assert body["preflight"]["quality_status"] == "IMPORT_SPARSE_RESOLVED_SAMPLE"
    assert body["preflight"]["mutates_research_ledger"] is False
    assert body["collection_health"]["status"] == "COLLECTION_HEALTH_SAMPLE_READY"
    assert body["collection_health"]["processed_observations"] == 3
    assert body["collection_health"]["resolved_observations"] == 3
    assert body["collection_health"]["backtest_depth_progress_pct"] == 3
    assert body["collection_health"]["blockers"] == ["backtest_depth_target"]
    assert "backtest_depth_available" in body["blockers"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_research_intake_runbook_marks_sparse_sample_research_only(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_db = tmp_path / "krypt-trader.db"
    create_mkt_fixture_db(mkt_db)

    response = client.post(
        "/strategies/research-candidates/mkt-intake-runbook",
        json={"db_path": str(mkt_db), "limit_per_source": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RUNBOOK_READY_FOR_RESEARCH_IMPORT"
    assert body["readiness_status"] == "RESEARCH_INTAKE_READY_FOR_RESEARCH_IMPORT"
    assert body["db_freshness_status"] == "RESEARCH_DB_RECENT"
    assert body["db_file_size_bytes"] > 0
    assert body["db_modified_at"] is not None
    assert body["processed_observations"] == 3
    assert body["resolved_observations"] == 3
    assert body["unresolved_observations"] == 0
    assert body["backtest_depth_progress_pct"] == 3
    assert body["collection_health"]["status"] == "COLLECTION_HEALTH_SAMPLE_READY"
    assert body["preflight_quality_status"] == "IMPORT_SPARSE_RESOLVED_SAMPLE"
    assert body["current_step"]["key"] == "research_only_import_boundary"
    assert body["current_step"]["status"] == "READY"
    assert body["current_step"]["writes_research_ledger"] is True
    assert body["current_command"] is None
    assert body["completed_step_count"] == 4
    assert body["total_step_count"] == 8
    assert body["progress_pct"] == 50
    thresholds = {threshold["key"]: threshold for threshold in body["thresholds"]}
    assert thresholds["parseable_research_rows"]["status"] == "PASSED"
    assert thresholds["resolved_research_rows"]["status"] == "PASSED"
    assert thresholds["backtest_depth_resolved_rows"]["current_count"] == 3
    assert thresholds["backtest_depth_resolved_rows"]["target_count"] == 100
    assert thresholds["backtest_depth_resolved_rows"]["remaining_count"] == 97
    assert body["live_execution_enabled"] is False
    steps = {step["key"]: step for step in body["steps"]}
    assert steps["research_rows_present"]["status"] == "PASSED"
    assert steps["resolved_observations_present"]["status"] == "PASSED"
    assert steps["preflight_quality"]["status"] == "RESEARCH_ONLY"
    assert steps["research_only_import_boundary"]["status"] == "READY"
    assert steps["research_only_import_boundary"]["writes_research_ledger"] is True
    assert steps["research_backtest_gate"]["status"] == "BLOCKED"
    assert "research_backtest_gate" in body["blockers"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []


def test_mkt_sqlite_import_records_research_observations_and_dedupes(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_db = tmp_path / "krypt-trader.db"
    create_mkt_fixture_db(mkt_db)

    blocked = client.post(
        "/strategies/research-candidates/import-mkt",
        json={"db_path": str(mkt_db), "limit_per_source": 50},
    )
    assert blocked.status_code == 400
    assert "not backtest-depth evidence" in blocked.json()["detail"]
    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchCandidate)).scalars().all() == []
        assert session.execute(select(StrategyResearchObservation)).scalars().all() == []

    first = client.post(
        "/strategies/research-candidates/import-mkt",
        json={
            "db_path": str(mkt_db),
            "limit_per_source": 50,
            "acknowledge_research_only_import": True,
        },
    )
    second = client.post(
        "/strategies/research-candidates/import-mkt",
        json={
            "db_path": str(mkt_db),
            "limit_per_source": 50,
            "acknowledge_research_only_import": True,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["candidate_count"] == 3
    assert first.json()["processed_observations"] == 3
    assert first.json()["resolved_observations"] == 3
    assert first.json()["unresolved_observations"] == 0
    assert first.json()["source_counts"] == {"whale": 1, "momentum": 1, "crypto15m": 1}
    assert first.json()["quality_status"] == "IMPORT_SPARSE_RESOLVED_SAMPLE"
    assert "mkt_research_backtest_depth_missing" in first.json()["blockers"]
    assert first.json()["research_only_import_acknowledged"] is True
    assert first.json()["preflight_only"] is False
    assert first.json()["mutates_research_ledger"] is True
    assert first.json()["live_execution_enabled"] is False
    source_quality = {item["source"]: item for item in first.json()["source_quality"]}
    assert source_quality["whale"]["status"] == "SOURCE_SPARSE_RESOLVED_SAMPLE"
    assert source_quality["whale"]["resolved_observations"] == 1
    assert source_quality["whale"]["remaining_resolved_observations"] == 99
    assert source_quality["momentum"]["target_resolved_observations"] == 100

    candidates = client.get("/strategies/research-candidates").json()
    assert {candidate["candidate_key"] for candidate in candidates} == {
        "mkt_whale_research_candidate",
        "mkt_momentum_research_candidate",
        "mkt_crypto15m_research_candidate",
    }
    assert all(candidate["trade_eligible"] is False for candidate in candidates)
    candidate_by_key = {candidate["candidate_key"]: candidate for candidate in candidates}
    whale_payload = candidate_by_key["mkt_whale_research_candidate"]["normalized_payload"]
    assert whale_payload["trusted_profitable_strategy"] is False
    assert whale_payload["research_only_import_acknowledged"] is True
    assert whale_payload["import_quality_status"] == "IMPORT_SPARSE_RESOLVED_SAMPLE"
    assert "mkt_research_backtest_depth_missing" in whale_payload["import_blockers"]
    assert whale_payload["source_quality_status"] == "SOURCE_SPARSE_RESOLVED_SAMPLE"
    assert whale_payload["source_resolved_observations"] == 1
    assert whale_payload["source_target_resolved_observations"] == 100

    observations = client.get(
        "/strategies/research-candidates/observations",
        params={"limit": 10},
    ).json()
    assert len(observations) == 3
    assert {observation["source_event_id"] for observation in observations} == {
        "mkt:whale:w-1",
        "mkt:momentum:10",
        "mkt:crypto15m:20",
    }

    momentum = next(
        observation
        for observation in observations
        if observation["source_event_id"] == "mkt:momentum:10"
    )
    assert momentum["side"] == "NO"
    assert Decimal(momentum["implied_probability"]) == Decimal("0.35")
    assert momentum["outcome_snapshot"]["settlement_value"] == "0"

    crypto = next(
        observation
        for observation in observations
        if observation["source_event_id"] == "mkt:crypto15m:20"
    )
    assert crypto["side"] == "NO"
    assert crypto["outcome_snapshot"]["settlement_value"] == "0"

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(StrategyResearchObservation)).all()
        assert (
            session.execute(select(StrategyResearchObservation)).scalars().unique().all()
        )
        assert len(session.execute(select(StrategyResearchObservation)).scalars().all()) == 3


def test_mkt_imported_resolved_rows_can_feed_research_backtest_gate(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_db = tmp_path / "krypt-trader.db"
    create_mkt_fixture_db(mkt_db)
    client.post(
        "/strategies/research-candidates/import-mkt",
        json={
            "db_path": str(mkt_db),
            "sources": ["momentum"],
            "acknowledge_research_only_import": True,
        },
    )
    candidate = client.get("/strategies/research-candidates").json()[0]

    response = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 1,
            "minimum_oos_trades": 1,
            "minimum_active_days": 1,
            "minimum_walk_forward_windows": 1,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 1,
            "minimum_regime_pass_rate": "1",
            "maximum_single_day_share": "1",
            "oos_fraction": "0.5",
            "minimum_statistical_oos_trades": 1,
            "maximum_statistical_p_value": "0.50",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["decision"] == StrategyResearchStatus.PAPER_ELIGIBLE

    with next(client.app.dependency_overrides[get_db]()) as session:
        config = session.execute(
            select(StrategyConfig).where(
                StrategyConfig.strategy == "mkt_momentum_research_candidate"
            )
        ).scalar_one()
        assert config.is_enabled is False
        assert config.parameters["paper_eligible"] is True
        assert config.parameters["live_eligible"] is False


def create_resolved_research_candidate(
    client: TestClient,
    *,
    candidate_key: str,
    trade_count: int,
    wins_every: int,
    snapshot_for_index,
) -> dict:
    candidate = client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": candidate_key,
            "strategy": candidate_key,
            "display_name": candidate_key.replace("_", " ").title(),
            "hypothesis": "Synthetic resolved research fixture for gate behavior.",
            "status": "RESEARCH_ONLY",
        },
    ).json()
    start = datetime(2026, 2, 1, tzinfo=UTC)
    for index in range(trade_count):
        observed_at = start + timedelta(days=index, minutes=index)
        is_win = wins_every == 1 or index % wins_every != 0
        response = client.post(
            "/strategies/research-candidates/observations",
            json={
                "candidate_key": candidate_key,
                "source": "MY_KRYPT_TRADER",
                "strategy": candidate_key,
                "display_name": candidate_key.replace("_", " ").title(),
                "hypothesis": "Synthetic resolved research fixture for gate behavior.",
                "observation_type": "WHALE_TRADE",
                "source_event_id": f"{candidate_key}-{index}",
                "symbol": "BTCUSDT",
                "contract_ticker": f"KXTEST-{index}",
                "side": "YES",
                "confidence": "0.80",
                "implied_probability": "0.40",
                "observation_snapshot": snapshot_for_index(index),
                "observed_at": observed_at.isoformat(),
                "resolved_at": (observed_at + timedelta(hours=1)).isoformat(),
                "outcome_snapshot": {"settlement_value": "1" if is_win else "0"},
            },
        )
        assert response.status_code == 200
    return candidate


def create_mkt_fixture_db(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE whale_trades (
                id INTEGER PRIMARY KEY,
                trade_id TEXT,
                ticker TEXT,
                event_ticker TEXT,
                title TEXT,
                yes_sub_title TEXT,
                category TEXT,
                taker_side TEXT,
                count_fp REAL,
                price REAL,
                dollar_value REAL,
                market_volume REAL,
                open_interest REAL,
                confidence REAL,
                resolved INTEGER,
                outcome_correct INTEGER,
                resolved_price REAL,
                pnl_estimate REAL,
                resolved_at TEXT,
                created_at TEXT
            );
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                event_ticker TEXT,
                title TEXT,
                yes_sub_title TEXT,
                category TEXT,
                signal_type TEXT,
                direction TEXT,
                volume_24h REAL,
                price REAL,
                price_change REAL,
                confidence REAL,
                resolved INTEGER,
                outcome_correct INTEGER,
                resolved_price REAL,
                pnl_estimate REAL,
                resolved_at TEXT,
                created_at TEXT
            );
            CREATE TABLE crypto15m_signals (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                asset TEXT,
                series TEXT,
                close_time TEXT,
                observed_at TEXT,
                mins_left REAL,
                favorite TEXT,
                favorite_price REAL,
                entry_cost REAL,
                up_prob REAL,
                delta_pct REAL,
                open_spot REAL,
                obs_spot REAL,
                resolved INTEGER,
                up_won INTEGER,
                settled_at TEXT,
                kalshi_env TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO whale_trades (
                id, trade_id, ticker, event_ticker, title, category, taker_side,
                count_fp, price, dollar_value, market_volume, open_interest,
                confidence, resolved, outcome_correct, resolved_price, pnl_estimate,
                resolved_at, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                1,
                "w-1",
                "KXBTC-26JAN01-B100000",
                "KXBTC-26JAN01",
                "Bitcoin above 100k",
                "crypto",
                "yes",
                10,
                0.40,
                400,
                10000,
                5000,
                70,
                1,
                1,
                1.0,
                0.58,
                "2026-01-02T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.execute(
            """
            INSERT INTO alerts (
                id, ticker, event_ticker, title, category, signal_type, direction,
                volume_24h, price, price_change, confidence, resolved, outcome_correct,
                resolved_price, pnl_estimate, resolved_at, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                10,
                "KXBTC-26JAN02-B100000",
                "KXBTC-26JAN02",
                "Bitcoin above 100k",
                "crypto",
                "trade_cluster",
                "no",
                50000,
                0.65,
                0.08,
                75,
                1,
                1,
                0.0,
                0.63,
                "2026-01-03T00:00:00Z",
                "2026-01-02T00:00:00Z",
            ),
        )
        conn.execute(
            """
            INSERT INTO crypto15m_signals (
                id, ticker, asset, series, close_time, observed_at, mins_left,
                favorite, favorite_price, entry_cost, up_prob, delta_pct, open_spot,
                obs_spot, resolved, up_won, settled_at, kalshi_env
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                20,
                "KXBTCD-26JAN02-T1200",
                "BTC",
                "KXBTCD",
                "2026-01-02T12:15:00Z",
                "2026-01-02T12:07:00Z",
                8,
                "down",
                0.60,
                0.42,
                0.40,
                0.001,
                100000,
                99850,
                1,
                0,
                "2026-01-02T12:15:30Z",
                "demo",
            ),
        )
