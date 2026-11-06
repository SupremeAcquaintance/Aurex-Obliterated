import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3P03SourceAuditContract,
    audit_v3_p03_source_audit_contract,
)
from aurex.backtest_engine.research_v3_p03_transport_amendment import (
    V3P03TransportAmendment,
    audit_v3_p03_transport_amendment,
    build_v3_p03_transport_amendment,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "data/evidence/v3_p03_source_audit_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p03_transport_amendment_v1.json"
)


def source_contract_hash(paths: list[Path]) -> str:
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


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p03_transport_amendment.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_transport_amendment.py",
        ]
    )


def original_contract_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p03_source_audit_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
        ]
    )


def load_contract(path: Path) -> V3P03SourceAuditContract:
    contract = V3P03SourceAuditContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_source_audit_contract(contract)
        or contract.builder_contract_hash
        != original_contract_builder_hash()
    ):
        raise ValueError("Original V3P03 source audit contract failed audit")
    return contract


def authoritative_amendment(
    *,
    frozen_at: datetime,
    contract: V3P03SourceAuditContract,
) -> V3P03TransportAmendment:
    return build_v3_p03_transport_amendment(
        frozen_at=frozen_at,
        original_contract_evidence_hash=contract.contract_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "The first formal run stopped after the schema target returned HTTP "
                "202 and created no authoritative source-audit result."
            ),
            (
                "This amendment changes transport polling only; all five source "
                "targets and all eight qualification requirements remain unchanged."
            ),
            (
                "Only the exact schema target may return HTTP 202 and receive up to "
                "three bounded follow-up polls."
            ),
            (
                "A terminal HTTP 200 remains mandatory before schema content can be "
                "captured or classified."
            ),
            (
                "Pending-status exhaustion aborts without a partial authoritative "
                "result and cannot be treated as a passing source observation."
            ),
            (
                "No credential, market value, strategy outcome, source substitution, "
                "candidate, paper, sandbox, live, or capital permission is added."
            ),
        ],
    )


def write_amendment(path: Path, amendment: V3P03TransportAmendment) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if V3P03TransportAmendment.model_validate_json(serialized) != amendment:
        raise ValueError("V3P03 transport amendment JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3P03TransportAmendment:
    if args.output.exists():
        raise ValueError("Frozen V3P03 transport amendment exists; use --check")
    contract = load_contract(args.contract)
    amendment = authoritative_amendment(
        frozen_at=datetime.now(UTC),
        contract=contract,
    )
    write_amendment(args.output, amendment)
    print(
        f"WROTE {args.output} {amendment.amendment_evidence_hash} "
        f"max_requests={amendment.amended_maximum_http_requests}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3P03TransportAmendment:
    contract = load_contract(args.contract)
    amendment = V3P03TransportAmendment.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_amendment(
        frozen_at=amendment.frozen_at,
        contract=contract,
    )
    if amendment != expected:
        raise ValueError("V3P03 transport amendment is not reproducible")
    if not audit_v3_p03_transport_amendment(amendment):
        raise ValueError("V3P03 transport amendment hash audit failed")
    print(
        "PASS "
        f"v3p03_transport_amendment={amendment.amendment_evidence_hash} "
        f"targets_changed={amendment.source_targets_changed} "
        f"rules_changed={amendment.qualification_rule_changed} "
        f"max_requests={amendment.amended_maximum_http_requests}",
        flush=True,
    )
    return amendment


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the bounded V3P03 HTTP-202 transport amendment."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
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
