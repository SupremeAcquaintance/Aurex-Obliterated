from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s4_spot_bitcoin_etp_charter import (  # noqa: E402
    S4_NEXT_AUTHORIZATION,
    S4SpotBitcoinEtpCharter,
    S4SpotBitcoinEtpCharterAudit,
    audit_s4_charter,
    audit_s4_charter_audit,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_source_feasibility import (  # noqa: E402
    S4EtpSourceFeasibilityProtocol,
    S4FeasibilityBinding,
    S4MetadataEndpointSpec,
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

DEFAULT_OUTPUT = Path("data/evidence/s4_etp_source_feasibility_protocol_v1.json")
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s4_spot_bitcoin_etp_source_feasibility.py"
)
SCRIPT_PATH = Path("scripts/freeze_s4_etp_source_feasibility.py")
CHARTER_PATH = Path("data/evidence/s4_spot_bitcoin_etp_charter_v1.json")
CHARTER_AUDIT_PATH = Path(
    "data/evidence/s4_spot_bitcoin_etp_charter_audit_v1.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v26.json"
)
READINESS_AUDIT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v26.json"
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


def load_and_validate_inputs() -> S4SpotBitcoinEtpCharter:
    charter = S4SpotBitcoinEtpCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    charter_audit = S4SpotBitcoinEtpCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        not audit_s4_charter(charter)
        or not audit_s4_charter_audit(charter_audit)
        or charter_audit.charter_evidence_hash != charter.charter_evidence_hash
        or charter.next_authorization != S4_NEXT_AUTHORIZATION
        or charter.etp_time_series_rows_parsed != 0
        or charter.etp_numeric_payloads_acquired != 0
        or charter.btc_market_numeric_fields_inspected != ()
        or charter.authorizes_etp_numeric_value_access is not False
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
        raise ValueError("S4 feasibility input lineage or authority changed")
    return charter


def bindings() -> tuple[S4FeasibilityBinding, ...]:
    paths = (
        CHARTER_PATH,
        CHARTER_AUDIT_PATH,
        READINESS_RESULT_PATH,
        READINESS_AUDIT_PATH,
    )
    return tuple(
        S4FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def endpoints() -> tuple[S4MetadataEndpointSpec, ...]:
    specs = (
        S4MetadataEndpointSpec(
            endpoint_id="SEC_API_DOCUMENTATION",
            url=(
                "https://www.sec.gov/search-filings/"
                "edgar-application-programming-interfaces"
            ),
            response_kind="TEXT_DOCUMENTATION",
            required_markers=tuple(
                sorted(
                    (
                        "data.sec.gov/submissions/",
                        "do not require any authentication or API keys",
                        "metadata such as current name",
                    )
                )
            ),
            maximum_response_bytes=2_000_000,
            permits_cik_ticker_exchange_values=False,
        ),
        S4MetadataEndpointSpec(
            endpoint_id="SEC_EDGAR_ACCESS_DOCUMENTATION",
            url=(
                "https://www.sec.gov/search-filings/edgar-search-assistance/"
                "accessing-edgar-data"
            ),
            response_kind="TEXT_DOCUMENTATION",
            required_markers=tuple(
                sorted(
                    (
                        "company_tickers_exchange.json",
                        "date filed",
                        "do not guarantee accuracy or scope",
                        "index.json",
                    )
                )
            ),
            maximum_response_bytes=2_000_000,
            permits_cik_ticker_exchange_values=False,
        ),
        S4MetadataEndpointSpec(
            endpoint_id="SEC_FUND_TICKER_CATALOG",
            url="https://www.sec.gov/files/company_tickers_mf.json",
            response_kind="JSON_IDENTITY_CATALOG",
            required_markers=("cik", "ticker"),
            permitted_json_keys=("cik", "class", "series", "ticker"),
            maximum_response_bytes=25_000_000,
            permits_cik_ticker_exchange_values=True,
        ),
        S4MetadataEndpointSpec(
            endpoint_id="SEC_PUBLIC_REUSE_POLICY",
            url="https://www.sec.gov/about/privacy-information",
            response_kind="TEXT_DOCUMENTATION",
            required_markers=tuple(
                sorted(
                    (
                        "copied or further distributed",
                        "public information",
                        "SEC as the source",
                    )
                )
            ),
            maximum_response_bytes=2_000_000,
            permits_cik_ticker_exchange_values=False,
        ),
        S4MetadataEndpointSpec(
            endpoint_id="SEC_TICKER_EXCHANGE_CATALOG",
            url="https://www.sec.gov/files/company_tickers_exchange.json",
            response_kind="JSON_IDENTITY_CATALOG",
            required_markers=("cik", "exchange", "ticker"),
            permitted_json_keys=("cik", "exchange", "name", "ticker"),
            maximum_response_bytes=25_000_000,
            permits_cik_ticker_exchange_values=True,
        ),
    )
    return tuple(sorted(specs, key=lambda item: item.endpoint_id))


def build_protocol(*, frozen_at: datetime) -> S4EtpSourceFeasibilityProtocol:
    charter = load_and_validate_inputs()
    return build_hashed(
        S4EtpSourceFeasibilityProtocol,
        "protocol_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "charter_evidence_hash": charter.charter_evidence_hash,
            "source_bindings": bindings(),
            "static_metadata_endpoints": endpoints(),
            "limitations": tuple(
                sorted(
                    (
                        "A complete current ticker catalog does not prove complete "
                        "historical universe coverage.",
                        "A filing acceptance timestamp does not prove an issuer data "
                        "publication timestamp.",
                        "Current issuer pages and response bodies are forbidden because "
                        "they can expose values.",
                        "EDGAR identity metadata cannot substitute for daily issuer "
                        "source history.",
                        "Failure to prove one fund's history or timing retires S4 before values.",
                        "Issuer website fields do not prove an official daily data "
                        "endpoint or archive.",
                        "Numeric values incidentally exposed in pre-freeze search context "
                        "are outcome-aware and nonqualifying.",
                        "Only SEC documentation, identity catalogs, and submissions "
                        "metadata are permitted.",
                        "SEC states that ticker association catalogs do not guarantee "
                        "accuracy or scope.",
                        "The one run must persist every attempt and partial response "
                        "before returning.",
                        "No ETP value, BTC price, parameter, return, candidate, signal, "
                        "or order is authorized.",
                        "No XBRL facts, filing bodies, issuer page bodies, payloads, or "
                        "market data may be requested.",
                        "Zero-dollar access and reuse rights must be established rather "
                        "than assumed.",
                    )
                )
            ),
        },
    )


def write_atomic(path: Path, protocol: S4EtpSourceFeasibilityProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S4 protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S4 feasibility transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S4EtpSourceFeasibilityProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S4 feasibility protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check S4 ETP feasibility.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S4EtpSourceFeasibilityProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_protocol(frozen_at=stored.frozen_at):
                raise ValueError("Stored S4 feasibility protocol differs from reconstruction")
            print(f"PASS {stored.protocol_evidence_hash}")
            return 0
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_atomic(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "network=0 etp_values=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
