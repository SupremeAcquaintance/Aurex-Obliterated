from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
    audit_s5_census_result,
    audit_s5_census_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadResultV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_bitcoin_core_history_census import (  # noqa: E402
    dataset_manifest_valid,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_history_census import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    MODULE_PATH,
    build_result,
    load_protocol,
    run_census,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_history_census_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_census_result_audit_v1.json")
HISTORY_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v2.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_history_census_result.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct_result(result_path: Path) -> S5BitcoinCoreHistoryCensusResult:
    protocol = load_protocol(DEFAULT_PROTOCOL, DEFAULT_PROTOCOL_AUDIT)
    result = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_s5_census_result(result)
        or result.runner_contract_hash != runner_contract_hash()
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
    ):
        raise ValueError("S5 census result or runner contract changed")
    history_result = S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
        HISTORY_RESULT_PATH.read_text(encoding="utf-8")
    )
    manifest_matches = (
        history_result.dataset_directory_sha256 == protocol.dataset_directory_sha256
        and dataset_manifest_valid(history_result)
    )
    inspection = run_census(protocol)
    expected = build_result(
        protocol=protocol,
        inspection=inspection,
        dataset_manifest_matches=manifest_matches,
        local_git_process_count=2,
        github_token_environment_present=result.github_token_environment_present,
        executed_at=result.executed_at,
    )
    if result != expected:
        raise ValueError("S5 census result differs from local reconstruction")
    return result


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5BitcoinCoreHistoryCensusResultAudit:
    result = reconstruct_result(result_path)
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "commit_object_count": result.commit_object_count,
        "recognized_pull_merge_count": result.recognized_pull_merge_count,
        "distinct_pull_request_count": result.distinct_pull_request_count,
        "exact_direct_pull_request_count": result.exact_direct_pull_request_count,
        "passed_gate_count": result.passed_gate_count,
        "failed_gate_count": result.failed_gate_count,
        "next_authorization": result.next_authorization,
    }
    provisional = S5BitcoinCoreHistoryCensusResultAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5BitcoinCoreHistoryCensusResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5BitcoinCoreHistoryCensusResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 census result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 census result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 census result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the local S5 history census result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected or not audit_s5_census_result_audit(stored):
                raise ValueError("Stored S5 census result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"commits={audit.commit_object_count} "
            f"recognized={audit.recognized_pull_merge_count} "
            f"distinct_prs={audit.distinct_pull_request_count} "
            f"direct_requests={audit.exact_direct_pull_request_count} "
            f"gates={audit.passed_gate_count}/13 additional_network=0 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
