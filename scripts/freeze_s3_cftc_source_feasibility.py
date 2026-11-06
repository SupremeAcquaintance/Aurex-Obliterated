from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_positioning_charter import (  # noqa: E402
    S3_NEXT_AUTHORIZATION,
    S3CftcPositioningCharter,
    S3CftcPositioningCharterAudit,
    audit_s3_charter,
    audit_s3_charter_audit,
)
from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3CftcSourceFeasibilityProtocol,
    S3FeasibilityBinding,
    S3MetadataEndpointSpec,
    build_hashed,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s3_cftc_source_feasibility.py")
SCRIPT_PATH = Path("scripts/freeze_s3_cftc_source_feasibility.py")
CHARTER_PATH = Path("data/evidence/s3_cftc_positioning_charter_v1.json")
CHARTER_AUDIT_PATH = Path("data/evidence/s3_cftc_positioning_charter_audit_v1.json")
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v24.json"
)
READINESS_AUDIT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v24.json"
)


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_and_validate_inputs() -> S3CftcPositioningCharter:
    charter = S3CftcPositioningCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    charter_audit = S3CftcPositioningCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        not audit_s3_charter(charter)
        or not audit_s3_charter_audit(charter_audit)
        or charter_audit.charter_evidence_hash != charter.charter_evidence_hash
        or charter.next_authorization != S3_NEXT_AUTHORIZATION
        or charter.cftc_position_values_inspected != ()
        or charter.btc_market_numeric_fields_inspected != ()
        or charter.authorizes_cftc_position_value_access is not False
        or charter.authorizes_market_value_access is not False
        or charter.authorizes_return_testing is not False
        or charter.authorizes_live is not False
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.passed_gate_count != 14
        or readiness.partial_gate_count != 1
        or readiness.failed_gate_count != 0
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    ):
        raise ValueError("S3 feasibility input lineage or authority changed")
    return charter


def bindings() -> tuple[S3FeasibilityBinding, ...]:
    paths = (
        CHARTER_PATH,
        CHARTER_AUDIT_PATH,
        READINESS_RESULT_PATH,
        READINESS_AUDIT_PATH,
    )
    return tuple(
        S3FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def endpoints() -> tuple[S3MetadataEndpointSpec, ...]:
    specs = (
        S3MetadataEndpointSpec(
            endpoint_id="COT_FAQ",
            url="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            required_text_tokens=tuple(
                sorted(
                    (
                        "Is there a list of historical release dates?",
                        "There is not a list of historical release dates",
                        "only available release dates are for the 13 months",
                    )
                )
            ),
        ),
        S3MetadataEndpointSpec(
            endpoint_id="HISTORICAL_SPECIAL_ANNOUNCEMENTS",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "HistoricalSpecialAnnouncements/index.htm"
            ),
            required_text_tokens=tuple(
                sorted(
                    (
                        "Historical Special Announcements",
                        "New Publish Date",
                        "Original Publish Date",
                    )
                )
            ),
        ),
        S3MetadataEndpointSpec(
            endpoint_id="HISTORICAL_VIEWABLE_INDEX",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "HistoricalViewable/index.htm"
            ),
            required_text_tokens=tuple(
                sorted(
                    (
                        "Dates indicate the report date and not the release date",
                        "Historical Viewable",
                    )
                )
            ),
        ),
    )
    return tuple(sorted(specs, key=lambda item: item.endpoint_id))


def build_protocol(*, frozen_at: datetime) -> S3CftcSourceFeasibilityProtocol:
    charter = load_and_validate_inputs()
    return build_hashed(
        S3CftcSourceFeasibilityProtocol,
        "protocol_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "charter_evidence_hash": charter.charter_evidence_hash,
            "source_bindings": bindings(),
            "metadata_endpoints": endpoints(),
            "development_release_coverage_start": datetime(2022, 1, 1, tzinfo=UTC),
            "development_release_coverage_end_exclusive": datetime(
                2025, 1, 1, tzinfo=UTC
            ),
            "limitations": tuple(
                sorted(
                    (
                        "A successful HTTP request does not prove point-in-time coverage.",
                        "Actual publication timing must be proven for every development report.",
                        "Historical report dates and scheduled dates are not release timestamps.",
                        "Metadata may prove the source infeasible and retire S3 before values.",
                        "No CFTC target position row or value may be parsed by this protocol.",
                        "No BTC price, parameter, return, candidate, signal, or order "
                        "is authorized.",
                        "Published study outcomes cannot substitute for source reconstruction.",
                        "Reuse rights and zero-dollar access must be explicit rather than assumed.",
                    )
                )
            ),
        },
    )


def write_atomic(path: Path, protocol: S3CftcSourceFeasibilityProtocol) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 feasibility protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S3CftcSourceFeasibilityProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S3 feasibility protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check S3 CFTC feasibility.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.check:
        stored = S3CftcSourceFeasibilityProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S3 feasibility protocol differs from reconstruction")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S3 feasibility protocol: {args.output}")
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "network=0 cftc_values=0 market_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
