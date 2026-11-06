import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.research_r4_protocol import R4_DECISION_SYMBOLS
from aurex.backtest_engine.research_u1_result import (
    U1ResultLedger,
    audit_u1_result_ledger,
)
from aurex.backtest_engine.research_v2_capability_audit import (
    V2CapabilityAudit,
    audit_v2_capability_audit,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_ALLOWED_CENSUS_FIELDS,
    V2_MONTHS,
    V2ArchiveFamilyContract,
    V2SourceCensusContract,
    V2SourceCensusDecisionRule,
    audit_v2_source_census_contract,
    build_v2_source_census_contract,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CAPABILITY_AUDIT = DEFAULT_EVIDENCE_ROOT / "v2_capability_audit_v1.json"
DEFAULT_U1_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json"
)
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_CONTAMINATION = (
    DEFAULT_EVIDENCE_ROOT / "strategy_contamination_ledger_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_source_census_contract_v1.json"
)
DEFAULT_CENSUS_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_source_census_v1.json"
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v2_source_census_contract.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_source_census_contract.py",
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
    capability = V2CapabilityAudit.model_validate_json(
        args.capability_audit.read_text(encoding="utf-8")
    )
    u1_result = U1ResultLedger.model_validate_json(
        args.u1_result.read_text(encoding="utf-8")
    )
    universe = MarketUniverseManifest.model_validate_json(
        args.universe.read_text(encoding="utf-8")
    )
    contamination = StrategyContaminationLedger.model_validate_json(
        args.contamination.read_text(encoding="utf-8")
    )
    if not audit_v2_capability_audit(capability):
        raise ValueError("V2 capability audit failed its hash audit")
    if not audit_u1_result_ledger(u1_result):
        raise ValueError("U1 result failed its hash audit")
    if audit_market_universe_manifest(universe)["status"] != "PASS":
        raise ValueError("Universe manifest failed its audit")
    if not audit_contamination_ledger(contamination):
        raise ValueError("Contamination ledger failed its audit")
    if (
        capability.predecessor_u1_result_evidence_hash
        != u1_result.ledger_evidence_hash
        or capability.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
        or capability.contamination_ledger_evidence_hash
        != contamination.ledger_evidence_hash
        or capability.decision
        != "BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER"
    ):
        raise ValueError("V2 source contract inputs do not share one lineage")
    return capability, u1_result, universe, contamination


def family(
    *,
    family_id: str,
    market: str,
    data_type: str,
    interval: str,
    template: str,
) -> V2ArchiveFamilyContract:
    return V2ArchiveFamilyContract(
        family_id=family_id,
        market=market,
        data_type=data_type,
        interval=interval,
        archive_url_template=template,
        checksum_url_template=f"{template}.CHECKSUM",
    )


def authoritative_families() -> list[V2ArchiveFamilyContract]:
    root = "https://data.binance.vision/data"
    return [
        family(
            family_id="spot_klines_1m",
            market="SPOT",
            data_type="KLINES",
            interval="1m",
            template=(
                f"{root}/spot/monthly/klines/{{symbol}}/1m/"
                "{symbol}-1m-{month}.zip"
            ),
        ),
        family(
            family_id="um_contract_klines_1m",
            market="USD_M_FUTURES",
            data_type="KLINES",
            interval="1m",
            template=(
                f"{root}/futures/um/monthly/klines/{{symbol}}/1m/"
                "{symbol}-1m-{month}.zip"
            ),
        ),
        family(
            family_id="um_funding_rate_events",
            market="USD_M_FUTURES",
            data_type="FUNDING_RATE_EVENTS",
            interval="EVENT",
            template=(
                f"{root}/futures/um/monthly/fundingRate/{{symbol}}/"
                "{symbol}-fundingRate-{month}.zip"
            ),
        ),
        family(
            family_id="um_index_price_klines_1m",
            market="USD_M_FUTURES",
            data_type="INDEX_PRICE_KLINES",
            interval="1m",
            template=(
                f"{root}/futures/um/monthly/indexPriceKlines/{{symbol}}/1m/"
                "{symbol}-1m-{month}.zip"
            ),
        ),
        family(
            family_id="um_mark_price_klines_1m",
            market="USD_M_FUTURES",
            data_type="MARK_PRICE_KLINES",
            interval="1m",
            template=(
                f"{root}/futures/um/monthly/markPriceKlines/{{symbol}}/1m/"
                "{symbol}-1m-{month}.zip"
            ),
        ),
        family(
            family_id="um_premium_index_klines_1m",
            market="USD_M_FUTURES",
            data_type="PREMIUM_INDEX_KLINES",
            interval="1m",
            template=(
                f"{root}/futures/um/monthly/premiumIndexKlines/{{symbol}}/1m/"
                "{symbol}-1m-{month}.zip"
            ),
        ),
    ]


def authoritative_contract(
    *,
    frozen_at: datetime,
    capability: V2CapabilityAudit,
    u1_result: U1ResultLedger,
    universe: MarketUniverseManifest,
    contamination: StrategyContaminationLedger,
) -> V2SourceCensusContract:
    return build_v2_source_census_contract(
        frozen_at=frozen_at,
        capability_audit_evidence_hash=capability.audit_evidence_hash,
        predecessor_u1_result_evidence_hash=u1_result.ledger_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        contamination_ledger_evidence_hash=contamination.ledger_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        official_documentation_urls=[
            "https://developers.binance.com/en/docs/catalog",
            "https://developers.binance.com/en/docs/llms.txt",
            "https://data.binance.vision/",
        ],
        census_start=datetime(2023, 1, 1, tzinfo=UTC),
        census_end=datetime(2025, 1, 1, tzinfo=UTC),
        months=V2_MONTHS,
        symbols=list(R4_DECISION_SYMBOLS),
        families=authoritative_families(),
        allowed_census_fields=V2_ALLOWED_CENSUS_FIELDS,
        decision_rule=V2SourceCensusDecisionRule(),
    )


def write_contract(path: Path, contract: V2SourceCensusContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if V2SourceCensusContract.model_validate_json(serialized) != contract:
        raise ValueError("V2 source census contract JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2SourceCensusContract:
    if args.output.exists():
        raise ValueError("Frozen V2 source contract exists; use --check")
    if args.census_result.exists():
        raise ValueError("V2 census exists before its source contract")
    inputs = load_inputs(args)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        capability=inputs[0],
        u1_result=inputs[1],
        universe=inputs[2],
        contamination=inputs[3],
    )
    write_contract(args.output, contract)
    stored = V2SourceCensusContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != contract or not audit_v2_source_census_contract(stored):
        raise ValueError("V2 source contract failed reload verification")
    print(
        f"WROTE {args.output} {stored.contract_evidence_hash} "
        f"checks={stored.expected_checksum_checks}",
        flush=True,
    )
    return stored


def run_check(args) -> V2SourceCensusContract:
    inputs = load_inputs(args)
    stored = V2SourceCensusContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=stored.frozen_at,
        capability=inputs[0],
        u1_result=inputs[1],
        universe=inputs[2],
        contamination=inputs[3],
    )
    if stored != expected or not audit_v2_source_census_contract(stored):
        raise ValueError("Stored V2 source contract differs from rebuild")
    print(
        f"PASS v2_source_contract={stored.contract_evidence_hash} "
        f"checks={stored.expected_checksum_checks}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the metadata-only V2 source census contract."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--capability-audit",
        type=Path,
        default=DEFAULT_CAPABILITY_AUDIT,
    )
    parser.add_argument("--u1-result", type=Path, default=DEFAULT_U1_RESULT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument(
        "--contamination",
        type=Path,
        default=DEFAULT_CONTAMINATION,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--census-result",
        type=Path,
        default=DEFAULT_CENSUS_RESULT,
    )
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
