from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    audit_s5_github_preflight_result,
    audit_s5_github_preflight_result_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_github_preflight import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    MODULE_PATH,
    build_result,
    load_protocol,
    observation_from_transcript,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_preflight_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_preflight_result_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_preflight_result.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct_result(result_path: Path) -> S5GitHubPreflightResult:
    protocol = load_protocol(DEFAULT_PROTOCOL, DEFAULT_PROTOCOL_AUDIT)
    result = S5GitHubPreflightResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    if (
        not audit_s5_github_preflight_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("S5 GitHub preflight result or runner contract changed")
    transcript_path = Path(result.transcript_path)
    if (
        file_sha256(transcript_path) != result.transcript_file_sha256
        or transcript_path.stat().st_size != result.transcript_byte_count
    ):
        raise ValueError("S5 GitHub preflight transcript changed")
    observation = observation_from_transcript(path=transcript_path, protocol=protocol)
    expected = build_result(
        protocol=protocol,
        observation=observation,
        transcript_path=transcript_path,
        executed_at=result.executed_at,
    )
    if result != expected:
        raise ValueError("S5 GitHub preflight result differs from transcript reconstruction")
    return result


def build_audit(*, result_path: Path, audited_at: datetime) -> S5GitHubPreflightResultAudit:
    result = reconstruct_result(result_path)
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "http_status": result.http_status,
        "terminal_record_count": result.terminal_record_count,
        "bulk_request_page_count_at_100": result.bulk_request_page_count_at_100,
        "passed_gate_count": result.passed_gate_count,
        "failed_gate_count": result.failed_gate_count,
        "next_authorization": result.next_authorization,
    }
    provisional = S5GitHubPreflightResultAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubPreflightResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubPreflightResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub preflight result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub preflight result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub preflight result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S5 GitHub preflight result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubPreflightResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected or not audit_s5_github_preflight_result_audit(stored):
                raise ValueError("Stored S5 GitHub preflight result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"status={audit.http_status} records={audit.terminal_record_count} "
            f"bulk_pages={audit.bulk_request_page_count_at_100} "
            f"gates={audit.passed_gate_count}/14 additional_requests=0 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
