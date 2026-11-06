from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_feasibility import (  # noqa: E402
    S1SourceMetadataProtocol,
    S1SourceRequest,
)
from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1MacroFinancialConditionsCharter,
    audit_s1_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
)
CHARTER_PATH = Path(
    "data/evidence/s1_macro_financial_conditions_charter_v1.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s1_source_feasibility.py")
SCRIPT_PATH = Path("scripts/freeze_s1_source_metadata_feasibility.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def requests() -> tuple[S1SourceRequest, ...]:
    return (
        S1SourceRequest(
            request_id="01-alfred-nfci-series",
            url="https://alfred.stlouisfed.org/series?seid=NFCI",
            expected_final_host="alfred.stlouisfed.org",
            role="ALFRED_SERIES_PAGE",
        ),
        S1SourceRequest(
            request_id="02-nfci-vintage-2020",
            url=(
                "https://fred.stlouisfed.org/graph/fredgraph.csv?"
                "id=NFCI&vintage_date=2020-01-01"
            ),
            expected_final_host="fred.stlouisfed.org",
            role="NO_KEY_VINTAGE_CSV",
        ),
        S1SourceRequest(
            request_id="03-nfci-vintage-2021",
            url=(
                "https://fred.stlouisfed.org/graph/fredgraph.csv?"
                "id=NFCI&vintage_date=2021-01-01"
            ),
            expected_final_host="fred.stlouisfed.org",
            role="NO_KEY_VINTAGE_CSV",
        ),
        S1SourceRequest(
            request_id="04-structured-api-no-key",
            url=(
                "https://api.stlouisfed.org/fred/series/observations?"
                "series_id=NFCI&file_type=json&realtime_start=2020-01-01&"
                "realtime_end=2020-01-01"
            ),
            expected_final_host="api.stlouisfed.org",
            role="STRUCTURED_API_AUTH_CLASSIFICATION",
        ),
    )


def build_protocol(*, frozen_at: datetime) -> S1SourceMetadataProtocol:
    charter = S1MacroFinancialConditionsCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    if not audit_s1_charter(charter):
        raise ValueError("S1 charter failed its evidence hash")
    if charter.next_authorization != (
        "AUTHORIZE_S1_METADATA_ONLY_NFCI_VINTAGE_FEASIBILITY"
    ):
        raise ValueError("S1 charter does not authorize metadata feasibility")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_file_sha256": file_sha256(CHARTER_PATH),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "requests": requests(),
        "feasibility_gates": (
            "EXACTLY_FOUR_HEAD_REQUESTS_AND_ZERO_RESPONSE_BODY_BYTES",
            "ALFRED_NFCI_SERIES_ENDPOINT_REACHABLE",
            "BOTH_NO_KEY_VINTAGE_CSV_ENDPOINTS_REACHABLE",
            "VINTAGE_ENDPOINTS_RETURN_DOWNLOADABLE_CONTENT_TYPES",
            "ALL_FINAL_HOSTS_MATCH_THE_FROZEN_OFFICIAL_HOSTS",
            "STRUCTURED_API_AUTH_REQUIREMENT_CLASSIFIED_WITHOUT_CREDENTIALS",
            "ZERO_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_AND_ORDERS",
        ),
    }
    provisional = S1SourceMetadataProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"protocol_evidence_hash"})
    )
    return S1SourceMetadataProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1SourceMetadataProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 source protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1SourceMetadataProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 source protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 source metadata.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1SourceMetadataProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 source protocol differs from reconstruction")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S1 source protocol: {args.output}")
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "requests=0 body_bytes=0 market_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
