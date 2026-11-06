from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessGateResult,
    StrategyFactoryReadinessProtocol,
    StrategyFactoryReadinessResult,
    StrategyFactorySourceEvidence,
    audit_readiness_protocol,
    build_readiness_result,
    contamination_artifact_valid,
    file_sha256,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/aurex_strategy_factory_readiness_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/aurex_strategy_factory_readiness_baseline_result_v1.json"
)


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def source_evidence(*paths: str) -> list[StrategyFactorySourceEvidence]:
    evidence = []
    for raw_path in sorted(set(paths)):
        path = PROJECT_ROOT / raw_path
        if not path.is_file():
            raise ValueError(f"Readiness source evidence is missing: {raw_path}")
        evidence.append(
            StrategyFactorySourceEvidence(
                path=relative_path(path),
                file_sha256=file_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    return evidence


def source_text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def has_all(text: str, *tokens: str) -> bool:
    return all(token in text for token in tokens)


def gate_result(
    gate_id: str,
    status: str,
    summary: str,
    *,
    checks: list[str],
    blockers: list[str],
    paths: list[str],
) -> StrategyFactoryReadinessGateResult:
    return StrategyFactoryReadinessGateResult(
        gate_id=gate_id,
        status=status,
        summary=summary,
        checks=checks,
        blockers=blockers,
        source_evidence=source_evidence(*paths),
    )


def canonical_program_truth() -> StrategyFactoryReadinessGateResult:
    control = source_text("docs/10_PROJECT_CONTROL.md")
    outcome = source_text("docs/31_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME.md")
    required = (
        "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED",
        "NONE_DEVELOPMENT_OUTCOME_FAILED",
        "Real net profit",
        "1068",
    )
    passed = has_all(control, *required) and has_all(outcome, *required)
    return gate_result(
        "CANONICAL_PROGRAM_TRUTH",
        "PASS" if passed else "FAIL",
        "Canonical control and terminal Jam evidence state the same strategy and profit truth.",
        checks=[
            "Canonical checkpoint records the terminal Jam decision.",
            "No next authorization exists for the failed Jam lineage.",
            "Real net profit remains zero and the verified suite count is recorded.",
        ],
        blockers=[] if passed else ["canonical_program_truth_inconsistent"],
        paths=[
            "docs/10_PROJECT_CONTROL.md",
            "docs/31_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME.md",
        ],
    )


def immutable_evidence_integrity() -> StrategyFactoryReadinessGateResult:
    outcome_path = PROJECT_ROOT / (
        "data/evidence/jam_successor_development_outcome_result_v1.json"
    )
    audit_path = PROJECT_ROOT / (
        "data/evidence/jam_successor_development_outcome_audit_v1.json"
    )
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    passed = (
        outcome.get("decision") == "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED"
        and audit.get("result_evidence_hash") == outcome.get("result_evidence_hash")
        and audit.get("sealed_market_periods_opened") == 0
        and audit.get("strategy_executions") == 0
    )
    return gate_result(
        "IMMUTABLE_EVIDENCE_INTEGRITY",
        "PASS" if passed else "FAIL",
        "Canonical outcome and independent audit hashes reconcile with zero sealed access.",
        checks=[
            "Result and audit evidence hashes reconcile.",
            "Audit records zero sealed-period access and zero strategy execution.",
            "Shared evidence models enforce schema and hash validation.",
        ],
        blockers=[] if passed else ["canonical_evidence_integrity_failed"],
        paths=[
            "data/evidence/jam_successor_development_outcome_audit_v1.json",
            "data/evidence/jam_successor_development_outcome_result_v1.json",
            "src/aurex/backtest_engine/universe.py",
            "tests/unit/test_jam_successor_development_outcome.py",
        ],
    )


def market_data_lineage() -> StrategyFactoryReadinessGateResult:
    vision = source_text("src/aurex/backtest_engine/binance_vision.py")
    datasets = source_text("src/aurex/backtest_engine/datasets.py")
    validation = source_text("src/aurex/backtest_engine/validation_bundle.py")
    native = source_text("src/aurex/signal_gateway/native_bars.py")
    public = source_text("src/aurex/signal_gateway/native_market_data.py")
    passed = (
        has_all(vision, "file_sha256", "parse_checksum_file")
        and has_all(datasets, "source_artifact_bundle_hash", "gap_count")
        and has_all(validation, "contamination_ledger_hash", "bundle_evidence_hash")
        and has_all(
            native, "candle_not_closed", "latest_closed_bar_is_stale",
            "previous_history_changed", "cursor_requires_exactly_one_next_bar",
            "source_origin_verified: bool = False", "execution_authority: bool = False",
        )
        and has_all(
            public, "https://data-api.binance.vision", "verify_public_evidence",
            "public_server_clock_skew", "public_kline_time_or_continuity_invalid",
            "public_response_hash_mismatch", "public_normalized_history_mismatch",
            "forward_qualifying: Literal[False] = False",
        )
    )
    return gate_result(
        "MARKET_DATA_LINEAGE_AND_QUALITY",
        "PASS" if passed else "FAIL",
        "Dataset identity, continuity, quarantine, and validation-bundle controls exist.",
        checks=[
            "Binance Vision files are checksum-bound.",
            "Dataset records preserve source identity and gap diagnostics.",
            "Validation bundles bind contamination and evidence hashes.",
            "Native preflight bounds closed-bar freshness and fixed-seed continuity; "
            "it neither verifies origin nor persists processing or grants execution authority.",
            "A bounded public-only candle client retains response bytes and checks clock, "
            "closed intervals, pagination and normalized hashes. Offline reconstruction "
            "is not source authentication, online exit supervision or forward qualification.",
        ],
        blockers=[] if passed else ["market_data_lineage_controls_missing"],
        paths=[
            "src/aurex/backtest_engine/binance_vision.py",
            "src/aurex/backtest_engine/datasets.py",
            "src/aurex/backtest_engine/validation_bundle.py",
            "src/aurex/signal_gateway/native_bars.py",
            "src/aurex/signal_gateway/native_market_data.py",
            "scripts/check_native_public_data.py",
            "tests/unit/test_native_market_data.py",
            "docs/49_NATIVE_PUBLIC_DATA.md",
            "tests/unit/test_native_closed_bars.py",
            "tests/integration/test_native_closed_bar_intake.py",
            "tests/integration/test_backtest_datasets.py",
            "tests/unit/test_validation_bundle.py",
        ],
    )


def contamination_and_partitions() -> StrategyFactoryReadinessGateResult:
    ledger = PROJECT_ROOT / "data/evidence/strategy_contamination_ledger_v2.json"
    module = source_text("src/aurex/backtest_engine/contamination.py")
    passed = contamination_artifact_valid(ledger) and has_all(
        module,
        "HOLDOUT_OPENED_RETIRED",
        "contamination_reasons",
        "ledger_evidence_hash",
    )
    return gate_result(
        "CONTAMINATION_AND_PARTITION_ISOLATION",
        "PASS" if passed else "FAIL",
        "The append-only contamination ledger is hash-valid and partition conflicts fail closed.",
        checks=[
            "Canonical v2 contamination ledger validates.",
            "Retired holdout use is represented explicitly.",
            "Conflict checks cover strategy family, symbol, timeframe, and period.",
        ],
        blockers=[] if passed else ["contamination_or_partition_control_failed"],
        paths=[
            "data/evidence/strategy_contamination_ledger_v2.json",
            "src/aurex/backtest_engine/contamination.py",
            "tests/unit/test_strategy_contamination.py",
        ],
    )


def preregistration() -> StrategyFactoryReadinessGateResult:
    protocols = source_text("src/aurex/backtest_engine/candidate_protocols.py")
    service = source_text("src/aurex/backtest_engine/service.py")
    passed = has_all(
        protocols,
        "register_candidate_protocol_durably",
        "candidate_protocol_registration_blocked_outcome_already_recorded",
        "candidate_protocol_commit_temporal_binding_failed",
    ) and has_all(service, "build_backtest_protocol_hash", "protocol_snapshot")
    return gate_result(
        "PREREGISTRATION_BEFORE_OUTCOMES",
        "PASS" if passed else "FAIL",
        "Candidate protocols commit durably and reject prior-outcome contamination.",
        checks=[
            "Protocol registration precedes candidate outcomes.",
            "Persisted protocol hashes are re-read after commit.",
            "Protocol consumption is immutable and single-use.",
        ],
        blockers=[] if passed else ["durable_preregistration_control_missing"],
        paths=[
            "src/aurex/backtest_engine/candidate_protocols.py",
            "src/aurex/backtest_engine/service.py",
            "tests/integration/test_candidate_preregistration.py",
        ],
    )


def deterministic_replay() -> StrategyFactoryReadinessGateResult:
    replay = source_text("src/aurex/backtest_engine/reference_replay.py")
    parity = source_text("src/aurex/backtest_engine/parity.py")
    service = source_text("src/aurex/backtest_engine/service.py")
    passed = (
        "evidence_hash" in replay
        and "compare" in parity
        and has_all(service, "build_trade_evidence_hash", "walk_forward_evidence_hash")
    )
    return gate_result(
        "DETERMINISTIC_REPLAY_AND_RECONCILIATION",
        "PASS" if passed else "FAIL",
        "Replay, trade, walk-forward, and parity evidence are deterministic and reconcilable.",
        checks=[
            "Reference replay persists deterministic evidence identity.",
            "Trade and walk-forward evidence hashes are recomputed during eligibility.",
            "Parity reports mismatches rather than silently accepting aggregates.",
        ],
        blockers=[] if passed else ["deterministic_replay_control_missing"],
        paths=[
            "src/aurex/backtest_engine/parity.py",
            "src/aurex/backtest_engine/reference_replay.py",
            "src/aurex/backtest_engine/service.py",
            "tests/integration/test_backtest_lab.py",
            "tests/integration/test_reference_replay.py",
        ],
    )


def universal_robustness() -> StrategyFactoryReadinessGateResult:
    schemas = source_text("src/aurex/backtest_engine/schemas.py")
    service = source_text("src/aurex/backtest_engine/service.py")
    required = (
        "require_cost_stress",
        "require_uncertainty_bound",
        "require_multiple_testing_control",
        "require_holdout_decision",
    )
    present = [token for token in required if token in schemas and token in service]
    passed = len(present) == len(required)
    blockers = [] if passed else [
        "generic_acceptance_does_not_require_cost_stress",
        "generic_acceptance_does_not_require_uncertainty_bound",
        "generic_acceptance_does_not_require_multiple_testing_control",
        "generic_acceptance_has_no_separate_holdout_decision_gate",
    ]
    return gate_result(
        "UNIVERSAL_COST_STRESS_AND_INFERENCE",
        "PASS" if passed else "PARTIAL",
        (
            "Candidate-specific research engines contain strong controls, but the "
            "reusable acceptance schema does not mandate them for every candidate."
        ),
        checks=[
            "Generic acceptance already requires OOS, walk-forward, regime, "
            "drawdown, and concentration evidence.",
            f"Universal robustness requirement anchors present: {len(present)}/{len(required)}.",
            "Lineage-specific engines demonstrate cost-stress capability but do "
            "not create a universal contract.",
        ],
        blockers=blockers,
        paths=[
            "src/aurex/backtest_engine/research_execution_spec.py",
            "src/aurex/backtest_engine/schemas.py",
            "src/aurex/backtest_engine/service.py",
            "tests/integration/test_backtest_lab.py",
        ],
    )


def candidate_lifecycle() -> StrategyFactoryReadinessGateResult:
    registry = source_text("src/aurex/strategy_engine/registry.py")
    service = source_text("src/aurex/strategy_engine/service.py")
    passed = has_all(
        registry,
        "lifecycle_status",
        "RETIRED",
        "QUARANTINED",
    ) and has_all(service, "strategy_lifecycle_allows_enable")
    blockers = [] if passed else [
        "strategy_registry_has_no_machine_readable_lifecycle_status",
        "retired_or_quarantined_strategy_enable_is_not_directly_blocked",
    ]
    return gate_result(
        "CANDIDATE_LIFECYCLE_AND_RETIREMENT",
        "PASS" if passed else "PARTIAL",
        (
            "Retirement is strongly preserved in research evidence, but the shared "
            "strategy registry does not yet enforce lifecycle state."
        ),
        checks=[
            "Registered strategies default disabled.",
            "Paper promotion independently requires accepted evidence.",
            "Machine-readable retired/quarantined lifecycle enforcement is checked.",
        ],
        blockers=blockers,
        paths=[
            "src/aurex/backtest_engine/contamination.py",
            "src/aurex/strategy_engine/registry.py",
            "src/aurex/strategy_engine/service.py",
            "tests/integration/test_strategy_portfolio.py",
        ],
    )


def fail_closed_paper_promotion() -> StrategyFactoryReadinessGateResult:
    eligibility = source_text("src/aurex/backtest_engine/eligibility.py")
    risk = source_text("src/aurex/risk_engine/service.py")
    passed = has_all(
        eligibility,
        "persisted_trade_evidence_reasons",
        "persisted_backtest_protocol_reasons",
        "walk_forward_reasons",
    ) and has_all(
        risk,
        "paper_backtest_eligibility",
        "signal_backtest_provenance_gate",
        "Strategy",
    )
    return gate_result(
        "FAIL_CLOSED_PAPER_PROMOTION",
        "PASS" if passed else "FAIL",
        "Paper risk approval requires accepted, intact, scope-matched backtest "
        "and signal evidence.",
        checks=[
            "Strategy enabled state is insufficient by itself.",
            "Persisted trades, protocol identity, OOS, regime, and walk-forward "
            "evidence are re-audited.",
            "Signal version and settings fingerprint must match accepted evidence.",
        ],
        blockers=[] if passed else ["paper_promotion_not_fail_closed"],
        paths=[
            "src/aurex/backtest_engine/eligibility.py",
            "src/aurex/risk_engine/service.py",
            "tests/integration/test_backtest_source_eligibility.py",
            "tests/integration/test_risk_engine.py",
        ],
    )


def authenticated_signal_delivery() -> StrategyFactoryReadinessGateResult:
    delivery = source_text("src/aurex/signal_gateway/tradingview_delivery.py")
    route = source_text("src/aurex/api/routes/webhooks.py")
    proof = source_text("src/aurex/signal_gateway/tradingview_external_proof.py")
    artifact = PROJECT_ROOT / "data/evidence/tradingview_external_delivery_proof_v1.json"
    code_ready = has_all(
        delivery, "has_forwarding_headers", "tradingview_source_network_snapshot"
    ) and has_all(route, "body_sha256", "SHARED_SECRET_VALIDATED") and has_all(
        proof,
        "RISK_REJECTED",
        "paper_order_id",
        "broker_order_ids",
    )
    passed = code_ready and artifact.is_file()
    return gate_result(
        "AUTHENTICATED_SIGNAL_DELIVERY",
        "PASS" if passed else "PARTIAL",
        "Webhook delivery controls are code-ready, but no genuine external proof artifact exists.",
        checks=[
            "Exact request body and sender policy are evidence-bound.",
            "Idempotent normalization and side-effect checks exist.",
            f"Genuine external proof artifact present: {artifact.is_file()}.",
        ],
        blockers=[] if passed else ["genuine_tradingview_external_proof_missing"],
        paths=[
            "src/aurex/signal_gateway/tradingview_delivery.py",
            "src/aurex/signal_gateway/tradingview_external_proof.py",
            "src/aurex/api/routes/webhooks.py",
            "src/aurex/api/webhook_ingress.py",
            "scripts/run_tradingview_ingress.py",
            "tests/integration/test_webhook_ingress.py",
            "tests/integration/test_signal_verification.py",
            "tests/unit/test_tradingview_ingress_launcher.py",
            "tests/unit/test_tradingview_ingress_startup.py",
            "tests/unit/test_tradingview_delivery.py",
            "tests/unit/test_tradingview_external_proof.py",
        ],
    )


def evidence_grade_paper_execution() -> StrategyFactoryReadinessGateResult:
    paper = source_text("src/aurex/execution_engine/paper.py")
    intake = source_text("src/aurex/signal_gateway/service.py")
    processing = source_text("src/aurex/signal_gateway/native_processing.py")
    continuation = source_text("src/aurex/signal_gateway/native_continuation.py")
    recovery = source_text("src/aurex/signal_gateway/native_recovery.py")
    source_binding = source_text("src/aurex/signal_gateway/native_source.py")
    observation = source_text("src/aurex/signal_gateway/native_observation.py")
    exits = source_text("src/aurex/signal_gateway/native_exits.py")
    jam_features = source_text("src/aurex/signal_gateway/native_jam_features.py")
    jam_history = source_text("src/aurex/signal_gateway/native_jam_history.py")
    jam_decisions = source_text("src/aurex/signal_gateway/native_jam_decisions.py")
    jam_runtime = source_text("src/aurex/signal_gateway/native_jam_runtime.py")
    supervision = source_text("src/aurex/signal_gateway/native_supervision.py")
    passed = has_all(
        paper,
        "DETERMINISTIC_PAPER_FILL_MODEL",
        "cost_floor_enforced",
        "paper_execution_evidence_hash",
        "execute_approved_signal",
    ) and has_all(
        intake, "ingest_native", "delivery_context=None", "live_execution_adapter"
    ) and has_all(
        processing, "BEGIN IMMEDIATE", "commit=False", "processing_receipt_integrity_failed",
        "processing_signal_link_invalid", "processed_bar_request_changed",
        "retained_history_seed_missing", "retained_history_checkpoint_mismatch", "process_next",
        "continuation_reconstruction_mismatch", "iter_validated_chain", "receipt_evidence",
        "recover_next", "RECOVERY_NO_ENTRY", "open_position_requires_exit_only_recovery",
        "recovery_entry_chain_mismatch",
        "process_sourced", "processed_bar_source_changed", "processing_source_binding_dropped",
        "SOURCE_OBSERVED_NO_ENTRY", "native_bar_processing_v4",
        "native_bar_processing_v5", "processing_observation_admission_dropped",
        "processed_bar_observation_changed", "observation_expected_head_changed",
        "native_bar_processing_v6", "ONLINE_EXIT_NO_ENTRY",
        "online_exit_fill_model_transition_invalid",
        "native_bar_processing_v7", "jam_runtime_expected_head_changed",
    ) and has_all(
        continuation, "initialize_continuation", "advance_indicators", "continuation_frame",
        "require_replay_arithmetic", "native_bar_chain_v1", "visible_higher_fast",
    ) and has_all(
        recovery, "native_ohlc_recovery_v1", "forward_qualifying", "manage_recovery",
        "verify_recovery", "PARTIAL_ENTRY_STOP_BOUND", "recovery_close_ledger_mismatch",
    ) and has_all(
        source_binding, "source_acquisition_hash_mismatch", "verify_public_evidence",
        "source_seed_checkpoint_mismatch", "source_received_after_processing",
        "retained_evidence_reconstruction", "forward_qualifying: Literal[False] = False",
        "NativeObservationAdmission", "observation_acquisition_timing_invalid",
    ) and has_all(
        observation, "NativePublicObserver", "PublicCandleClient().acquire",
        "WAITING_FOR_CLOSE", "observation_window_missed_requires_reconciliation",
        "open_position_requires_online_exit_monitor", "observation_requires_live_disabled",
        "def manage_exits", "online_exit_requires_initialized_stream",
    ) and has_all(
        exits, "NativeOnlineExitEvidence", "manage_online_exit", "verify_online_exit",
        "source_acquisition_sha256", "online_exit_requires_fresh_closed_bar",
    ) and has_all(
        jam_features, "initialize_jam_features", "advance_jam_features", "jam_feature_frame",
        "require_replay_arithmetic", "jam_requires_one_next_bar", "jam_higher_visibility_invalid",
        "execution_authority: Literal[False] = False",
    ) and has_all(
        jam_history, "NativeJamHistoryReader", "bind_jam_feature_parameters",
        "jam_history_settings_fingerprint_mismatch", "verified_native_history",
        "iter_validated_chain", "jam_history_expected_head_changed", "?mode=ro",
        "PRAGMA query_only=ON", "forward_qualifying: Literal[False] = False",
    ) and has_all(
        jam_decisions, "initialize_jam_setup", "evaluate_jam_setup", "resolve_jam_entry",
        "initialize_jam_position", "plan_jam_exit", "jam_entry_resolution_required",
        "jam_exit_resolution_required", "jam_decision_context_changed",
        "jam_management_requires_boundary_fill", "execution_authority: Literal[False] = False",
    ) and has_all(
        jam_runtime, "JamChainAudit", "process_jam_decision", "management_plan",
        "verify_management", "jam_runtime_close_ledger_mismatch",
        "jam_runtime_account_changed_without_receipt",
        "jam_runtime_resolution_reconstruction_mismatch",
        "jam_runtime_requires_live_disabled", "forward_qualifying: Literal[False] = False",
    ) and has_all(
        supervision, "run_native_supervisor", "exclusive_runner", "audit_run_journal",
        "resource_check", "retry_delay", "supervisor_wall_clock_changed",
        "supervisor_requires_live_disabled", "PUBLIC_DATA_FAILURE",
    )
    return gate_result(
        "EVIDENCE_GRADE_PAPER_EXECUTION",
        "PASS" if passed else "FAIL",
        "Paper orders and trades preserve explicit fill, fee, slippage, and position evidence.",
        checks=[
            "Only risk-approved signals can execute.",
            "Modeled execution enforces a conservative cost floor.",
            "Imported paper evidence preserves source hashes and reconciliation context.",
            "Local native intake uses the same services without external delivery receipts.",
            "The bounded SQLite native processor commits outcomes, cursors and paper effects "
            "together; it is not a continuous feed or source attestation.",
            "The initial seed is retained atomically and reconstructed prefixes are verified; "
            "versioned continuation preserves replay arithmetic beyond the fixed prefix window.",
            "Continuation state is reconstructed from retained inputs with paged receipt reads; "
            "audit time and storage still grow, and stale entries remain rejected.",
            "Exit-only recovery accepts contiguous closed candles without entry authority; "
            "touched positions are quarantined from qualifying forward-paper evidence.",
            "Versioned source-bound observations retain raw acquisition evidence atomically "
            "with seed/checkpoint/recovery effects; imports cannot grant origin "
            "or entry authority.",
            "The one-shot observer owns public acquisition, checks its planned stream head "
            "at commit and persists observation admission; default observation cannot enter. "
            "The opt-in Jam coordinator is separately risk-gated; neither mode schedules "
            "itself or grants forward qualification.",
            "Explicit acquired-candle exit management commits costed FLAT/HELD/CLOSED outcomes "
            "with v6 receipts, preserves recovery quarantine and cannot qualify OHLC-model fills.",
            "Bounded Jam features are reconstructed from audited retained history under an "
            "enforced read-only SQLite snapshot, bound to full settings and the exact head; "
            "this is not a decision, candidate approval, or a supervised runner.",
            "Pure Jam proposals preserve pending confirmation, explicit entry resolution, "
            "old-bracket-first exits and next-bar stop updates. They do not write receipts, "
            "approve risk, prove fills or qualify a candidate.",
            "The v7 Jam coordinator reconstructs setup/management state, records real risk "
            "decisions and modeled paper effects in the receipt transaction, verifies costs "
            "and equity, and preserves conservative partial-bar and exit-phase semantics. "
            "Its OHLC fills remain nonqualifying; Jam retirement and live locks remain intact.",
            "A bounded cooperative local supervisor owns polling, resource and clock stops, "
            "OS-held process locking, rate-limit waits and durable run journals. Separate "
            "read-only reconciliation checks retained receipt references. These controls "
            "do not prove continuous real-feed operation or deployment acceptance.",
        ],
        blockers=[] if passed else ["paper_execution_evidence_controls_missing"],
        paths=[
            "src/aurex/execution_engine/paper.py",
            "src/aurex/execution_engine/costs.py",
            "src/aurex/signal_gateway/schemas.py",
            "src/aurex/signal_gateway/service.py",
            "src/aurex/signal_gateway/native_processing.py",
            "src/aurex/signal_gateway/native_continuation.py",
            "src/aurex/signal_gateway/native_recovery.py",
            "src/aurex/signal_gateway/native_source.py",
            "src/aurex/signal_gateway/native_observation.py",
            "src/aurex/signal_gateway/native_exits.py",
            "src/aurex/signal_gateway/native_jam_features.py",
            "src/aurex/signal_gateway/native_jam_history.py",
            "src/aurex/signal_gateway/native_jam_decisions.py",
            "src/aurex/signal_gateway/native_jam_runtime.py",
            "src/aurex/signal_gateway/native_supervision.py",
            "scripts/run_native_supervisor.py",
            "scripts/audit_native_supervisor.py",
            "src/aurex/live_deployment/service.py",
            "src/aurex/db/models.py",
            "infra/alembic/versions/20260930_0030_native_bar_outcomes.py",
            "infra/alembic/versions/20261004_0031_native_history_seed.py",
            "tests/integration/test_native_bar_processing.py",
            "tests/integration/test_native_bar_migration.py",
            "tests/integration/test_native_retained_history.py",
            "tests/integration/test_native_continuation_processing.py",
            "tests/integration/test_native_recovery.py",
            "tests/integration/test_native_source_binding.py",
            "tests/integration/test_native_observation.py",
            "tests/integration/test_native_online_exits.py",
            "tests/unit/test_native_continuation.py",
            "tests/unit/test_native_jam_features.py",
            "tests/integration/test_native_jam_history.py",
            "tests/integration/test_native_jam_decisions.py",
            "tests/integration/test_native_jam_runtime.py",
            "tests/integration/test_native_supervision.py",
            "tests/integration/test_native_seed_migration.py",
            "tests/integration/test_native_signal_intake.py",
            "tests/integration/test_paper_evidence_import.py",
            "tests/integration/test_tradingview_webhook.py",
        ],
    )


def risk_limits() -> StrategyFactoryReadinessGateResult:
    risk = source_text("src/aurex/risk_engine/service.py")
    native = source_text("src/aurex/risk_engine/native_spot.py")
    passed = has_all(
        risk,
        "kill_switch_enabled",
        "Daily loss limit reached",
        "Weekly loss limit reached",
        "Signal is stale",
        "Signal timestamp is in the future",
        "Max open positions reached",
        "validate_native_paper_decision",
    ) and has_all(
        native, "modeled_stop_loss", "available_quote", "strategy_remaining", "account_remaining"
    )
    return gate_result(
        "RISK_LIMITS_AND_KILL_SWITCH",
        "PASS" if passed else "FAIL",
        "Risk approval fails closed on kill, stale, loss, exposure, regime, and evidence gates.",
        checks=[
            "Position size derives from equity, stop distance, and bounded risk.",
            "Daily, weekly, per-strategy, and account exposure limits exist.",
            "Kill switch, stale signals and future timestamps reject before paper execution.",
            "Native BTCUSDT spot sizes against costed stop, cash and cumulative loss budgets.",
            "Native execution rechecks approval; modeled stop risk does not guarantee gap losses.",
        ],
        blockers=[] if passed else ["risk_or_kill_switch_control_missing"],
        paths=[
            "src/aurex/risk_engine/calculations.py",
            "src/aurex/risk_engine/service.py",
            "src/aurex/risk_engine/native_spot.py",
            "src/aurex/execution_engine/costs.py",
            "tests/integration/test_native_spot_risk.py",
            "tests/unit/test_native_spot_sizing.py",
            "tests/integration/test_risk_engine.py",
            "tests/unit/test_risk_calculations.py",
        ],
    )


def exchange_sandbox() -> StrategyFactoryReadinessGateResult:
    audit_path = (
        PROJECT_ROOT
        / "data/evidence/binance_spot_testnet_restart_soak_audit_20260731T125305Z.json"
    )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    passed = (
        audit.get("decision") == "BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED"
        and audit.get("order_submission_count") in (None, 1)
        and audit.get("live_authority") in (None, False)
    )
    return gate_result(
        "EXCHANGE_SANDBOX_QUALIFICATION",
        "PASS" if passed else "FAIL",
        "Binance Spot Testnet Phase 2A-D is independently qualified without live authority.",
        checks=[
            "Authenticated order lifecycle and fill/fee/balance reconciliation passed.",
            "User stream, REST gap recovery, restart idempotency, kill-stop, and soak passed.",
            "Qualified adapter evidence grants no strategy or production authority.",
        ],
        blockers=[] if passed else ["exchange_sandbox_qualification_missing"],
        paths=[
            "data/evidence/binance_spot_testnet_fill_fee_audit_20260731T091050Z.json",
            "data/evidence/binance_spot_testnet_restart_soak_audit_20260731T125305Z.json",
            "data/evidence/binance_spot_testnet_user_stream_audit_20260731T100023Z.json",
            "src/aurex/broker_engine/binance_spot_testnet.py",
            "tests/unit/test_binance_testnet_restart_soak.py",
        ],
    )


def live_isolation() -> StrategyFactoryReadinessGateResult:
    settings = source_text("src/aurex/config/settings.py")
    adapter = source_text("src/aurex/live_deployment/execution_adapter.py")
    service = source_text("src/aurex/live_deployment/service.py")
    passed = (
        has_all(
            settings,
            "live_trading_enabled: bool = False",
            'live_execution_adapter: str = "disabled"',
        )
        and has_all(
            adapter,
            "DisabledLiveExecutionAdapter",
            "supports_live_order_submission = False",
        )
        and has_all(
            service,
            "activation_allowed=False",
            "plan.live_trading_enabled = False",
        )
    )
    return gate_result(
        "LIVE_EXECUTION_ISOLATION",
        "PASS" if passed else "FAIL",
        "Live order submission is intentionally unimplemented and activation "
        "attempts remain audit-only.",
        checks=[
            "Platform live flag defaults false.",
            "Configured adapter defaults disabled and cannot submit orders.",
            "Activation service records blockers while forcing plan live state false.",
        ],
        blockers=[] if passed else ["live_execution_isolation_failed"],
        paths=[
            "src/aurex/config/settings.py",
            "src/aurex/live_deployment/execution_adapter.py",
            "src/aurex/live_deployment/service.py",
            "tests/integration/test_live_micro_deployment.py",
        ],
    )


def operator_visibility() -> StrategyFactoryReadinessGateResult:
    route = source_text("src/aurex/api/routes/system.py")
    app = source_text("apps/frontend/app.js")
    html = source_text("apps/frontend/index.html")
    backup = source_text("src/aurex/db/backup.py")
    rehearsal = source_text("scripts/rehearse_native_database_upgrade.py")
    private_runtime = source_text("src/aurex/api/private_runtime.py")
    private_launcher = source_text("scripts/run_private_operator.py")
    native_lifecycle = source_text("src/aurex/signal_gateway/native_lifecycle.py")
    recovery_bundle = source_text("src/aurex/db/recovery_bundle.py")
    recovery_environment = source_text("src/aurex/db/recovery_environment.py")
    recovery_controls = has_all(
        recovery_bundle, "FULL_EVIDENCE", "OPERATIONAL_WITHOUT_RAW_ARCHIVES",
        "omitted_archives", "recovery_source_tree_changed_during_copy",
        "recovery_relative_path_invalid", "verify_restored", "CONFIG_FIELDS",
    ) and has_all(
        recovery_environment, "verify_wheelhouse", "--no-index", "--require-hashes",
        "system_site_packages=False", "recovery_installed_versions_mismatch",
    )
    private_controls = has_all(
        private_runtime, "CURRENT_SCHEMA_REQUIRED", "REQUIRED_COLUMNS_MISSING",
        "LIVE_EXECUTION_MUST_BE_DISABLED", "SAME_ORIGIN_REQUIRED", "RUNTIME_INSTANCE_MISMATCH",
        "DATABASE_FILE_REPLACED", '"?mode=rw"', '"/system/private-runtime"',
    ) and has_all(
        private_launcher, 'host="127.0.0.1"', "proxy_headers=False", "server.should_exit = True",
        "exist_ok=False", "os.fsync", '"STOPPED" if clean else "BLOCKED"',
    )
    backup_controls = has_all(
        backup, "create_backup", "verify_backup", "restore_copy", "source.backup",
        "backup_snapshot_copy_mismatch", "backup_logical_snapshot_mismatch", "table_hashes",
    ) and has_all(
        rehearsal, "upgrade_rehearsal_existing_table_changed", "rollback.db",
        '"operator_database_upgraded": False', '"runtime_resume_verified": False',
    )
    native_controls = has_all(
        native_lifecycle, "ManagedNativeLaunch", "NativeControlRequest",
        "managed_source_changed", "managed_database_identity_changed", "MAX_MANAGED_RUNS",
        "self._child.poll()", "audit_run_journal", "managed_request_id_conflict",
        "managed_strategy_not_eligible", "control_journal_failed", "SHUTDOWN_SECONDS",
    ) and has_all(
        private_runtime, '"/system/native-supervisor/start"', '"/system/native-supervisor/stop"',
        "controller.close", "native_shutdown_clean",
    ) and has_all(app, "refreshNativeSupervisor", "controlNativeSupervisor", "nativeReadSequence")
    has_endpoint = "/readiness" in route and "StrategyFactoryReadiness" in route
    has_ui = "strategyFactoryReadiness" in app and "platform-readiness" in html
    authority_aware = has_all(
        app,
        "qualifiedStrategyContext",
        "refreshQualifiedStrategyResources",
        "paper_operation_ready",
        '"No qualified strategy"',
        '"Research only"',
        '"LOCKED / no execution authority"',
    )
    stale_core = "trend_pullback_v1" in app or "trend_pullback_v1" in html
    passed = (
        has_endpoint and has_ui and authority_aware and not stale_core
        and backup_controls and private_controls and recovery_controls and native_controls
    )
    blockers = [] if passed else [
        "canonical_strategy_factory_readiness_api_missing",
        "operator_ui_does_not_render_platform_readiness_artifact",
        "command_evidence_path_contains_stale_hard_coded_strategy_guidance",
        "database_backup_and_copy_rehearsal_controls_missing",
        "private_runtime_startup_boundary_or_lifecycle_controls_missing",
        "application_recovery_coverage_or_dependency_integrity_controls_missing",
        "owned_native_supervisor_lifecycle_controls_missing",
    ]
    return gate_result(
        "OPERATOR_READINESS_VISIBILITY",
        "PASS" if passed else "PARTIAL",
        "Operator strategy context is derived from canonical readiness and lifecycle authority.",
        checks=[
            f"Canonical readiness API present: {has_endpoint}.",
            f"Canonical readiness UI present: {has_ui}.",
            f"Authority-aware strategy context present: {authority_aware}.",
            f"Stale hard-coded core strategy guidance present: {stale_core}.",
            f"Verified-backup and copy-only upgrade/rollback tooling present: {backup_controls}.",
            f"Private startup and lifecycle controls present: {private_controls}.",
            f"Application recovery and offline dependency controls present: {recovery_controls}.",
            f"Owned bounded native-supervisor controls present: {native_controls}.",
            "Process ownership and terminal journals do not establish fresh feed or qualification; "
            "test-only waiting children do not acquire market data.",
            "Operational bundles list omitted raw archives; environment recreation, "
            "application startup and full-history recovery require separate demonstrations.",
            "Restored-copy service rehearsal is distinct from full operator cutover, "
            "supervisor/feed operation and strategy qualification.",
            "Database snapshots exclude external files and do not prove service cutover, "
            "complete application restoration or production acceptance.",
        ],
        blockers=blockers,
        paths=[
            "apps/frontend/app.js",
            "apps/frontend/dashboard-transport.js",
            "apps/frontend/styles.css",
            "tests/frontend/dashboard-transport.test.cjs",
            "scripts/rehearse_operator_dashboard.cjs",
            "apps/frontend/index.html",
            "src/aurex/api/routes/system.py",
            "src/aurex/backtest_engine/s5_measurement_readiness.py",
            "tests/integration/test_dashboard.py",
            "tests/integration/test_system_readiness.py",
            "tests/unit/test_s5_measurement_readiness.py",
            "src/aurex/db/backup.py",
            "scripts/manage_database_backup.py",
            "scripts/rehearse_native_database_upgrade.py",
            "tests/integration/test_database_backup.py",
            "src/aurex/api/private_runtime.py",
            "scripts/run_private_operator.py",
            "scripts/rehearse_private_operator.py",
            "tests/integration/test_private_runtime.py",
            "src/aurex/signal_gateway/native_lifecycle.py",
            "tests/integration/test_native_lifecycle.py",
            "tests/fixtures/native_managed_wait_child.py",
            "tests/fixtures/private_native_wait_service.py",
            "src/aurex/db/recovery_bundle.py",
            "src/aurex/db/recovery_environment.py",
            "scripts/manage_recovery_bundle.py",
            "scripts/manage_recovery_environment.py",
            "scripts/rehearse_recovered_application.py",
            "tests/integration/test_recovery_bundle.py",
            "tests/unit/test_recovery_environment.py",
            "docs/19_LOCAL_OPERATOR_RUNBOOK.md",
        ],
    )


def runner_contract_hash() -> str:
    path = PROJECT_ROOT / "scripts/run_strategy_factory_readiness.py"
    return universe_evidence_hash(
        {"runner_file": relative_path(path), "runner_file_sha256": file_sha256(path)}
    )


def build_result(
    *,
    protocol: StrategyFactoryReadinessProtocol,
    evaluated_at: datetime,
) -> StrategyFactoryReadinessResult:
    gates = [
        canonical_program_truth(),
        immutable_evidence_integrity(),
        market_data_lineage(),
        contamination_and_partitions(),
        preregistration(),
        deterministic_replay(),
        universal_robustness(),
        candidate_lifecycle(),
        fail_closed_paper_promotion(),
        authenticated_signal_delivery(),
        evidence_grade_paper_execution(),
        risk_limits(),
        exchange_sandbox(),
        live_isolation(),
        operator_visibility(),
    ]
    external_proof = (
        PROJECT_ROOT
        / "data/evidence/tradingview_external_delivery_proof_v1.json"
    ).is_file()
    return build_readiness_result(
        protocol=protocol,
        evaluated_at=evaluated_at,
        runner_contract_hash=runner_contract_hash(),
        gate_results=gates,
        external_tradingview_proof_present=external_proof,
        limitations=[
            "A passing capability gate does not establish a profitable strategy.",
            "No candidate is historically, paper, sandbox-strategy, production, or live eligible.",
            "Operational TradingView delivery remains unproven without a genuine "
            "external artifact.",
            "Production account, legal, tax, and real-capital facts remain unresolved.",
            "The baseline audit inspects source and existing evidence only.",
        ],
    )


def write_result(path: Path, result: StrategyFactoryReadinessResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if StrategyFactoryReadinessResult.model_validate_json(serialized) != result:
        raise ValueError("Strategy-factory readiness result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional readiness result exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(args) -> StrategyFactoryReadinessResult:
    if args.output.exists():
        raise ValueError(f"Strategy-factory readiness result exists: {args.output}")
    protocol = StrategyFactoryReadinessProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    if not audit_readiness_protocol(protocol):
        raise ValueError("Strategy-factory readiness protocol failed audit")
    result = build_result(
        protocol=protocol,
        evaluated_at=args.evaluated_at or datetime.now(UTC),
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"gates={result.passed_gate_count}/{len(result.gate_results)} "
        f"partial={result.partial_gate_count} fail={result.failed_gate_count} "
        f"research_ready={result.strategy_research_ready} "
        f"decision={result.decision} strategies=0 orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Score Aurex strategy-factory readiness without market outcomes."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evaluated-at", type=datetime.fromisoformat)
    return parser.parse_args()


def main() -> int:
    try:
        run(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
