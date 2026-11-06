from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (  # noqa: E402
    S5GitHubPreflightCorrectedResultAuditV2,
    S5GitHubPreflightCorrectedResultV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_github_preflight_local_revalidation_v2 import (  # noqa: E402
    MODULE_PATH,
    build_result,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_preflight_corrected_result_v2.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_corrected_result_audit_v2.json"
)
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_preflight_corrected_result_v2.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S5GitHubPreflightCorrectedResultV2:
    stored = S5GitHubPreflightCorrectedResultV2.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not evidence_hash_valid(stored, "result_evidence_hash"):
        raise ValueError("Corrected S5 GitHub preflight result failed its evidence hash")
    if stored.runner_contract_hash != runner_contract_hash():
        raise ValueError("Corrected S5 GitHub preflight runner source changed")
    if stored != build_result(corrected_at=stored.corrected_at):
        raise ValueError("Corrected S5 GitHub preflight result differs from reconstruction")
    return stored


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5GitHubPreflightCorrectedResultAuditV2:
    result = reconstruct(result_path)
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S5GitHubPreflightCorrectedResultAuditV2.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubPreflightCorrectedResultAuditV2.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubPreflightCorrectedResultAuditV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite corrected S5 GitHub result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale corrected S5 GitHub result-audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightCorrectedResultAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("Corrected S5 GitHub preflight result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the corrected S5 preflight result v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubPreflightCorrectedResultAuditV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected or not evidence_hash_valid(stored, "audit_evidence_hash"):
                raise ValueError("Stored corrected S5 GitHub result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"records={audit.terminal_record_count} "
            f"bulk_pages={audit.bulk_request_page_count_at_100} "
            "additional_requests=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
