from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_STOP,
    S5GitHubPreflightProtocol,
    S5GitHubPreflightProtocolAudit,
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    audit_s5_github_preflight_protocol,
    audit_s5_github_preflight_protocol_audit,
    audit_s5_github_preflight_result,
    audit_s5_github_preflight_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (  # noqa: E402
    S5GitHubPreflightFailureAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (  # noqa: E402
    S5BitcoinCoreSourceFeasibilityResult,
    audit_s5_source_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_preflight_failure_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_preflight_correction.py")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_preflight_failure.py")
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_protocol_audit_v1.json")
RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_result_v1.json")
RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_result_audit_v1.json")
TRANSCRIPT_PATH = Path("data/evidence/s5_github_pull_metadata_preflight_transcript_v1.json")
SOURCE_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json")
REPOSITORY_METADATA_PATH = Path(
    "data/evidence/s5_bitcoin_core_source_feasibility_responses_v1/"
    "01_github_repository_metadata.json"
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                PROTOCOL_PATH,
                PROTOCOL_AUDIT_PATH,
                RESULT_PATH,
                RESULT_AUDIT_PATH,
                TRANSCRIPT_PATH,
                SOURCE_RESULT_PATH,
                REPOSITORY_METADATA_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def decoded_body(path: Path) -> tuple[dict, bytes]:
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    body = base64.b64decode(wrapper["body_base64"], validate=True)
    return json.loads(body), body


def load_inputs() -> tuple[S5GitHubPreflightResult, S5GitHubPreflightResultAudit, dict, dict]:
    protocol = S5GitHubPreflightProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5GitHubPreflightProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5GitHubPreflightResult.model_validate_json(RESULT_PATH.read_text(encoding="utf-8"))
    result_audit = S5GitHubPreflightResultAudit.model_validate_json(
        RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    source_result = S5BitcoinCoreSourceFeasibilityResult.model_validate_json(
        SOURCE_RESULT_PATH.read_text(encoding="utf-8")
    )
    transcript = json.loads(TRANSCRIPT_PATH.read_text(encoding="utf-8"))
    response_body = base64.b64decode(transcript["response"]["body_base64"], validate=True)
    pulls = json.loads(response_body)
    repository, repository_body = decoded_body(REPOSITORY_METADATA_PATH)
    changed = (
        not audit_s5_github_preflight_protocol(protocol)
        or not audit_s5_github_preflight_protocol_audit(protocol_audit)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not audit_s5_github_preflight_result(result)
        or not audit_s5_github_preflight_result_audit(result_audit)
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or result.decision != S5_GITHUB_PREFLIGHT_STOP
        or result.request_attempt_count != 1
        or result.http_status != 200
        or result.response_byte_count != len(response_body)
        or result.response_body_sha256 != hashlib.sha256(response_body).hexdigest()
        or result.transcript_file_sha256 != file_sha256(TRANSCRIPT_PATH)
        or not audit_s5_source_result(source_result)
        or not isinstance(pulls, list)
        or len(pulls) != 1
        or not isinstance(pulls[0], dict)
        or repository.get("id") != 1_181_927
        or repository.get("full_name") != "bitcoin/bitcoin"
        or source_result.raw_artifacts[0].file_sha256
        != hashlib.sha256(REPOSITORY_METADATA_PATH.read_bytes()).hexdigest()
        or not repository_body
        or result.btc_market_values_read != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
    )
    if changed:
        raise ValueError("S5 GitHub preflight failure lineage changed")
    return result, result_audit, transcript, {"pull": pulls[0], "repository": repository}


def build_failure_audit(*, audited_at: datetime) -> S5GitHubPreflightFailureAudit:
    result, result_audit, transcript, decoded = load_inputs()
    pull = decoded["pull"]
    repository = decoded["repository"]
    link = transcript["response"]["headers"]["link"]
    first_link_url = link.split(",", 1)[0].split(";", 1)[0].strip()[1:-1]
    observed_path = urlparse(first_link_url).path
    payload = {
        "audited_at": audited_at,
        "auditor_contract_hash": auditor_contract_hash(),
        "source_bindings": source_bindings(),
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "prior_result_evidence_hash": result.result_evidence_hash,
        "prior_result_audit_evidence_hash": result_audit.audit_evidence_hash,
        "transcript_file_sha256": file_sha256(TRANSCRIPT_PATH),
        "repository_metadata_file_sha256": file_sha256(REPOSITORY_METADATA_PATH),
        "response_body_sha256": result.response_body_sha256,
        "canonical_repository_id": repository["id"],
        "canonical_repository_full_name": repository["full_name"],
        "observed_link_path": observed_path,
        "first_record_number": pull.get("number"),
        "first_record_state": pull.get("state"),
        "first_record_base_ref": pull.get("base", {}).get("ref"),
        "merge_commit_sha_key_present": "merge_commit_sha" in pull,
        "head_sha_key_present": isinstance(pull.get("head"), dict) and "sha" in pull["head"],
        "limitations": tuple(
            sorted(
                (
                    "The original STOP remains immutable and is not relabeled.",
                    "This audit reuses only the preserved response and executes no request.",
                    "The official list response omits merge_commit_sha for the observed record.",
                    "The official list response includes head.sha, but its value is not persisted "
                    "here.",
                    "The numeric repository Link path matches prior official repository identity.",
                    "A local correction can establish transport shape but not history "
                    "completeness.",
                    "Any corrected identity rule must fail closed on head-parent mismatch or "
                    "ambiguity.",
                    "No BTC value, parameter, return, candidate, signal, or order was accessed.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority is created.",
                )
            )
        ),
    }
    provisional = S5GitHubPreflightFailureAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubPreflightFailureAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubPreflightFailureAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub preflight failure audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub preflight failure-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightFailureAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub preflight failure audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S5 GitHub preflight failure.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubPreflightFailureAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_failure_audit(audited_at=stored.audited_at):
                raise ValueError("Stored S5 GitHub preflight failure audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_failure_audit(audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"status=200 bytes={audit.response_byte_count} canonical_repo_id="
            f"{audit.canonical_repository_id} additional_requests=0 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
