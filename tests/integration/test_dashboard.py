import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base


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


def test_dashboard_shell_and_assets_are_served(client: TestClient) -> None:
    dashboard = client.get("/dashboard")
    script = client.get("/dashboard/assets/app.js")
    styles = client.get("/dashboard/assets/styles.css")

    assert dashboard.status_code == 200
    assert '/dashboard/assets/app.js?v=20261011-1' in dashboard.text
    assert '/dashboard/assets/styles.css?v=20261011-1' in dashboard.text
    assert '/dashboard/assets/dashboard-transport.js?v=20261011-1' in dashboard.text
    assert client.get('/dashboard/assets/dashboard-transport.js').status_code == 200
    assert "Command Center" in dashboard.text
    assert "Market Preview" in dashboard.text
    assert "Market posture" in dashboard.text
    assert "Platform readiness" in dashboard.text
    assert 'id="platform-readiness"' in dashboard.text
    assert "Current blocker" in dashboard.text
    assert "Factory contract" in dashboard.text
    assert "Research gates" in dashboard.text
    assert "Qualified strategy" in dashboard.text
    assert "Backtest authority" in dashboard.text
    assert "External signal" in dashboard.text
    assert "Paper evidence" in dashboard.text
    assert "Broker sandbox" in dashboard.text
    assert "Displayed checks" in dashboard.text
    assert "Operator runtime" in dashboard.text
    assert 'id="native-start-button"' in dashboard.text
    assert 'id="native-stop-button"' in dashboard.text
    assert 'id="native-process"' in dashboard.text
    assert 'id="preview-chart-empty"' in dashboard.text
    assert 'class="candle-strip"' not in dashboard.text
    assert "Live boundary" in dashboard.text
    assert "command-evidence-pine" in dashboard.text
    assert "command-evidence-protocol" in dashboard.text
    assert "command-evidence-manifest" in dashboard.text
    assert "command-evidence-backtest" in dashboard.text
    assert "command-evidence-signal" in dashboard.text
    assert "command-evidence-paper" in dashboard.text
    assert "command-evidence-broker" in dashboard.text
    assert "Strategy Portfolio" in dashboard.text
    assert "Research candidates" in dashboard.text
    assert "Observation type" in dashboard.text
    assert "MKT DB path" in dashboard.text
    assert "Research gate" in dashboard.text
    assert "OOS drawdown" in dashboard.text
    assert "Variant pressure" in dashboard.text
    assert "Readiness queue" in dashboard.text
    assert "Ready for gate" in dashboard.text
    assert "MKT import quality" in dashboard.text
    assert "MKT runbook" in dashboard.text
    assert "MKT research runbook" in dashboard.text
    assert "Research-only MKT import" in dashboard.text
    assert "Intake gate" in dashboard.text
    assert "DB freshness" in dashboard.text
    assert "Log activity" in dashboard.text
    assert "Collection health" in dashboard.text
    assert "Start command" in dashboard.text
    assert "Resolved depth" in dashboard.text
    assert "Ledger writes" in dashboard.text
    assert "Runbook next" in dashboard.text
    assert "Current step" in dashboard.text
    assert "Current command" in dashboard.text
    assert "Runbook progress" in dashboard.text
    assert "Intake next" in dashboard.text
    assert "Import next" in dashboard.text
    assert "Evidence drilldown" in dashboard.text
    assert "Gate history" in dashboard.text
    assert "Selected candidate" in dashboard.text
    assert "Backtest" in dashboard.text
    assert "Analyst" in dashboard.text
    assert "Broker Readiness" in dashboard.text
    assert "Operator Access Profile" in dashboard.text
    assert "Binance Spot Testnet boundary" in dashboard.text
    assert "User-stream contract" in dashboard.text
    assert "Reconnect recovery" in dashboard.text
    assert "sandbox-profile-state" in dashboard.text
    assert "sandbox-profile-adapter-authority" in dashboard.text
    assert "sandbox-connectivity-public" in dashboard.text
    assert "sandbox-connectivity-auth" in dashboard.text
    assert "sandbox-connectivity-test-order" in dashboard.text
    assert "sandbox-connectivity-cancel" in dashboard.text
    assert "sandbox-connectivity-reconciliation" in dashboard.text
    assert "sandbox-profile-order-authority" in dashboard.text
    assert "sandbox-profile-qualification" in dashboard.text
    assert "sandbox-profile-live-authority" in dashboard.text
    assert "TESTNET FUNDS ARE VIRTUAL" in dashboard.text
    assert "operator-profile-preflight-button" in dashboard.text
    assert "operator-profile-download-button" in dashboard.text
    assert "operator-profile-copy-freeze-button" in dashboard.text
    assert "operator-profile-gate-list" in dashboard.text
    assert "Capital and loss boundary" in dashboard.text
    assert "NO CREDENTIALS" in dashboard.text
    assert "Live Micro-Deployment" in dashboard.text
    assert "Backtest Evidence Intake" in dashboard.text
    assert "Prediction Markets" in dashboard.text
    assert "Market snapshot" in dashboard.text
    assert "Snapshot CSV" in dashboard.text
    assert "CSV preflight" in dashboard.text
    assert "Importable rows" in dashboard.text
    assert "Actionable quotes" in dashboard.text
    assert "Contract snapshot CSV" in dashboard.text
    assert "MKT DB snapshots" in dashboard.text
    assert "Donor runbook" in dashboard.text
    assert "MKT runbook" in dashboard.text
    assert "Runbook blockers" in dashboard.text
    assert "Runbook next" in dashboard.text
    assert "MKT donor runbook" in dashboard.text
    assert "prediction-mkt-donor-runbook-body" in dashboard.text
    assert "Demo bootstrap" in dashboard.text
    assert "MKT bootstrap" in dashboard.text
    assert "Bootstrap settings" in dashboard.text
    assert "Bootstrap next" in dashboard.text
    assert "MKT demo bootstrap" in dashboard.text
    assert "prediction-mkt-donor-bootstrap-body" in dashboard.text
    assert "Launch preflight" in dashboard.text
    assert "Copy launch" in dashboard.text
    assert "MKT launch" in dashboard.text
    assert "Launch boundary" in dashboard.text
    assert "Launch command" in dashboard.text
    assert "Launch next" in dashboard.text
    assert "MKT launch preflight" in dashboard.text
    assert "prediction-mkt-donor-launch-body" in dashboard.text
    assert "Collection status" in dashboard.text
    assert "MKT collection" in dashboard.text
    assert "Collection DB" in dashboard.text
    assert "Collection freshness" in dashboard.text
    assert "Collection quality" in dashboard.text
    assert "Evidence tier" in dashboard.text
    assert "Quality next" in dashboard.text
    assert "Collection next" in dashboard.text
    assert "Collection recheck" in dashboard.text
    assert "MKT collection monitor" in dashboard.text
    assert "prediction-mkt-donor-collection-body" in dashboard.text
    assert "MKT collection quality gates" in dashboard.text
    assert "prediction-mkt-donor-collection-quality-body" in dashboard.text
    assert "MKT launch health gates" in dashboard.text
    assert "prediction-mkt-donor-launch-health-body" in dashboard.text
    assert "Runtime safety" in dashboard.text
    assert "MKT safety" in dashboard.text
    assert "Safety checks" in dashboard.text
    assert "Safety blockers" in dashboard.text
    assert "Settings path" in dashboard.text
    assert "Userdata path" in dashboard.text
    assert "Safety next" in dashboard.text
    assert "MKT runtime safety" in dashboard.text
    assert "prediction-mkt-runtime-safety-body" in dashboard.text
    assert "MKT settings path" in dashboard.text
    assert "MKT userdata path" in dashboard.text
    assert "Donor readiness" in dashboard.text
    assert "MKT donor" in dashboard.text
    assert "Donor DBs" in dashboard.text
    assert "Donor blockers" in dashboard.text
    assert "Donor next" in dashboard.text
    assert "DB discover" in dashboard.text
    assert "MKT DB discovery" in dashboard.text
    assert "Ready discovered DBs" in dashboard.text
    assert "Discovery next" in dashboard.text
    assert "Discovered DB candidates" in dashboard.text
    assert "prediction-mkt-db-discovery-body" in dashboard.text
    assert "DB readiness" in dashboard.text
    assert "MKT DB readiness" in dashboard.text
    assert "Usable DB rows" in dashboard.text
    assert "DB next" in dashboard.text
    assert "DB inventory" in dashboard.text
    assert "MKT DB inventory" in dashboard.text
    assert "Inventory rows" in dashboard.text
    assert "Inventory blockers" in dashboard.text
    assert "Inventory next" in dashboard.text
    assert "prediction-mkt-db-inventory-body" in dashboard.text
    assert "Campaign readiness" in dashboard.text
    assert "Campaign manifest" in dashboard.text
    assert "Campaign data" in dashboard.text
    assert "Campaign evidence tier" in dashboard.text
    assert "Campaign gate" in dashboard.text
    assert "Readiness next" in dashboard.text
    assert "Manifest hash" in dashboard.text
    assert "Manifest next" in dashboard.text
    assert "DB preflight" in dashboard.text
    assert "DB import" in dashboard.text
    assert "Campaign preflight" in dashboard.text
    assert "Campaign replay" in dashboard.text
    assert "Projected fee-net P/L" in dashboard.text
    assert "Opposite-side P/L" in dashboard.text
    assert "Projection blocker" in dashboard.text
    assert "Side sensitivity" in dashboard.text
    assert "Campaign evidence" in dashboard.text
    assert "Acknowledge side sensitivity" in dashboard.text
    assert "Side rationale" in dashboard.text
    assert "MKT DB path" in dashboard.text
    assert "Paper order" in dashboard.text
    assert "Open fees" in dashboard.text
    assert "Lifecycle fees" in dashboard.text
    assert "prediction-action" in dashboard.text
    assert "SELL to close" in dashboard.text
    assert "Manual max quote age s" in dashboard.text
    assert "Manual max spread" in dashboard.text
    assert "Manual max latency ms" in dashboard.text
    assert "Manual max slippage" in dashboard.text
    assert "Paper intent gate" in dashboard.text
    assert "Gate evidence" in dashboard.text
    assert "Latest intent gate" in dashboard.text
    assert "Paper demo readiness" in dashboard.text
    assert "Start readiness" in dashboard.text
    assert "Demo lifecycle" in dashboard.text
    assert "Next demo action" in dashboard.text
    assert "Demo evidence target" in dashboard.text
    assert "Closed records" in dashboard.text
    assert "Calendar days" in dashboard.text
    assert "Active days" in dashboard.text
    assert "Unique contracts" in dashboard.text
    assert "Expectancy" in dashboard.text
    assert "Concentration" in dashboard.text
    assert "Contract concentration" in dashboard.text
    assert "Provenance" in dashboard.text
    assert "Ledger clean" in dashboard.text
    assert "Next evidence action" in dashboard.text
    assert "Demo ledger" in dashboard.text
    assert "Evidence" in dashboard.text
    assert "prediction-demo-ledger-body" in dashboard.text
    assert "Campaign audit" in dashboard.text
    assert "prediction-demo-campaign-body" in dashboard.text
    assert "Donor tier" in dashboard.text
    assert "Current ledger" in dashboard.text
    assert "Demo run" in dashboard.text
    assert "Batch preflight" in dashboard.text
    assert "Batch replay" in dashboard.text
    assert "prediction-demo-batch-state" in dashboard.text
    assert "Batch audit" in dashboard.text
    assert "prediction-demo-batch-audit-body" in dashboard.text
    assert "Cancel" in dashboard.text
    assert "Rejected intents" in dashboard.text
    assert "Expected fingerprint" in dashboard.text
    assert "Alert setup" in dashboard.text
    assert "Webhook URL" in dashboard.text
    assert "Webhook auth" in dashboard.text
    assert "signals-contract-status" in dashboard.text
    assert "signals-alert-setup-status" in dashboard.text
    assert "signal-alert-setup-button" in dashboard.text
    assert "Runbook progress" in dashboard.text
    assert "signals-runbook-body" in dashboard.text
    assert "External proof" in dashboard.text
    assert "Delivery proof" in dashboard.text
    assert "Aurex pipeline" in dashboard.text
    assert "signals-verification-body" in dashboard.text
    assert "signals-verification-delivery" in dashboard.text
    assert "signals-verification-pipeline" in dashboard.text
    assert "signals-verification-origin" in dashboard.text
    assert "Preflight alert" in dashboard.text
    assert "Expected webhook" in dashboard.text
    assert "Duplicate check" in dashboard.text
    assert "Idempotency" in dashboard.text
    assert "signal-preflight-payload" in dashboard.text
    assert "Paper Evidence Intake" in dashboard.text
    assert "Collection status" in dashboard.text
    assert "Preflight" in dashboard.text
    assert "Export window" in dashboard.text
    assert "Fix queue" in dashboard.text
    assert "Backtest evidence" in dashboard.text
    assert "Paper eligibility" in dashboard.text
    assert "backtest-paper-eligibility" in dashboard.text
    assert "Walk-forward" in dashboard.text
    assert "Regime coverage" in dashboard.text
    assert "Parameter evidence" in dashboard.text
    assert "Statistical edge" in dashboard.text
    assert "Pine setup" in dashboard.text
    assert "Historical data" in dashboard.text
    assert "Dataset rows" in dashboard.text
    assert "Missing intervals" in dashboard.text
    assert "Dataset hash" in dashboard.text
    assert "backtest-ohlcv-preflight-button" in dashboard.text
    assert "backtest-ohlcv-import-button" in dashboard.text
    assert "backtest-ohlcv-file" in dashboard.text
    assert "backtest-ohlcv-manifest-file" in dashboard.text
    assert "backtest-ohlcv-manifest" in dashboard.text
    assert "backtest-ohlcv-continuity" in dashboard.text
    assert "backtest-ohlcv-source-verification" in dashboard.text
    assert "backtest-ohlcv-input-hash" in dashboard.text
    assert "Reference replay" in dashboard.text
    assert "COMPARISON ONLY" in dashboard.text
    assert "backtest-reference-button" in dashboard.text
    assert "backtest-reference-dataset-id" in dashboard.text
    assert "backtest-reference-warmup" in dashboard.text
    assert "backtest-parity-preflight-button" in dashboard.text
    assert "backtest-parity-record-button" in dashboard.text
    assert "backtest-parity-dataset-id" in dashboard.text
    assert "backtest-parity-chart-dataset-id" in dashboard.text
    assert "backtest-parity-report-id" in dashboard.text
    assert "backtest-parity-export-attestation" in dashboard.text
    assert "backtest-parity-lineage-button" in dashboard.text
    assert "backtest-parity-lineage-state" in dashboard.text
    assert "backtest-parity-lineage-hash" in dashboard.text
    assert "backtest-parity-body" in dashboard.text
    assert "backtest-parity-market-match" in dashboard.text
    assert "Pre-registered protocol" in dashboard.text
    assert "backtest-setup-button" in dashboard.text
    assert "backtest-window-plan-button" in dashboard.text
    assert "backtest-window-plan-summary" in dashboard.text
    assert "backtest-protocol-button" in dashboard.text
    assert "backtest-protocol-id" in dashboard.text
    assert "Frozen TradingView run" in dashboard.text
    assert "backtest-run-manifest-button" in dashboard.text
    assert "backtest-run-package-button" in dashboard.text
    assert "backtest-copy-pine-button" in dashboard.text
    assert "backtest-copy-setup-button" in dashboard.text
    assert "backtest-run-ticker" in dashboard.text
    assert "backtest-run-package-hash" in dashboard.text
    assert "backtest-run-source" in dashboard.text
    assert "backtest-reference-point-value" in dashboard.text
    assert "backtest-reference-minimum-contract" in dashboard.text
    assert "backtest-parity-point-value" in dashboard.text
    assert "backtest-parity-minimum-contract" in dashboard.text
    assert "backtest-setup-summary" in dashboard.text
    assert "Parameters JSON" in dashboard.text
    assert "Walk-forward windows JSON" in dashboard.text
    assert "backtest-walk-forward-windows" in dashboard.text
    assert "Acceptance JSON" in dashboard.text
    assert "min_walk_forward_windows" in dashboard.text
    assert "min_walk_forward_pass_rate" in dashboard.text
    assert "TradingView CSV file" in dashboard.text
    assert "backtest-csv-file" in dashboard.text
    assert "Report CSV contents" in dashboard.text
    assert "<th>Provenance</th>" in dashboard.text
    assert "<th>Delivery</th>" in dashboard.text
    assert "Activation audit" in dashboard.text
    assert "Live execution adapter" in dashboard.text
    assert "MKT credential boundary" in dashboard.text
    assert "Paper freshness" in dashboard.text
    assert "Paper progress" in dashboard.text
    assert "Paper scope" in dashboard.text
    assert "Paper coverage" in dashboard.text
    assert "Paper integrity" in dashboard.text
    assert "Journal coverage" in dashboard.text
    assert "Prediction demo" in dashboard.text
    assert "Current demo gate" in dashboard.text
    assert "Readiness progress" in dashboard.text
    assert "Current evidence gate" in dashboard.text
    assert "Evidence progress" in dashboard.text
    assert "Demo runbook" in dashboard.text
    assert "Current runbook step" in dashboard.text
    assert "Research blocker" in dashboard.text
    assert "Paper/demo runbook" in dashboard.text
    assert "Statement reconciliation" in dashboard.text
    assert "Statement freshness" in dashboard.text
    assert "Statement CSV" in dashboard.text
    assert "Statement fixes" in dashboard.text
    assert "First profit milestone" in dashboard.text
    assert "Strategy review" in dashboard.text
    assert "Broker packet" in dashboard.text
    assert "Broker diligence" in dashboard.text
    assert "Submit packet" in dashboard.text
    assert "Record decision" in dashboard.text
    assert "Profit check" in dashboard.text
    assert "Terms reference" in dashboard.text
    assert "Approval domain" in dashboard.text
    assert "/risk/status" in script.text
    assert "/performance/summary" in script.text
    assert "/performance/equity-curve?limit=80" in script.text
    assert "/strategies/comparison" in script.text
    assert "/strategies/research-candidates" in script.text
    assert "/strategies/research-candidates/readiness-queue" in script.text
    assert "/strategies/research-candidates/observations?limit=20" in script.text
    assert "/strategies/research-candidates/mkt-intake-readiness" in script.text
    assert "/strategies/research-candidates/mkt-intake-runbook" in script.text
    assert "/strategies/research-candidates/preflight-mkt" in script.text
    assert "/strategies/research-candidates/import-mkt" in script.text
    research_evidence_path = (
        "/strategies/research-candidates/${encodeURIComponent(candidate.id)}/evidence"
    )
    assert research_evidence_path in script.text
    research_backtest_path = (
        "/strategies/research-candidates/${encodeURIComponent(candidate.id)}/backtest"
    )
    assert research_backtest_path in script.text
    assert "/analyst/summary" in script.text
    assert "/analyst/risk-anomalies/scan" in script.text
    assert "/broker/readiness" in script.text
    assert "/broker/emergency-stop" in script.text
    assert "/live/deployment" in script.text
    assert "/live/deployment/paper-evidence/run" in script.text
    assert "/live/deployment/broker-statements/preflight-csv" in script.text
    assert "/live/deployment/broker-statements/reconcile-csv" in script.text
    assert "/live/deployment/approval-packet" in script.text
    assert "/live/deployment/approvals" in script.text
    assert "/live/deployment/profit-milestone/run" in script.text
    assert "/live/deployment/evidence-review/run" in script.text
    assert "/live/deployment/evidence-reviews" in script.text
    assert "/backtests/reports?limit=10" in script.text
    assert "/backtests/paper-eligibility?strategy=${encodedStrategy}" in script.text
    assert "/backtests/ohlcv/datasets?limit=10" in script.text
    assert 'api("/backtests/ohlcv/preflight-csv"' in script.text
    assert 'api("/backtests/ohlcv/import-csv"' in script.text
    assert "preflightBacktestOhlcv" in script.text
    assert "importBacktestOhlcv" in script.text
    assert "loadBacktestOhlcvFile" in script.text
    assert 'api("/backtests/reference-replay/preflight"' in script.text
    assert "/backtests/reference-replay/runs?limit=10" in script.text
    assert 'api("/backtests/reference-replay/runs"' in script.text
    assert "/backtests/reference-replay/validations?limit=10" in script.text
    assert '"/backtests/reference-replay/validations/preflight"' in script.text
    assert 'api("/backtests/reference-replay/validations"' in script.text
    assert 'api("/backtests/parity/preflight"' in script.text
    assert 'api("/backtests/parity/runs"' in script.text
    assert "preflightReferenceReplay" in script.text
    assert "recordReferenceReplay" in script.text
    assert "preflightReferenceReplayValidation" in script.text
    assert "recordReferenceReplayValidation" in script.text
    assert "renderBacktestReferenceReplay" in script.text
    assert "/backtests/protocols?limit=20" in script.text
    assert 'api("/backtests/protocols"' in script.text
    assert "/run-manifest`" in script.text
    assert 'api("/backtests/window-plan"' in script.text
    assert "planBacktestWalkForwardWindows" in script.text
    assert "loadBacktestCsvFile" in script.text
    assert "/backtests/strategy-setup?strategy=${encodedStrategy}" in script.text
    assert "/backtests/report-template.csv" in script.text
    assert "/backtests/reports/preflight-csv" in script.text
    assert "/backtests/reports/import-csv" in script.text
    assert "/backtests/parity/export-manifest/preflight" in script.text
    assert "preflightBacktestParityExportManifest" in script.text
    assert "reviewed_export_manifest_hash" in script.text
    assert "TRADINGVIEW_PAIRED_EXPORT_ATTESTATION" in script.text
    assert "/prediction-market/summary" in script.text
    assert "/prediction-market/paper/demo-readiness" in script.text
    assert "/prediction-market/paper/demo-progress" in script.text
    assert "/prediction-market/paper/demo-runbook" in script.text
    assert "/prediction-market/paper/demo-ledger?limit=20" in script.text
    assert "/prediction-market/paper/demo-campaigns?limit=10" in script.text
    assert "/prediction-market/paper/demo-batches?limit=10" in script.text
    assert "/prediction-market/paper/demo-run" in script.text
    assert "/prediction-market/paper/demo-batch-preflight" in script.text
    assert "/prediction-market/paper/demo-batch-run" in script.text
    assert "/prediction-market/paper/demo-mkt-db-campaign-readiness" in script.text
    assert "/prediction-market/paper/demo-mkt-db-campaign-manifest" in script.text
    assert "/prediction-market/paper/demo-mkt-db-campaign-preflight" in script.text
    assert "/prediction-market/paper/demo-mkt-db-campaign-run" in script.text
    assert "/prediction-market/contracts" in script.text
    assert "/prediction-market/contracts/template.csv" in script.text
    assert "/prediction-market/contracts/preflight-csv" in script.text
    assert "/prediction-market/contracts/import-csv" in script.text
    assert "/prediction-market/contracts/mkt-donor-runbook" in script.text
    assert "renderPredictionContractMktDonorRunbook" in script.text
    assert "buildPredictionContractSnapshotMktDonorRunbook" in script.text
    assert "/prediction-market/contracts/mkt-donor-bootstrap" in script.text
    assert "renderPredictionContractMktDonorBootstrap" in script.text
    assert "bootstrapPredictionContractSnapshotMktDonor" in script.text
    assert "/prediction-market/contracts/mkt-donor-launch-preflight" in script.text
    assert "renderPredictionContractMktDonorLaunchPreflight" in script.text
    assert "preflightPredictionContractSnapshotMktDonorLaunch" in script.text
    assert "/prediction-market/contracts/mkt-donor-collection-status" in script.text
    assert "command_hints" in script.text
    assert "currentPredictionMktDonorLaunchCommand" in script.text
    assert "copyPredictionMktDonorLaunchCommand" in script.text
    assert "prediction-mkt-donor-copy-launch-command-button" in script.text
    assert "prediction-mkt-donor-launch-boundary" in script.text
    assert "launch_scope" in script.text
    assert "backtest_depth_ready" in script.text
    assert "evidence_boundary" in script.text
    assert "formatAgeSeconds" in script.text
    assert "db_age_seconds" in script.text
    assert "latest_log_age_seconds" in script.text
    assert "freshness_window_seconds" in script.text
    assert "recommended_recheck_after_seconds" in script.text
    assert "recommended_recheck_at" in script.text
    assert "evidence_tier" in script.text
    assert "aurex_use_scope" in script.text
    assert "SPARSE" in script.text
    assert "data_evidence_tier" in script.text
    assert "data_use_scope" in script.text
    assert "data_backtest_depth_ready" in script.text
    assert "prediction-mkt-donor-collection-quality" in script.text
    assert "prediction-mkt-donor-collection-freshness" in script.text
    assert "prediction-mkt-donor-launch-health" in script.text
    assert "FRESHNESS_DB_RECENT" in script.text
    assert "COLLECTION_INACTIVE" in script.text
    assert "LAUNCH_HEALTH_INACTIVE" in script.text
    assert "QUALITY_BACKTEST_CANDIDATE" in script.text
    assert "backtest_depth_progress_pct" in script.text
    assert "renderPredictionContractMktDonorCollectionStatus" in script.text
    assert "renderPredictionMktDonorCollectionQualityRows" in script.text
    assert "renderPredictionMktDonorLaunchHealthRows" in script.text
    assert "checkPredictionContractSnapshotMktDonorCollectionStatus" in script.text
    assert "/prediction-market/contracts/mkt-runtime-safety" in script.text
    assert "renderPredictionContractMktRuntimeSafety" in script.text
    assert "checkPredictionContractSnapshotMktRuntimeSafety" in script.text
    assert "hydratePredictionMktRuntimePaths" in script.text
    assert "settings_auto_discovered" in script.text
    assert "/prediction-market/contracts/mkt-donor-readiness" in script.text
    assert "/prediction-market/contracts/discover-mkt-dbs" in script.text
    assert "renderPredictionContractMktDonorReadiness" in script.text
    assert "checkPredictionContractSnapshotMktDonorReadiness" in script.text
    assert "renderPredictionContractMktDbDiscovery" in script.text
    assert "selectPredictionContractSnapshotMktDbCandidate" in script.text
    assert "data-mkt-db-candidate-index" in script.text
    assert "renderPredictionMktDbCampaignManifest" in script.text
    assert "buildPredictionDemoMktDbCampaignManifest" in script.text
    assert "/prediction-market/contracts/preflight-mkt-db" in script.text
    assert "/prediction-market/contracts/mkt-db-readiness" in script.text
    assert "/prediction-market/contracts/mkt-db-inventory" in script.text
    assert "renderPredictionContractMktDbInventory" in script.text
    assert "inspectPredictionContractSnapshotMktDbInventory" in script.text
    assert "/prediction-market/contracts/import-mkt-db" in script.text
    assert "/prediction-market/paper/order-intents" in script.text
    assert "prediction-action" in script.text
    assert "prediction-max-quote-age-seconds" in script.text
    assert "max_quote_age_seconds" in script.text
    assert "prediction-max-spread" in script.text
    assert "max_spread" in script.text
    assert "prediction-max-latency-ms" in script.text
    assert "max_latency_ms" in script.text
    assert "prediction-max-slippage" in script.text
    assert "max_slippage" in script.text
    assert "/cancel" in script.text
    assert "/prediction-market/paper/orders" in script.text
    assert "/prediction-market/paper/positions" in script.text
    assert "/prediction-market/paper/stale-orders/cancel" in script.text
    assert "/prediction-market/paper/reconciliation/run" in script.text
    assert "/prediction-market/evidence?limit=12" in script.text
    assert "/paper/evidence/imports?limit=10" in script.text
    assert "/paper/evidence/collection-status" in script.text
    assert "/paper/evidence/preflight-csv" in script.text
    assert "/paper/evidence/import-csv" in script.text
    assert "/paper/evidence/template.csv" in script.text
    assert "/signals/contract?strategy=${encodedStrategy}" in script.text
    assert "/signals/tradingview-runbook?strategy=${encodedStrategy}" in script.text
    assert "/signals/tradingview-alert-setup?strategy=${encodedStrategy}" in script.text
    assert "/signals/tradingview-verification?strategy=${encodedStrategy}" in script.text
    assert "refreshQualifiedStrategyResources" in script.text
    assert "qualifiedStrategyContext" in script.text
    assert "trend_pullback_v1" not in script.text
    assert "trend_pullback_v1" not in dashboard.text
    assert "/signals/preflight/tradingview" in script.text
    assert "evidence-collection-status" in script.text
    assert "evidence-collection-drift" in dashboard.text
    assert "paper_evidence_freshness_reasons" in script.text
    assert "scoped_imported_count" in script.text
    assert "out_of_scope_imported_count" in script.text
    assert "out_of_scope_import_summary" in script.text
    assert "paperEvidenceCollectionImportSummary" in script.text
    assert "scope_status" in script.text
    assert "scoped_importable_count" in script.text
    assert "out_of_scope_importable_count" in script.text
    assert "evidence-preflight-summary" in script.text
    assert "evidence-analysis-window" in script.text
    assert "renderPaperEvidenceAnalysis" in script.text
    assert "evidence-imports-body" in script.text
    assert "firstImportedEvidenceHash" in script.text
    assert "import_hash" in script.text
    assert "imported_external_trade_hashes" in script.text
    assert "deployment-statement-reconciliation" in script.text
    assert "deployment-statement-csv-summary" in script.text
    assert "renderBrokerStatementPreflight" in script.text
    assert "reconciliation_status" in script.text
    assert "reconciliation_discrepancies" in script.text
    assert "renderBacktestPreflight" in script.text
    assert "renderBacktestSetup" in script.text
    assert "loadBacktestStrategySetup" in script.text
    assert "hydrateBacktestStrategySetup" in script.text
    assert "registerBacktestProtocol" in script.text
    assert "loadBacktestRunManifest" in script.text
    assert "loadBacktestTradingViewRunPackage" in script.text
    assert "copyBacktestPineSource" in script.text
    assert "copyBacktestTradingViewSetup" in script.text
    assert "/tradingview-run-package`" in script.text
    assert "backtestProtocolPayload" in script.text
    assert "renderBacktestProtocols" in script.text
    assert "backtestPrimarySymbol" in script.text
    assert "renderBacktestReports" in script.text
    assert "renderSignalContract" in script.text
    assert "renderSignalRunbook" in script.text
    assert "renderSignalAlertSetup" in script.text
    assert "loadTradingViewAlertSetup" in script.text
    assert "hydrateSignalAlertPayload" in script.text
    assert "renderSignalVerification" in script.text
    assert "renderSignalPreflight" in script.text
    assert "signalPreflightWebhookSummary" in script.text
    assert "TradingView alert setup loaded." in script.text
    assert "signalPreflightDuplicateSummary" in script.text
    assert "preflightTradingViewSignal" in script.text
    assert "hydrateSignalPreflightPayload" in script.text
    assert "signalContractFingerprint" in script.text
    assert "signalProvenanceSummary" in script.text
    assert "signalDeliverySummary" in script.text
    assert "signal_backtest_provenance_gate" in script.text
    assert "MATCHED / v" in script.text
    assert "PAYLOAD / v" in script.text
    assert "backtest-walk-forward-summary" in script.text
    assert "backtest-parameter-summary" in script.text
    assert "backtestParameterEvidenceSummary" in script.text
    assert "strategy_parameter_evidence" in script.text
    assert "accepted_backtest_strategy_parameters_missing" in script.text
    assert "walk_forward?.passed_windows" in script.text
    assert "verified WF" in script.text
    assert "backtestReportPayload" in script.text
    assert "source contract passed" in script.text
    assert "source contract blocked" in script.text
    assert "PROMOTION BLOCKED" in script.text
    assert 'walk_forward_windows: jsonInputValue("backtest-walk-forward-windows")' in (
        script.text
    )
    assert "diagnostic slices" in script.text
    assert "renderPredictionMarkets" in script.text
    assert "researchGateSignificanceSummary" in script.text
    assert "renderPredictionDemoReadiness" in script.text
    assert "prediction-demo-readiness-current" in script.text
    assert "prediction-demo-readiness-progress" in script.text
    assert "current_check" in script.text
    assert "completed_check_count" in script.text
    assert "renderPredictionDemoProgress" in script.text
    assert "prediction-demo-progress-current" in script.text
    assert "prediction-demo-progress-completion" in script.text
    assert "renderPredictionDemoRunbook" in script.text
    assert "prediction-demo-runbook-body" in dashboard.text
    assert "prediction-demo-runbook-current" in script.text
    assert "prediction-demo-runbook-upstream" in script.text
    assert "upstream_research_runbook" in script.text
    assert "renderPredictionDemoLedger" in script.text
    assert "missing_evidence_kinds" in script.text
    assert "recorded_evidence_kinds" in script.text
    assert "PAPER_DEMO_LEDGER_BLOCKED" in script.text
    assert "renderPredictionDemoCampaignAudit" in script.text
    assert "renderPredictionDemoBatchAudit" in script.text
    assert "current_result_drifted_records" in script.text
    assert "renderPredictionDemoBatch" in script.text
    assert "predictionDemoBatches" in script.text
    assert "prediction-demo-batch-audit-state" in script.text
    assert "prediction-demo-batch-hash" in script.text
    assert "reviewed_preflight_hash" in script.text
    assert "state.predictionDemoBatchPreflight?.preflight_hash" in script.text
    assert "delete batchPayload.reviewed_preflight_hash" in script.text
    assert "prediction-demo-unique-contracts" in script.text
    assert "prediction-demo-contract-concentration" in script.text
    assert "prediction-demo-provenance" in script.text
    assert "prediction-demo-ledger-clean" in script.text
    assert "raw_closed_records" in script.text
    assert "prediction-mkt-db-campaign-projected-evidence" in script.text
    assert "prediction-mkt-db-campaign-projected-coverage" in script.text
    assert "campaignProjectionEvidenceSummary" in script.text
    assert "campaignProjectionCoverageSummary" in script.text
    assert "projected_progress_pct" in script.text
    assert "remaining_closed_records" in script.text
    assert "reviewed_manifest_hash" in script.text
    assert "state.predictionDemoMktDbCampaignManifest?.manifest_hash" in script.text
    assert "raw_closed_records" in script.text
    assert "current_check_key" in script.text
    assert "remaining_records" in script.text
    assert "formatPercentNumber" in script.text
    assert "renderPredictionContractCsvPreflight" in script.text
    assert "renderPredictionContractMktDbDiscovery" in script.text
    assert "renderPredictionContractMktDbPreflight" in script.text
    assert "renderPredictionContractMktDbReadiness" in script.text
    assert "renderPredictionMktDbCampaignReadiness" in script.text
    assert "renderPredictionMktDbCampaign" in script.text
    assert "renderPredictionPaperIntentGate" in script.text
    assert "predictionReadinessForStrategy" in script.text
    assert "runPredictionDemo" in script.text
    assert "preflightPredictionDemoBatch" in script.text
    assert "runPredictionDemoBatch" in script.text
    assert "predictionExecutionRiskLimitsPayload" in script.text
    assert "predictionContractSnapshotCsvPayload" in script.text
    assert "predictionContractSnapshotMktDbPayload" in script.text
    assert "predictionDemoMktDbCampaignPayload" in script.text
    assert "projected_fee_net_realized_pl" in script.text
    assert "first_failed_check" in script.text
    assert "opposite_side_projection" in script.text
    assert "side_sensitivity_warning" in script.text
    assert "campaign_evidence" in script.text
    assert "donor_evidence_tier" in script.text
    assert "donor_use_scope" in script.text
    assert "acknowledge_side_sensitivity" in script.text
    assert "side_selection_rationale" in script.text
    assert "loadPredictionContractSnapshotTemplate" in script.text
    assert "Prediction paper intent rejected; evidence recorded." in script.text
    assert "renderResearchCandidates" in script.text
    assert "renderResearchReadinessQueue" in script.text
    assert "research-readiness-body" in dashboard.text
    assert "renderResearchGate" in script.text
    assert "regime_diagnostics" in script.text
    assert "variant_diagnostics" in script.text
    assert "renderResearchEvidence" in script.text
    assert "refreshResearchEvidence" in script.text
    assert "latestResearchBacktest" in script.text
    assert "registerResearchCandidate" in script.text
    assert "recordResearchObservation" in script.text
    assert "checkMktResearchIntakeReadiness" in script.text
    assert "buildMktResearchIntakeRunbook" in script.text
    assert "renderMktResearchRunbook" in script.text
    assert "research-mkt-runbook-current-step" in script.text
    assert "research-mkt-runbook-current-command" in script.text
    assert "research-mkt-runbook-progress" in script.text
    assert "progress_pct" in script.text
    assert "current_step" in script.text
    assert "current_command" in script.text
    assert "research-mkt-runbook-body" in dashboard.text
    assert "research-mkt-runbook-button" in dashboard.text
    assert "RUNBOOK_READY_FOR_RESEARCH_IMPORT" in script.text
    assert "renderMktResearchIntakeReadiness" in script.text
    assert "RESEARCH_INTAKE_READY_FOR_RESEARCH_IMPORT" in script.text
    assert "RESEARCH_DB_RECENT" in script.text
    assert "RESEARCH_DB_STALE" in script.text
    assert "research-mkt-log-activity" in script.text
    assert "collection_activity_status" in script.text
    assert "RESEARCH_COLLECTION_STARTING" in script.text
    assert "research-mkt-collection-health" in script.text
    assert "collection_health" in script.text
    assert "COLLECTION_HEALTH_SAMPLE_READY" in script.text
    assert "research-mkt-intake-start-command" in script.text
    assert "command_hints" in script.text
    assert "acknowledge_research_only_import" in script.text
    assert "research-mkt-ack-research-only" in script.text
    assert "source_quality_status" in script.text
    assert "preflightMktResearchCandidates" in script.text
    assert "importMktResearchCandidates" in script.text
    assert "renderMktResearchImport" in script.text
    assert "IMPORT_SPARSE_RESOLVED_SAMPLE" in script.text
    assert "SOURCE_BACKTEST_CANDIDATE" in script.text
    assert "read-only preflight" in script.text
    assert "runResearchCandidateBacktest" in script.text
    assert "maximum_oos_drawdown" in script.text
    assert "minimum_regime_trades" in script.text
    assert "maximum_tested_variants" in script.text
    assert "predictionSnapshotPayload" in script.text
    assert "createPredictionOrderIntent" in script.text
    assert "submitPredictionOrder" in script.text
    assert "cancelPredictionOrderIntent" in script.text
    assert "settlePredictionPosition" in script.text
    assert "runPredictionReconciliation" in script.text
    assert 'csv_format: "auto"' in script.text
    assert "Backtest setup loaded." in script.text
    assert 'inputValue("backtest-csv-timezone")' in script.text
    assert 'nullableInputValue("backtest-source-reference")' in script.text
    assert "backtest-reports-body" in dashboard.text
    assert "deployment-profit-milestone" in script.text
    assert "deployment-evidence-review" in script.text
    assert "deployment-evidence-review-next" in dashboard.text
    assert "deployment-evidence-review-blockers" in dashboard.text
    assert "deployment-activation-audit" in script.text
    assert "deployment-live-adapter" in script.text
    assert "deployment-mkt-credentials" in script.text
    assert "deployment-approval-packet" in script.text
    assert "deployment-backtest-evidence" in script.text
    assert "deployment-paper-freshness" in script.text
    assert "deployment-paper-scope" in script.text
    assert "deployment-paper-coverage" in script.text
    assert "deployment-journal-coverage" in script.text
    assert "deployment-prediction-demo" in script.text
    assert "deployment-prediction-demo-selected" in dashboard.text
    assert "deployment-prediction-demo-campaign-drift" in dashboard.text
    assert "deployment-prediction-demo-batch-drift" in dashboard.text
    assert "deployment-prediction-demo-next" in dashboard.text
    assert "deployment-statement-freshness" in script.text
    assert "deployment-broker-diligence" in script.text
    assert "approvalPacketPayload" in script.text
    assert "recordLiveApproval" in script.text
    assert "runProfitMilestone" in script.text
    assert "runStrategyEvidenceReview" in script.text
    assert "strategyEvidenceReviewSummary" in script.text
    assert "strategyEvidenceReviewNextAction" in script.text
    assert "strategyEvidenceReviewBlockers" in script.text
    assert "next_actions" in script.text
    assert "strategy_evidence_review_clear" in script.text
    assert "activationAuditSummary" in script.text
    assert "attempt.next_actions" in script.text
    assert "liveExecutionAdapterSummary" in script.text
    assert "paperEvidenceFreshness" in script.text
    assert "statementFreshness" in script.text
    assert "predictionDemoCampaignSummary" in script.text
    assert "predictionDemoCampaignSelectedSummary" in script.text
    assert "predictionDemoCampaignDriftSummary" in script.text
    assert "predictionDemoBatchDriftSummary" in script.text
    assert "predictionDemoCampaignNextAction" in script.text
    assert "strategy_campaign_audit_records" in script.text
    assert "strategy_batch_current_result_drifted_records" in script.text
    assert "mktDonorCredentialBoundarySummary" in script.text
    assert "approval-credentials-stored" in dashboard.text
    assert "approval-record-approved" in dashboard.text
    assert "preview-line-main" in dashboard.text
    assert "renderMarketPreview" in script.text
    assert "renderCommandEvidencePath" in script.text
    assert "command-evidence-path-state" in dashboard.text
    assert "command-evidence-current" in script.text
    assert "currentCoreBacktestProtocol" in script.text
    assert "refreshCoreRunManifest" in script.text
    assert "strategyFactoryReadiness" in script.text
    assert '"/system/readiness"' in script.text
    assert "Factory contract" in script.text
    assert "Accepted backtest" in script.text
    assert "navigator.clipboard" in script.text
    assert "/live/deployment/activation-attempt" in script.text
    assert "/system/events" in script.text
    assert ".metrics-grid" in styles.text
    assert ".market-preview" in styles.text
    assert "backdrop-filter" in styles.text
    assert ".strategy-table" in styles.text
    assert ".compact-list" in styles.text
    assert ".evidence-form" in styles.text


def test_dashboard_uses_single_view_navigation_and_dedicated_notifications(
    client: TestClient,
) -> None:
    dashboard = client.get("/dashboard").text
    script = client.get("/dashboard/assets/app.js").text
    styles = client.get("/dashboard/assets/styles.css").text

    ids = re.findall(r'\bid="([^"]+)"', dashboard)
    assert len(ids) == len(set(ids))
    assert 'href="#command"' not in dashboard
    assert 'data-view-target="command"' in dashboard
    assert 'data-view-target="prediction"' in dashboard
    assert 'data-view-target="operator"' in dashboard
    assert 'data-view-target="deployment"' in dashboard
    assert 'data-dashboard-view="command"' in dashboard
    assert 'data-dashboard-view="prediction"' in dashboard
    assert 'data-dashboard-view="operator"' in dashboard
    assert 'data-dashboard-view="events"' in dashboard
    assert dashboard.count('id="evidence"') == 1
    assert 'id="notification-region"' in dashboard
    assert dashboard.index('class="nav-list"') < dashboard.index('id="health-state"')

    assert "function revealActiveNavItem" in script
    assert 'nav.scrollTo({ left: Math.max(0, centeredLeft), behavior: "auto" })' in script
    assert "function activateView" in script
    assert "function initializeNavigation" in script
    assert "AurexTransport.settleResources" in script
    assert "function showNotification" in script
    assert "function runUiAction" in script
    run_ui_action = script[
        script.index("async function runUiAction"):
        script.index("function bindAction")
    ]
    assert "const pendingUiActions = new WeakSet();" in script
    assert "pendingUiActions.has(button)" in run_ui_action
    assert "pendingUiActions.delete(button)" in run_ui_action
    assert "button.disabled =" not in run_ui_action
    assert "Preflight blocked" in script
    assert "function renderOperatorProfile" in script
    assert "function operatorProfilePayload" in script
    assert "function preflightOperatorProfile" in script
    assert "function downloadOperatorProfileInput" in script
    assert "Select a verified Binance Vision dataset" in script
    assert "function formatWarmupPair" in script
    assert "undefined/undefined HTF" not in script
    assert 'text("health-state", error.message)' not in script
    assert '.dashboard-view:not(.is-active)' in styles
    assert ".operator-profile-form-grid" in styles
    assert ".operator-profile-gates" in styles
    assert '["sandboxProfileStatus", "/sandbox-profile/status"]' in script
    assert '["binanceTestnetStatus", "/broker/binance-testnet/status"]' in script
    assert ".notification-region" in styles
    assert "bottom: 18px" in styles
    assert ".notification-region" in styles
    assert ".nav-item.is-active" in styles
    assert "pointer-events: none" in styles
