import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_sandbox_capability_profile import (  # noqa: E402
    BinanceSpotTestnetSandboxInput,
    BinanceSpotTestnetSandboxProfile,
    audit_binance_spot_testnet_sandbox_profile,
    build_binance_spot_testnet_sandbox_profile,
)
from aurex.backtest_engine.sandbox_profile_workflow import (  # noqa: E402
    DEFAULT_OUTPUT_PATH,
    DEFAULT_REVIEW_PATH,
    SANDBOX_PROFILE_LIMITATIONS,
    load_post_v4_capability_review,
    sandbox_profile_builder_contract_hash,
    sandbox_profile_template_payload,
)

DEFAULT_OUTPUT = DEFAULT_OUTPUT_PATH
DEFAULT_REVIEW = DEFAULT_REVIEW_PATH


def load_operator_input(path: Path) -> BinanceSpotTestnetSandboxInput:
    if not path.is_file():
        raise ValueError("Sandbox capability input file is required")
    return BinanceSpotTestnetSandboxInput.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def authoritative_profile(
    *,
    frozen_at: datetime,
    review_path: Path,
    operator_input: BinanceSpotTestnetSandboxInput,
) -> BinanceSpotTestnetSandboxProfile:
    review = load_post_v4_capability_review(review_path)
    return build_binance_spot_testnet_sandbox_profile(
        frozen_at=frozen_at,
        post_v4_capability_review_evidence_hash=review.review_evidence_hash,
        post_v4_capability_review_builder_hash=review.builder_contract_hash,
        builder_contract_hash=sandbox_profile_builder_contract_hash(),
        operator_input=operator_input,
        limitations=SANDBOX_PROFILE_LIMITATIONS,
    )


def write_profile(
    path: Path,
    profile: BinanceSpotTestnetSandboxProfile,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (profile.model_dump_json(indent=2) + "\n").encode("utf-8")
    if BinanceSpotTestnetSandboxProfile.model_validate_json(serialized) != profile:
        raise ValueError("Sandbox capability JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale sandbox profile output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def print_profile_summary(
    profile: BinanceSpotTestnetSandboxProfile,
    prefix: str,
) -> None:
    print(
        f"{prefix} decision={profile.decision} "
        f"adapter_implementation="
        f"{profile.sandbox_adapter_implementation_authorized} "
        f"charter_design={profile.successor_charter_design_authorized} "
        f"testnet_orders={profile.testnet_virtual_order_entry_authorized} "
        f"sandbox_qualified={profile.sandbox_qualified} "
        f"live={profile.creates_live_eligibility} "
        f"failed_gates={profile.failed_gate_ids} "
        f"profile={profile.profile_evidence_hash}",
        flush=True,
    )


def run_preflight(args) -> BinanceSpotTestnetSandboxProfile:
    operator_input = load_operator_input(args.input)
    profile = authoritative_profile(
        frozen_at=operator_input.attested_at,
        review_path=args.review,
        operator_input=operator_input,
    )
    print_profile_summary(profile, "PREFLIGHT")
    return profile


def run_freeze(args) -> BinanceSpotTestnetSandboxProfile:
    if args.output.exists():
        raise ValueError("Frozen sandbox profile exists; use --check")
    operator_input = load_operator_input(args.input)
    profile = authoritative_profile(
        frozen_at=datetime.now(UTC),
        review_path=args.review,
        operator_input=operator_input,
    )
    if not profile.sandbox_adapter_implementation_authorized:
        raise ValueError(
            "Sandbox capability failed predeclared gates; run --preflight and "
            "correct the input before freezing"
        )
    write_profile(args.output, profile)
    print_profile_summary(profile, f"WROTE {args.output}")
    return run_check(args)


def run_check(args) -> BinanceSpotTestnetSandboxProfile:
    profile = BinanceSpotTestnetSandboxProfile.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_profile(
        frozen_at=profile.frozen_at,
        review_path=args.review,
        operator_input=profile.operator_input,
    )
    if (
        profile != expected
        or not audit_binance_spot_testnet_sandbox_profile(profile)
    ):
        raise ValueError("Frozen sandbox capability is not reproducible")
    print_profile_summary(profile, "PASS")
    return profile


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Template, preflight, freeze, or audit the credential-free Binance "
            "Spot Testnet sandbox capability profile."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.template:
            print(json.dumps(sandbox_profile_template_payload(), indent=2))
        elif args.preflight:
            if args.input is None:
                raise ValueError("--preflight requires --input")
            run_preflight(args)
        elif args.freeze:
            if args.input is None:
                raise ValueError("--freeze requires --input")
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
