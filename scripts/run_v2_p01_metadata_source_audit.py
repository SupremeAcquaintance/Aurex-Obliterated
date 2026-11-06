import argparse
import hashlib
import sys
import time
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from aurex.backtest_engine.research_v2_metadata_source_audit import (
    V2_METADATA_MANDATORY_PROTOCOL_REQUIREMENTS,
    V2MetadataRequirementAssessment,
    V2MetadataSourceObservation,
    V2P01MetadataSourceAuditResult,
    audit_v2_p01_metadata_source_audit_result,
    build_v2_p01_metadata_source_audit_result,
)
from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2MetadataSourceTarget,
)
from aurex.backtest_engine.research_v2_metadata_source_contract_v1_1 import (
    V2P01MetadataSourceContractV1_1,
    audit_v2_p01_metadata_source_contract_v1_1,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_contract_module = import_module(
    "scripts.freeze_v2_p01_metadata_source_contract_v1_1"
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_FOUNDATION_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_result_v1.json"
)
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "v2_mechanism_discovery_charter_v1.json"
DEFAULT_THEORY_SCREEN = (
    DEFAULT_EVIDENCE_ROOT / "v2_mechanism_theory_screen_v1.json"
)
DEFAULT_METADATA_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1_1.json"
)
DEFAULT_SUPERSEDED_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_audit_v1_1.json"
)
USER_AGENT = "AurexEvidenceAudit/1.1"


def runner_contract_hash() -> str:
    paths = [
        PROJECT_ROOT / "scripts" / "run_v2_p01_metadata_source_audit.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_metadata_source_audit.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_contract(args) -> V2P01MetadataSourceContractV1_1:
    superseded, screen = _contract_module.load_inputs(args)
    contract = V2P01MetadataSourceContractV1_1.model_validate_json(
        args.metadata_contract.read_text(encoding="utf-8")
    )
    expected = _contract_module.authoritative_contract(
        frozen_at=contract.frozen_at,
        superseded=superseded,
        screen=screen,
    )
    audit = audit_v2_p01_metadata_source_contract_v1_1(
        contract=contract,
        superseded_contract=superseded,
    )
    if (
        contract != expected
        or audit["status"] != "PASS"
    ):
        raise ValueError(
            f"V2 metadata source contract v1.1 is not reproducible: "
            f"{audit['reasons']}"
        )
    return contract


def fetch_source(
    *,
    target: V2MetadataSourceTarget,
    checked_at: datetime,
    timeout_seconds: int,
    retry_attempts: int,
    opener=urlopen,
    sleeper=time.sleep,
) -> V2MetadataSourceObservation:
    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        request = Request(
            target.requested_url,
            headers={
                "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "identity",
                "User-Agent": USER_AGENT,
            },
            method="GET",
        )
        try:
            with opener(request, timeout=timeout_seconds) as response:
                status = int(getattr(response, "status", response.getcode()))
                final_url = response.geturl()
                final_domain = (urlparse(final_url).hostname or "").lower()
                if status not in {200, 202}:
                    raise ValueError(
                        f"{target.source_id} returned HTTP {status}"
                    )
                if final_domain not in target.allowed_final_domains:
                    raise ValueError(
                        f"{target.source_id} redirected to {final_domain}"
                    )
                payload = response.read(target.maximum_response_bytes + 1)
                if len(payload) > target.maximum_response_bytes:
                    raise ValueError(
                        f"{target.source_id} exceeded response-byte cap"
                    )
                text = payload.decode("utf-8", errors="replace")
                missing = [
                    marker
                    for marker in target.required_markers
                    if marker not in text
                ]
                if missing:
                    raise ValueError(
                        f"{target.source_id} missing markers: {missing}"
                    )
                content_type = response.headers.get(
                    "Content-Type",
                    "application/octet-stream",
                )
                return V2MetadataSourceObservation(
                    source_id=target.source_id,
                    requested_url=target.requested_url,
                    final_url=final_url,
                    checked_at=checked_at,
                    http_status=status,
                    content_type=content_type,
                    response_bytes=len(payload),
                    response_sha256=hashlib.sha256(payload).hexdigest(),
                    required_markers=target.required_markers,
                    found_markers=target.required_markers,
                    missing_markers=[],
                )
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = exc
            if attempt < retry_attempts:
                sleeper(float(attempt))
    raise ValueError(
        f"Metadata source {target.source_id} failed after "
        f"{retry_attempts} attempts: {last_error}"
    )


def authoritative_assessments(
    contract: V2P01MetadataSourceContractV1_1,
) -> list[V2MetadataRequirementAssessment]:
    archive_hashes = [
        contract.source_census_result_evidence_hash,
        contract.pilot_result_evidence_hash,
    ]
    foundation_hashes = [
        contract.derivatives_foundation_result_evidence_hash
    ]
    return [
        V2MetadataRequirementAssessment(
            requirement_id="HISTORICAL_SETTLED_FUNDING_AND_INTERVALS",
            status="READY_HISTORICAL_ARCHIVE",
            source_ids=[
                "BINANCE_PUBLIC_DATA_README",
                "BINANCE_USD_M_MARKET_DATA_DOCS",
            ],
            existing_evidence_hashes=archive_hashes,
            blocks_direct_historical_replay=False,
            conservative_research_override_permitted=False,
            required_protocol_treatment="USE_IMMUTABLE_ARCHIVE_AND_AUDIT",
            rationale=(
                "The checksum-pinned funding archives contain settlement timestamp, "
                "interval hours, and settled funding rate; the full-data protocol must "
                "still audit every event and cross-check the public history surface."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id=(
                "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES"
            ),
            status="READY_HISTORICAL_ARCHIVE",
            source_ids=[
                "BINANCE_PUBLIC_DATA_README",
                "BINANCE_USD_M_MARKET_DATA_DOCS",
            ],
            existing_evidence_hashes=archive_hashes,
            blocks_direct_historical_replay=False,
            conservative_research_override_permitted=False,
            required_protocol_treatment="USE_IMMUTABLE_ARCHIVE_AND_AUDIT",
            rationale=(
                "The census and pilot prove official archive availability and schema "
                "for all five one-minute price families over the complete-source set."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id="HISTORICAL_FUTURES_CONTRACT_LIFECYCLE",
            status=(
                "PARTIAL_ARCHIVE_COVERAGE_REQUIRES_CONTINUITY_GATE"
            ),
            source_ids=[
                "BINANCE_PUBLIC_DATA_README",
                "BINANCE_USD_M_MARKET_DATA_DOCS",
            ],
            existing_evidence_hashes=archive_hashes,
            blocks_direct_historical_replay=True,
            conservative_research_override_permitted=False,
            required_protocol_treatment=(
                "FAIL_CLOSED_ON_ANY_LIFECYCLE_OR_CONTINUITY_GAP"
            ),
            rationale=(
                "Archive presence helps bound observable trading periods and current "
                "exchangeInfo exposes onboard/status fields, but neither is a complete "
                "point-in-time contract-status history. Full continuity must fail "
                "closed rather than invent a listing or suspension state."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id="HISTORICAL_FUTURES_ORDER_FILTERS",
            status="CURRENT_ONLY_NOT_HISTORICAL",
            source_ids=["BINANCE_USD_M_MARKET_DATA_DOCS"],
            existing_evidence_hashes=[],
            blocks_direct_historical_replay=True,
            conservative_research_override_permitted=True,
            required_protocol_treatment=(
                "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_"
                "NON_ELIGIBILITY_LIMITATION"
            ),
            rationale=(
                "The official endpoint explicitly returns current trading rules. "
                "Current tick, step, notional, and market bounds cannot prove the "
                "rules that applied to an order in 2023-2024."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id="HISTORICAL_SPOT_ORDER_FILTERS",
            status="CURRENT_ONLY_NOT_HISTORICAL",
            source_ids=["BINANCE_SPOT_API_DOCS"],
            existing_evidence_hashes=[],
            blocks_direct_historical_replay=True,
            conservative_research_override_permitted=True,
            required_protocol_treatment=(
                "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_"
                "NON_ELIGIBILITY_LIMITATION"
            ),
            rationale=(
                "The official spot exchangeInfo surface describes current rules. "
                "A later research protocol may apply a conservative current-filter "
                "proxy but cannot call that historical execution proof."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id="HISTORICAL_ACCOUNT_FEE_TIER",
            status="CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL",
            source_ids=["BINANCE_USD_M_ACCOUNT_DOCS"],
            existing_evidence_hashes=[],
            blocks_direct_historical_replay=True,
            conservative_research_override_permitted=True,
            required_protocol_treatment=(
                "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_"
                "NON_ELIGIBILITY_LIMITATION"
            ),
            rationale=(
                "The documented commission endpoint is signed and returns current "
                "user rates. No credentials were used and no complete historical "
                "account-tier fee series is established."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id=(
                "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS"
            ),
            status="CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL",
            source_ids=["BINANCE_USD_M_ACCOUNT_DOCS"],
            existing_evidence_hashes=foundation_hashes,
            blocks_direct_historical_replay=True,
            conservative_research_override_permitted=True,
            required_protocol_treatment=(
                "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_"
                "NON_ELIGIBILITY_LIMITATION"
            ),
            rationale=(
                "The leverage-bracket endpoint is signed current user data. The "
                "synthetic engine proves internal margin arithmetic but cannot turn "
                "its fixed rates into historical Binance brackets."
            ),
        ),
        V2MetadataRequirementAssessment(
            requirement_id=(
                "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES"
            ),
            status="CURRENT_OR_UNAVAILABLE_NOT_HISTORICAL",
            source_ids=[
                "BINANCE_USD_M_ACCOUNT_DOCS",
                "BINANCE_USD_M_MARKET_DATA_DOCS",
            ],
            existing_evidence_hashes=foundation_hashes,
            blocks_direct_historical_replay=True,
            conservative_research_override_permitted=True,
            required_protocol_treatment=(
                "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_"
                "NON_ELIGIBILITY_LIMITATION"
            ),
            rationale=(
                "Current docs expose pieces of margin, liquidation-fee, and ADL "
                "behavior, while the synthetic engine covers declared internal "
                "failure paths. A complete point-in-time 2023-2024 rule history is "
                "not established."
            ),
        ),
    ]


def authoritative_result(
    *,
    generated_at: datetime,
    contract: V2P01MetadataSourceContractV1_1,
    observations: list[V2MetadataSourceObservation],
) -> V2P01MetadataSourceAuditResult:
    return build_v2_p01_metadata_source_audit_result(
        generated_at=generated_at,
        metadata_source_contract_evidence_hash=(
            contract.contract_evidence_hash
        ),
        theory_screen_evidence_hash=contract.theory_screen_evidence_hash,
        discovery_charter_evidence_hash=(
            contract.discovery_charter_evidence_hash
        ),
        source_census_result_evidence_hash=(
            contract.source_census_result_evidence_hash
        ),
        derivatives_foundation_result_evidence_hash=(
            contract.derivatives_foundation_result_evidence_hash
        ),
        runner_contract_hash=runner_contract_hash(),
        observations=observations,
        requirement_assessments=authoritative_assessments(contract),
        mandatory_next_protocol_requirements=(
            V2_METADATA_MANDATORY_PROTOCOL_REQUIREMENTS
        ),
        limitations=[
            (
                "Only two of eight requirements have direct historical archive "
                "evidence; six still block an unqualified historical replay."
            ),
            (
                "Current exchange and signed account documentation cannot be "
                "projected backward as 2023-2024 rules or account state."
            ),
            (
                "Five gaps may receive conservative research-only overrides, but "
                "those overrides cannot create historical execution proof."
            ),
            (
                "Contract lifecycle has no override and must fail closed on any "
                "listing, suspension, delisting, or continuity ambiguity."
            ),
            (
                "Source bodies were hashed and discarded; no credential, private "
                "endpoint, account data, market value, or return was accessed."
            ),
            (
                "The decision permits protocol design only and does not authorize "
                "full acquisition, data import, development, paper, or live trading."
            ),
        ],
    )


def write_result(
    path: Path,
    result: V2P01MetadataSourceAuditResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V2P01MetadataSourceAuditResult.model_validate_json(serialized) != result:
        raise ValueError("V2 metadata audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_audit(args) -> V2P01MetadataSourceAuditResult:
    if args.output.exists():
        raise ValueError("V2 metadata audit exists; use --check")
    contract = load_contract(args)
    generated_at = datetime.now(UTC)
    observations = [
        fetch_source(
            target=target,
            checked_at=generated_at,
            timeout_seconds=contract.request_timeout_seconds,
            retry_attempts=contract.retry_attempts_per_source,
        )
        for target in contract.source_targets
    ]
    result = authoritative_result(
        generated_at=generated_at,
        contract=contract,
        observations=observations,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"ready={result.ready_historical_requirement_count} "
        f"unresolved={result.unresolved_historical_requirement_count}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2P01MetadataSourceAuditResult:
    contract = load_contract(args)
    result = V2P01MetadataSourceAuditResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    audit = audit_v2_p01_metadata_source_audit_result(
        result=result,
        contract=contract,
        current_runner_contract_hash=runner_contract_hash(),
    )
    if audit["status"] != "PASS":
        raise ValueError(f"V2 metadata audit failed: {audit['reasons']}")
    if result.requirement_assessments != authoritative_assessments(contract):
        raise ValueError("V2 metadata assessments differ from frozen policy")
    print(
        "PASS "
        f"v2_metadata_audit={result.result_evidence_hash} "
        f"decision={result.decision} "
        f"credentials={result.credentials_used}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or verify the bounded P01 metadata-source audit."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--foundation-protocol",
        type=Path,
        default=DEFAULT_FOUNDATION_PROTOCOL,
    )
    parser.add_argument(
        "--foundation-result",
        type=Path,
        default=DEFAULT_FOUNDATION_RESULT,
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--theory-screen",
        type=Path,
        default=DEFAULT_THEORY_SCREEN,
    )
    parser.add_argument(
        "--metadata-contract",
        type=Path,
        default=DEFAULT_METADATA_CONTRACT,
    )
    parser.add_argument(
        "--superseded-contract",
        type=Path,
        default=DEFAULT_SUPERSEDED_CONTRACT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_audit(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
