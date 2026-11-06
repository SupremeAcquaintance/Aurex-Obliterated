from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_GATE_IDS,
    S5_GITHUB_PREFLIGHT_STOP,
    S5GitHubPreflightGateResult,
    S5GitHubPreflightProtocol,
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    audit_s5_github_preflight_protocol,
    audit_s5_github_preflight_result,
    audit_s5_github_preflight_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_AMENDMENT_NEXT,
    S5_GITHUB_PREFLIGHT_CORRECTED_PASS,
    S5GitHubPreflightCorrectedResultV2,
    S5GitHubPreflightFailureAudit,
    S5GitHubPreflightInterpreterAmendmentAuditV2,
    S5GitHubPreflightInterpreterAmendmentV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_preflight_corrected_result_v2.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_preflight_correction.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_github_preflight_local_revalidation_v2.py")
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_protocol_v1.json")
PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_result_v1.json")
PRIOR_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_result_audit_v1.json"
)
FAILURE_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_failure_audit_v1.json")
AMENDMENT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_interpreter_amendment_v2.json"
)
AMENDMENT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_interpreter_amendment_audit_v2.json"
)
TRANSCRIPT_PATH = Path("data/evidence/s5_github_pull_metadata_preflight_transcript_v1.json")
SHA1_CHARACTERS = frozenset("0123456789abcdef")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def valid_sha1(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in SHA1_CHARACTERS for character in value)
    )


def parse_time(value: Any, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError("S5 corrected preflight timestamp is invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("S5 corrected preflight timestamp lacks timezone")
    return parsed


def load_inputs() -> tuple[
    S5GitHubPreflightProtocol,
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    S5GitHubPreflightFailureAudit,
    S5GitHubPreflightInterpreterAmendmentV2,
    S5GitHubPreflightInterpreterAmendmentAuditV2,
]:
    protocol = S5GitHubPreflightProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    prior = S5GitHubPreflightResult.model_validate_json(
        PRIOR_RESULT_PATH.read_text(encoding="utf-8")
    )
    prior_audit = S5GitHubPreflightResultAudit.model_validate_json(
        PRIOR_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    failure = S5GitHubPreflightFailureAudit.model_validate_json(
        FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    amendment = S5GitHubPreflightInterpreterAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    amendment_audit = S5GitHubPreflightInterpreterAmendmentAuditV2.model_validate_json(
        AMENDMENT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_github_preflight_protocol(protocol)
        or not audit_s5_github_preflight_result(prior)
        or not audit_s5_github_preflight_result_audit(prior_audit)
        or prior_audit.result_evidence_hash != prior.result_evidence_hash
        or prior.decision != S5_GITHUB_PREFLIGHT_STOP
        or not evidence_hash_valid(failure, "audit_evidence_hash")
        or failure.prior_result_evidence_hash != prior.result_evidence_hash
        or not evidence_hash_valid(amendment, "amendment_evidence_hash")
        or amendment.failure_audit_evidence_hash != failure.audit_evidence_hash
        or amendment.next_authorization != S5_GITHUB_PREFLIGHT_AMENDMENT_NEXT
        or not evidence_hash_valid(amendment_audit, "audit_evidence_hash")
        or amendment_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or file_sha256(TRANSCRIPT_PATH) != prior.transcript_file_sha256
    )
    if changed:
        raise ValueError("S5 corrected preflight predecessor lineage changed")
    return protocol, prior, prior_audit, failure, amendment, amendment_audit


def parse_corrected_link(
    *, link: str, amendment: S5GitHubPreflightInterpreterAmendmentV2
) -> tuple[str, int]:
    relations: dict[str, str] = {}
    for segment in link.split(","):
        url_part, separator, parameters = segment.strip().partition(";")
        if not separator or not url_part.startswith("<") or not url_part.endswith(">"):
            raise ValueError("S5 corrected preflight Link header is malformed")
        relation = None
        for parameter in parameters.split(";"):
            key, equals, value = parameter.strip().partition("=")
            if equals and key == "rel":
                relation = value.strip('"')
        if relation:
            relations[relation] = url_part[1:-1]
    last_url = relations.get("last")
    if last_url is None:
        raise ValueError("S5 corrected preflight Link header lacks last relation")
    parsed = urlparse(last_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    expected = {
        "state": ["closed"],
        "base": ["master"],
        "sort": ["created"],
        "direction": ["asc"],
        "per_page": ["1"],
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.path not in amendment.permitted_link_paths
        or any(query.get(key) != value for key, value in expected.items())
        or set(query) != {*expected, "page"}
        or len(query["page"]) != 1
        or not query["page"][0].isdigit()
        or int(query["page"][0]) <= 0
    ):
        raise ValueError("S5 corrected preflight Link scope changed")
    return parsed.path, int(query["page"][0])


def preserved_payload() -> tuple[dict, bytes, dict[str, Any]]:
    transcript = json.loads(TRANSCRIPT_PATH.read_text(encoding="utf-8"))
    body = base64.b64decode(transcript["response"]["body_base64"], validate=True)
    if (
        transcript["response"]["body_byte_count"] != len(body)
        or transcript["response"]["body_sha256"] != hashlib.sha256(body).hexdigest()
    ):
        raise ValueError("S5 corrected preflight preserved body changed")
    pulls = json.loads(body)
    if not isinstance(pulls, list) or len(pulls) != 1 or not isinstance(pulls[0], dict):
        raise ValueError("S5 corrected preflight preserved payload changed")
    return transcript, body, pulls[0]


def corrected_gate_results() -> tuple[S5GitHubPreflightGateResult, ...]:
    evidence = (
        "Transport, failure, amendment, and amendment-audit lineage is hash-bound.",
        "The original exact unauthenticated page-one request remains unchanged.",
        "The original run executed exactly one request and the correction executes zero.",
        "The preserved response is HTTP 200 at the original URL with zero redirect.",
        "The 15,733-byte response body and transcript hashes reverify exactly.",
        "The actual one-record GitHub list payload validates under the corrected schema.",
        "The preserved unauthenticated core rate-limit headers validate exactly.",
        "The numeric Link path matches canonical repository ID 1181927 and query scope.",
        "The closed master record exposes created_at, nullable merged_at, base.sha, and head.sha.",
        "The terminal count 24,012 yields exactly 241 bulk pages and five rate windows.",
        "No Authorization header, token value, environment proxy, redirect, or retry was used.",
        "Zero BTC values, parameters, returns, candidates, strategy executions, or orders ran.",
        "Source completeness and predictive edge remain explicitly unadjudicated.",
        "A PASS authorizes only a separately frozen bulk-acquisition protocol.",
    )
    return tuple(
        S5GitHubPreflightGateResult(gate_id=gate_id, status="PASS", evidence=message)
        for gate_id, message in zip(S5_GITHUB_PREFLIGHT_GATE_IDS, evidence, strict=True)
    )


def build_result(*, corrected_at: datetime) -> S5GitHubPreflightCorrectedResultV2:
    protocol, prior, prior_audit, failure, amendment, amendment_audit = load_inputs()
    transcript, body, pull = preserved_payload()
    response = transcript["response"]
    headers = response["headers"]
    request = transcript["request"]
    accepted_path, terminal_count = parse_corrected_link(link=headers["link"], amendment=amendment)
    base = pull.get("base")
    head = pull.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise ValueError("S5 corrected preflight identity records are invalid")
    base_sha = base.get("sha")
    head_sha = head.get("sha")
    if (
        pull.get("number") != 9
        or pull.get("state") != "closed"
        or base.get("ref") != "master"
        or not valid_sha1(base_sha)
        or not valid_sha1(head_sha)
        or "merge_commit_sha" in pull
        or request["authorization_header_used"] is not False
        or request["token_value_accessed"] is not False
        or request["environment_proxy_used"] is not False
        or response["http_status"] != 200
        or response["final_url"] != protocol.request_url
        or response["redirect_count"] != 0
        or headers["x-ratelimit-limit"] != "60"
        or headers["x-ratelimit-remaining"] != "59"
        or headers["x-ratelimit-resource"] != "core"
        or terminal_count != 24_012
    ):
        raise ValueError("S5 corrected preflight preserved response failed validation")
    payload = {
        "corrected_at": corrected_at,
        "runner_contract_hash": runner_contract_hash(),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "prior_result_evidence_hash": prior.result_evidence_hash,
        "prior_result_audit_evidence_hash": prior_audit.audit_evidence_hash,
        "failure_audit_evidence_hash": failure.audit_evidence_hash,
        "amendment_evidence_hash": amendment.amendment_evidence_hash,
        "amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
        "transcript_file_sha256": file_sha256(TRANSCRIPT_PATH),
        "response_body_sha256": hashlib.sha256(body).hexdigest(),
        "content_type": headers["content-type"],
        "canonical_repository_id": amendment.canonical_repository_id,
        "accepted_link_path": accepted_path,
        "first_pull_base_sha": base_sha,
        "first_pull_head_sha": head_sha,
        "first_pull_created_at": parse_time(pull.get("created_at")),
        "first_pull_merged_at": parse_time(pull.get("merged_at"), nullable=True),
        "gate_results": corrected_gate_results(),
        "limitations": tuple(
            sorted(
                (
                    "The original STOP is preserved and this result records a local correction.",
                    "No request was replayed and no new response or metadata record was acquired.",
                    "The terminal count is a current snapshot and can change after acquisition.",
                    "Closed pull records include both merged and unmerged proposals.",
                    "Bulk normalization must require merged_at before treating a record as "
                    "accepted.",
                    "Bulk identity must match head.sha to the Git merge second parent or fail "
                    "closed.",
                    "Deleted or mutated historical records can still prevent source completeness.",
                    "A PASS authorizes only bulk-acquisition protocol design.",
                    "No BTC value, parameter, return, candidate, signal, or order was created.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority was created.",
                )
            )
        ),
    }
    provisional = S5GitHubPreflightCorrectedResultV2.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5GitHubPreflightCorrectedResultV2.model_validate(complete)


def write_atomic(path: Path, result: S5GitHubPreflightCorrectedResultV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite corrected S5 GitHub preflight result: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale corrected S5 GitHub preflight transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightCorrectedResultV2.model_validate_json(serialized) != result:
        raise ValueError("Corrected S5 GitHub preflight result did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the S5 preflight local correction once.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        result = build_result(corrected_at=datetime.now(UTC))
        write_atomic(args.output, result)
        print(
            f"RECORDED {args.output} {result.result_evidence_hash} "
            f"decision={S5_GITHUB_PREFLIGHT_CORRECTED_PASS} "
            f"records={result.terminal_record_count} "
            f"bulk_pages={result.bulk_request_page_count_at_100} "
            f"unauth_hours={result.bulk_unauthenticated_hours_lower_bound} "
            "additional_requests=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
