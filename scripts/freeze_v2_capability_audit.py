import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.research_u1_result import (
    U1ResultLedger,
    audit_u1_result_ledger,
)
from aurex.backtest_engine.research_u1_theory_screen import (
    U1MechanismTheoryScreen,
    audit_u1_mechanism_theory_screen,
)
from aurex.backtest_engine.research_v2_capability_audit import (
    V2CapabilityAudit,
    V2CapabilityFinding,
    V2ExternalSurface,
    audit_v2_capability_audit,
    build_v2_capability_audit,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_U1_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json"
)
DEFAULT_U1_SCREEN = (
    DEFAULT_EVIDENCE_ROOT / "u1_mechanism_theory_screen_v1.json"
)
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_CONTAMINATION = (
    DEFAULT_EVIDENCE_ROOT / "strategy_contamination_ledger_v1.json"
)
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "v2_capability_audit_v1.json"
LOCAL_SOURCE_FILES = (
    "My-Krypt-Trader/python/crypto15m_trader.py",
    "My-Krypt-Trader/python/kalshi_api.py",
    "src/aurex/broker_engine/schemas.py",
    "src/aurex/execution_engine/paper.py",
    "src/aurex/execution_engine/schemas.py",
    "src/aurex/live_deployment/execution_adapter.py",
)


def source_hashes(project_root: Path) -> dict[str, str]:
    return {
        path: hashlib.sha256((project_root / path).read_bytes()).hexdigest()
        for path in LOCAL_SOURCE_FILES
    }


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v2_capability_audit.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_capability_audit.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_inputs(args):
    u1_result = U1ResultLedger.model_validate_json(
        args.u1_result.read_text(encoding="utf-8")
    )
    u1_screen = U1MechanismTheoryScreen.model_validate_json(
        args.u1_screen.read_text(encoding="utf-8")
    )
    universe = MarketUniverseManifest.model_validate_json(
        args.universe.read_text(encoding="utf-8")
    )
    contamination = StrategyContaminationLedger.model_validate_json(
        args.contamination.read_text(encoding="utf-8")
    )
    if not audit_u1_result_ledger(u1_result):
        raise ValueError("U1 result failed its hash audit")
    if u1_result.verdict != "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA":
        raise ValueError("V2 audit requires the final U1 stop")
    if not audit_u1_mechanism_theory_screen(u1_screen):
        raise ValueError("U1 theory screen failed its hash audit")
    if audit_market_universe_manifest(universe)["status"] != "PASS":
        raise ValueError("Universe manifest failed its audit")
    if not audit_contamination_ledger(contamination):
        raise ValueError("Contamination ledger failed its audit")
    if (
        u1_result.theory_screen_evidence_hash != u1_screen.screen_evidence_hash
        or u1_result.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
        or u1_result.contamination_ledger_evidence_hash
        != contamination.ledger_evidence_hash
    ):
        raise ValueError("V2 predecessor evidence does not share one lineage")
    return u1_result, u1_screen, universe, contamination


def authoritative_findings() -> list[V2CapabilityFinding]:
    return [
        V2CapabilityFinding(
            capability_id="audited_spot_ohlcv",
            status="READY",
            evidence=(
                "Aurex has checksum-verified canonical Binance Vision spot OHLCV, "
                "continuity audits, immutable bundles, and deterministic transforms."
            ),
        ),
        V2CapabilityFinding(
            capability_id="collateral_and_margin_state_model",
            status="ABSENT",
            evidence=(
                "Current execution and broker schemas have no derivatives collateral, "
                "maintenance margin, leverage bracket, or margin-balance state."
            ),
            blocking_reason=(
                "A carry replay cannot measure insolvency or capital usage without "
                "point-in-time collateral and margin semantics."
            ),
        ),
        V2CapabilityFinding(
            capability_id="derivatives_fee_schedule_history",
            status="ABSENT",
            evidence=(
                "Aurex stores generic modeled commission and slippage but no dated "
                "USD-M futures maker/taker or account-tier fee schedule."
            ),
            blocking_reason=(
                "Current generic costs cannot establish fee-net derivatives carry."
            ),
        ),
        V2CapabilityFinding(
            capability_id="funding_settlement_engine",
            status="ABSENT",
            evidence=(
                "No Aurex ledger applies signed funding cashflows at exchange funding "
                "timestamps to a perpetual position."
            ),
            blocking_reason=(
                "Funding carry cannot be tested without exact payer/receiver and "
                "settlement-notional arithmetic."
            ),
        ),
        V2CapabilityFinding(
            capability_id="historical_perpetual_funding",
            status="ABSENT",
            evidence=(
                "No local evidence bundle contains point-in-time USD-M perpetual "
                "funding rates or settlement timestamps."
            ),
            blocking_reason=(
                "The defining carry cashflow is absent from Aurex evidence."
            ),
        ),
        V2CapabilityFinding(
            capability_id="liquidation_and_adl_model",
            status="ABSENT",
            evidence=(
                "Current paper execution closes spot-style trades but has no mark-price "
                "liquidation, maintenance margin, insurance, or ADL behavior."
            ),
            blocking_reason=(
                "A hedge can fail before convergence if its perpetual leg liquidates "
                "or is auto-deleveraged."
            ),
        ),
        V2CapabilityFinding(
            capability_id="paired_spot_perpetual_execution",
            status="ABSENT",
            evidence=(
                "Current order intent and paper trade models represent one symbol leg "
                "and do not atomically coordinate spot-long and perpetual-short legs."
            ),
            blocking_reason=(
                "Legging, partial-fill, cancel, rollback, and residual-delta risk are "
                "not represented."
            ),
        ),
        V2CapabilityFinding(
            capability_id="perpetual_contract_metadata_history",
            status="ABSENT",
            evidence=(
                "No local artifact records historical USD-M contract status, quantity "
                "filters, price filters, leverage brackets, or funding interval changes."
            ),
            blocking_reason=(
                "Present-day contract metadata cannot be projected backward safely."
            ),
        ),
        V2CapabilityFinding(
            capability_id="perpetual_mark_and_index_history",
            status="ABSENT",
            evidence=(
                "No local bundle contains perpetual mark-price, index-price, or premium "
                "index history aligned with spot data."
            ),
            blocking_reason=(
                "Liquidation, fair basis, and funding context cannot be reconstructed."
            ),
        ),
        V2CapabilityFinding(
            capability_id="point_in_time_spot_perpetual_basis",
            status="ABSENT",
            evidence=(
                "Aurex has spot candles only and no synchronized perpetual execution "
                "price or point-in-time spot-perpetual basis series."
            ),
            blocking_reason=(
                "Entry, exit, convergence, and dislocation P/L are not measurable."
            ),
        ),
        V2CapabilityFinding(
            capability_id="production_derivatives_adapter",
            status="INTENTIONALLY_DISABLED",
            evidence=(
                "The live adapter registry returns only disabled or unregistered "
                "adapters and supports no live order submission."
            ),
            blocking_reason=(
                "No qualified spot or derivatives production execution path exists."
            ),
        ),
        V2CapabilityFinding(
            capability_id="spot_perpetual_reconciliation",
            status="ABSENT",
            evidence=(
                "Generic broker reconciliation exists, but no paired-leg position, "
                "funding, margin, or liquidation reconciliation contract exists."
            ),
            blocking_reason=(
                "Aurex cannot prove hedge quantity, cashflow, collateral, and venue "
                "state agree after each lifecycle event."
            ),
        ),
    ]


def authoritative_external_surfaces() -> list[V2ExternalSurface]:
    return [
        V2ExternalSurface(
            surface_id="binance_official_api_catalog",
            official_source_url="https://developers.binance.com/en/docs/catalog",
            observed_capability=(
                "Official catalog documents spot and USD-M futures market-data, "
                "account, and trading API families."
            ),
        ),
        V2ExternalSurface(
            surface_id="binance_official_derivatives_endpoint_index",
            official_source_url="https://developers.binance.com/en/docs/llms.txt",
            observed_capability=(
                "Official endpoint index lists USD-M funding history, futures klines, "
                "mark-price, index-price, premium-index, basis, exchange metadata, "
                "position risk, ADL risk, and insurance-fund surfaces."
            ),
        ),
        V2ExternalSurface(
            surface_id="binance_public_data_archive",
            official_source_url="https://data.binance.vision/",
            observed_capability=(
                "Official public archive exposes futures dataset directories including "
                "funding, mark-price, index-price, and premium-index families."
            ),
        ),
    ]


def authoritative_audit(
    *,
    frozen_at: datetime,
    u1_result: U1ResultLedger,
    u1_screen: U1MechanismTheoryScreen,
    universe: MarketUniverseManifest,
    contamination: StrategyContaminationLedger,
) -> V2CapabilityAudit:
    findings = authoritative_findings()
    return build_v2_capability_audit(
        frozen_at=frozen_at,
        predecessor_u1_result_evidence_hash=u1_result.ledger_evidence_hash,
        predecessor_u1_theory_screen_evidence_hash=u1_screen.screen_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        contamination_ledger_evidence_hash=contamination.ledger_evidence_hash,
        local_source_sha256=source_hashes(Path(__file__).resolve().parents[1]),
        local_capabilities=findings,
        external_surfaces=authoritative_external_surfaces(),
        ready_capability_count=sum(item.status == "READY" for item in findings),
        blocked_capability_count=sum(item.status != "READY" for item in findings),
        builder_contract_hash=builder_contract_hash(),
    )


def write_audit(path: Path, audit: V2CapabilityAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if V2CapabilityAudit.model_validate_json(serialized) != audit:
        raise ValueError("V2 capability audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2CapabilityAudit:
    if args.output.exists():
        raise ValueError("Frozen V2 capability audit exists; use --check")
    inputs = load_inputs(args)
    audit = authoritative_audit(
        frozen_at=datetime.now(UTC),
        u1_result=inputs[0],
        u1_screen=inputs[1],
        universe=inputs[2],
        contamination=inputs[3],
    )
    write_audit(args.output, audit)
    stored = V2CapabilityAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != audit or not audit_v2_capability_audit(stored):
        raise ValueError("V2 capability audit failed reload verification")
    print(
        f"WROTE {args.output} {stored.audit_evidence_hash} "
        f"ready={stored.ready_capability_count} "
        f"blocked={stored.blocked_capability_count}",
        flush=True,
    )
    return stored


def run_check(args) -> V2CapabilityAudit:
    inputs = load_inputs(args)
    stored = V2CapabilityAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        frozen_at=stored.frozen_at,
        u1_result=inputs[0],
        u1_screen=inputs[1],
        universe=inputs[2],
        contamination=inputs[3],
    )
    if stored != expected or not audit_v2_capability_audit(stored):
        raise ValueError("Stored V2 capability audit differs from rebuild")
    print(
        f"PASS v2_capability_audit={stored.audit_evidence_hash} "
        f"decision={stored.decision}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the no-return V2 capability audit."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--u1-result", type=Path, default=DEFAULT_U1_RESULT)
    parser.add_argument("--u1-screen", type=Path, default=DEFAULT_U1_SCREEN)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument(
        "--contamination",
        type=Path,
        default=DEFAULT_CONTAMINATION,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
