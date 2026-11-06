import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.operator_profile_workflow import (  # noqa: E402
    OPERATOR_PROFILE_LIMITATIONS as PROFILE_LIMITATIONS,
)
from aurex.backtest_engine.operator_profile_workflow import (  # noqa: E402
    operator_profile_builder_contract_hash as builder_contract_hash,
)
from aurex.backtest_engine.operator_profile_workflow import (  # noqa: E402
    operator_profile_template_payload as template_payload,
)
from aurex.backtest_engine.research_operator_access_profile import (  # noqa: E402
    OperatorAccessCapitalDataInput,
    PostV4OperatorAccessProfile,
    audit_post_v4_operator_access_profile,
    build_post_v4_operator_access_profile,
)
from aurex.backtest_engine.research_post_v4_capability_review import (  # noqa: E402
    PostV4CapabilityGapReview,
    audit_post_v4_capability_gap_review,
)
from scripts.freeze_post_v4_capability_review import (  # noqa: E402
    authoritative_review,
)
from scripts.freeze_post_v4_capability_review import (  # noqa: E402
    builder_contract_hash as review_builder_hash,
)
from scripts.freeze_post_v4_capability_review import (  # noqa: E402
    load_inputs as load_review_lineage,
)

DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_P01_ADDENDUM = Path(
    "data/evidence/v4_p01_terminal_audit_addendum_v1.json"
)
DEFAULT_P02_CONTRACT = Path(
    "data/evidence/v4_p02_feasibility_contract_v1.json"
)
DEFAULT_V4_SCREEN = Path(
    "data/evidence/v4_mechanism_feasibility_screen_v1.json"
)
DEFAULT_REVIEW = Path(
    "data/evidence/post_v4_capability_gap_review_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/post_v4_operator_access_profile_v1.json"
)


def load_review(args) -> PostV4CapabilityGapReview:
    lineage = load_review_lineage(args)
    review = PostV4CapabilityGapReview.model_validate_json(
        args.review.read_text(encoding="utf-8")
    )
    expected = authoritative_review(
        frozen_at=review.frozen_at,
        charter=lineage[0],
        register=lineage[1],
        screen=lineage[2],
    )
    if (
        review != expected
        or not audit_post_v4_capability_gap_review(review)
        or review.builder_contract_hash != review_builder_hash()
        or review.successor_discovery_authorized
        or review.creates_candidate
    ):
        raise ValueError("Post-V4 capability review audit failed")
    return review


def load_operator_input(path: Path) -> OperatorAccessCapitalDataInput:
    if not path.is_file():
        raise ValueError("Operator profile input file is required")
    return OperatorAccessCapitalDataInput.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def authoritative_profile(
    *,
    frozen_at: datetime,
    review: PostV4CapabilityGapReview,
    operator_input: OperatorAccessCapitalDataInput,
) -> PostV4OperatorAccessProfile:
    return build_post_v4_operator_access_profile(
        frozen_at=frozen_at,
        post_v4_capability_review_evidence_hash=review.review_evidence_hash,
        post_v4_capability_review_builder_hash=review.builder_contract_hash,
        builder_contract_hash=builder_contract_hash(),
        operator_input=operator_input,
        limitations=PROFILE_LIMITATIONS,
    )


def write_profile(path: Path, profile: PostV4OperatorAccessProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (profile.model_dump_json(indent=2) + "\n").encode("utf-8")
    if PostV4OperatorAccessProfile.model_validate_json(serialized) != profile:
        raise ValueError("Operator profile JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale operator profile output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def print_profile_summary(profile: PostV4OperatorAccessProfile, prefix: str) -> None:
    print(
        f"{prefix} decision={profile.decision} "
        f"charter_design={profile.successor_charter_design_authorized} "
        f"failed_gates={profile.failed_gate_ids} "
        f"profile={profile.profile_evidence_hash}",
        flush=True,
    )


def run_preflight(args) -> PostV4OperatorAccessProfile:
    review = load_review(args)
    operator_input = load_operator_input(args.input)
    profile = authoritative_profile(
        frozen_at=operator_input.attested_at,
        review=review,
        operator_input=operator_input,
    )
    print_profile_summary(profile, "PREFLIGHT")
    return profile


def run_freeze(args) -> PostV4OperatorAccessProfile:
    if args.output.exists():
        raise ValueError("Frozen operator profile exists; use --check")
    review = load_review(args)
    operator_input = load_operator_input(args.input)
    profile = authoritative_profile(
        frozen_at=datetime.now(UTC),
        review=review,
        operator_input=operator_input,
    )
    if not profile.successor_charter_design_authorized:
        raise ValueError(
            "Operator profile failed predeclared gates; run --preflight and "
            "correct the input before freezing"
        )
    write_profile(args.output, profile)
    print_profile_summary(profile, f"WROTE {args.output}")
    return run_check(args)


def run_check(args) -> PostV4OperatorAccessProfile:
    review = load_review(args)
    profile = PostV4OperatorAccessProfile.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_profile(
        frozen_at=profile.frozen_at,
        review=review,
        operator_input=profile.operator_input,
    )
    if (
        profile != expected
        or not audit_post_v4_operator_access_profile(profile)
    ):
        raise ValueError("Frozen operator profile is not reproducible")
    print_profile_summary(profile, "PASS")
    return profile


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Template, preflight, freeze, or audit the credential-free post-V4 "
            "operator access, capital, loss, and data-budget profile."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--p01-addendum",
        type=Path,
        default=DEFAULT_P01_ADDENDUM,
    )
    parser.add_argument(
        "--p02-contract",
        type=Path,
        default=DEFAULT_P02_CONTRACT,
    )
    parser.add_argument("--v4-screen", type=Path, default=DEFAULT_V4_SCREEN)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.template:
            print(json.dumps(template_payload(), indent=2), flush=True)
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
