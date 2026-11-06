from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (  # noqa: E402
    S5_SOURCE_GATE_IDS,
    S5_SOURCE_NEXT,
    S5_SOURCE_NONE,
    S5_SOURCE_PASS,
    S5_SOURCE_STOP,
    S5BitcoinCoreSourceFeasibilityProtocol,
    S5BitcoinCoreSourceFeasibilityProtocolAudit,
    S5BitcoinCoreSourceFeasibilityResult,
    S5GitRefRecord,
    S5MetadataAttempt,
    S5RawArtifactRecord,
    S5SourceGateResult,
    audit_s5_source_protocol,
    audit_s5_source_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_source_feasibility_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json")
DEFAULT_RESPONSE_DIR = Path("data/evidence/s5_bitcoin_core_source_feasibility_responses_v1")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_source_feasibility.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_source_feasibility.py")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def write_bytes_atomic(path: Path, content: bytes) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 response artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 response transaction exists: {temporary}")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_result_atomic(path: Path, result: S5BitcoinCoreSourceFeasibilityResult) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreSourceFeasibilityResult.model_validate_json(serialized) != result:
        raise ValueError("S5 source-feasibility result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def planned_attempts() -> list[S5MetadataAttempt]:
    return [
        S5MetadataAttempt(
            attempt_id="01_GITHUB_REPOSITORY_METADATA",
            attempt_kind="HTTP_GET",
            attempted=False,
            succeeded=False,
            started_at=None,
            completed_at=None,
            status_code_or_exit_code=None,
            response_bytes=0,
            raw_artifact_path=None,
            raw_artifact_sha256=None,
            error_type=None,
            error_message=None,
        ),
        S5MetadataAttempt(
            attempt_id="02_GIT_REF_DISCOVERY",
            attempt_kind="GIT_LS_REMOTE",
            attempted=False,
            succeeded=False,
            started_at=None,
            completed_at=None,
            status_code_or_exit_code=None,
            response_bytes=0,
            raw_artifact_path=None,
            raw_artifact_sha256=None,
            error_type=None,
            error_message=None,
        ),
    ]


def bounded_error(exc: BaseException) -> tuple[str, str]:
    return type(exc).__name__, str(exc)[:500]


def run_repository_attempt(
    *, protocol: S5BitcoinCoreSourceFeasibilityProtocol, response_dir: Path
) -> tuple[S5MetadataAttempt, S5RawArtifactRecord, dict[str, Any], dict[str, str]]:
    started = datetime.now(UTC)
    path = response_dir / "01_github_repository_metadata.json"
    status_code: int | None = None
    body = b""
    parsed: dict[str, Any] = {}
    headers: dict[str, str] = {}
    error_type: str | None = None
    error_message: str | None = None
    try:
        request = urllib.request.Request(
            protocol.repository_endpoint.url,
            method="GET",
            headers={
                "Accept": protocol.github_accept_header,
                "User-Agent": protocol.github_user_agent,
                "X-GitHub-Api-Version": protocol.github_api_version,
            },
        )
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=protocol.request_timeout_seconds
        ) as response:
            status_code = int(response.status)
            body = response.read(protocol.repository_endpoint.maximum_response_bytes + 1)
            if len(body) > protocol.repository_endpoint.maximum_response_bytes:
                raise ValueError("GitHub repository response exceeded frozen byte limit")
            headers = {
                key.lower(): value
                for key, value in response.headers.items()
                if key.lower() in protocol.repository_endpoint.response_headers_to_preserve
            }
        payload = json.loads(body.decode("utf-8"))
        license_payload = payload.get("license") or {}
        parsed = {
            "full_name": payload.get("full_name"),
            "private": payload.get("private"),
            "archived": payload.get("archived"),
            "disabled": payload.get("disabled"),
            "visibility": payload.get("visibility"),
            "default_branch": payload.get("default_branch"),
            "clone_url": payload.get("clone_url"),
            "license_spdx_id": license_payload.get("spdx_id"),
        }
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        body = exc.read(protocol.repository_endpoint.maximum_response_bytes)
        error_type, error_message = bounded_error(exc)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error_type, error_message = bounded_error(exc)
        if not body:
            body = json.dumps(
                {"error_type": error_type, "error_message": error_message},
                sort_keys=True,
            ).encode("utf-8")
    artifact_content = json.dumps(
        {
            "body_base64": base64.b64encode(body).decode("ascii"),
            "headers": headers,
            "status_code": status_code,
        },
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    write_bytes_atomic(path, artifact_content)
    sha = file_sha256(path)
    succeeded = status_code == 200 and error_type is None
    completed = datetime.now(UTC)
    attempt = S5MetadataAttempt(
        attempt_id="01_GITHUB_REPOSITORY_METADATA",
        attempt_kind="HTTP_GET",
        attempted=True,
        succeeded=succeeded,
        started_at=started,
        completed_at=completed,
        status_code_or_exit_code=status_code,
        response_bytes=len(body),
        raw_artifact_path=path.as_posix(),
        raw_artifact_sha256=sha,
        error_type=error_type,
        error_message=error_message,
    )
    artifact = S5RawArtifactRecord(
        attempt_id=attempt.attempt_id,
        path=path.as_posix(),
        file_sha256=sha,
        byte_count=len(artifact_content),
    )
    return attempt, artifact, parsed, headers


def parse_git_refs(stdout: bytes) -> tuple[S5GitRefRecord, ...]:
    records: list[S5GitRefRecord] = []
    for line in stdout.decode("utf-8").splitlines():
        object_hash, separator, ref = line.partition("\t")
        if not separator:
            raise ValueError("Unexpected git ls-remote row")
        records.append(S5GitRefRecord(ref=ref, object_hash=object_hash))
    return tuple(sorted(records, key=lambda item: item.ref))


def run_git_attempt(
    *, protocol: S5BitcoinCoreSourceFeasibilityProtocol, response_dir: Path
) -> tuple[S5MetadataAttempt, S5RawArtifactRecord, tuple[S5GitRefRecord, ...]]:
    started = datetime.now(UTC)
    path = response_dir / "02_git_ref_discovery.txt"
    stdout = b""
    stderr = b""
    exit_code: int | None = None
    records: tuple[S5GitRefRecord, ...] = ()
    error_type: str | None = None
    error_message: str | None = None
    try:
        git = shutil.which("git")
        if git is None:
            raise OSError("git executable not found")
        completed = subprocess.run(
            [
                git,
                "ls-remote",
                protocol.git_probe.remote_url,
                *protocol.git_probe.refs,
            ],
            check=False,
            capture_output=True,
            timeout=protocol.request_timeout_seconds,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        if len(stdout) > protocol.git_probe.maximum_stdout_bytes:
            raise ValueError("git ls-remote output exceeded frozen byte limit")
        if exit_code != 0:
            raise OSError(stderr.decode("utf-8", errors="replace")[:500])
        records = parse_git_refs(stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        error_type, error_message = bounded_error(exc)
        if not stdout:
            stdout = json.dumps(
                {"error_type": error_type, "error_message": error_message},
                sort_keys=True,
            ).encode("utf-8")
    write_bytes_atomic(path, stdout)
    sha = file_sha256(path)
    succeeded = exit_code == 0 and error_type is None
    completed_at = datetime.now(UTC)
    attempt = S5MetadataAttempt(
        attempt_id="02_GIT_REF_DISCOVERY",
        attempt_kind="GIT_LS_REMOTE",
        attempted=True,
        succeeded=succeeded,
        started_at=started,
        completed_at=completed_at,
        status_code_or_exit_code=exit_code,
        response_bytes=len(stdout),
        raw_artifact_path=path.as_posix(),
        raw_artifact_sha256=sha,
        error_type=error_type,
        error_message=error_message,
    )
    artifact = S5RawArtifactRecord(
        attempt_id=attempt.attempt_id,
        path=path.as_posix(),
        file_sha256=sha,
        byte_count=len(stdout),
    )
    return attempt, artifact, records


def integer_header(headers: dict[str, str], key: str) -> int | None:
    value = headers.get(key)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def build_gate_results(
    *,
    protocol: S5BitcoinCoreSourceFeasibilityProtocol,
    attempts: tuple[S5MetadataAttempt, ...],
    repository: dict[str, Any],
    headers: dict[str, str],
    refs: tuple[S5GitRefRecord, ...],
) -> tuple[S5SourceGateResult, ...]:
    http_ok = attempts[0].succeeded
    git_ok = attempts[1].succeeded
    ref_map = {item.ref: item.object_hash for item in refs}
    canonical = (
        http_ok
        and repository.get("full_name") == "bitcoin/bitcoin"
        and repository.get("private") is False
        and repository.get("archived") is False
        and repository.get("disabled") is False
        and repository.get("default_branch") == "master"
    )
    refs_exact = tuple(sorted(ref_map)) == tuple(sorted(protocol.git_probe.refs))
    rate_limit = integer_header(headers, "x-ratelimit-limit")
    rate_remaining = integer_header(headers, "x-ratelimit-remaining")
    conditions = (
        True,
        canonical,
        git_ok,
        http_ok and repository.get("license_spdx_id") == "MIT",
        True,
        True,
        True,
        True,
        http_ok and rate_limit is not None and rate_remaining is not None,
        git_ok and refs_exact,
        True,
        protocol.protocol_pass_condition_reachable_by_allowed_sources,
        protocol.parameters_defined == 0 and protocol.candidates_created == 0,
        protocol.repository_history_permitted is False
        and protocol.market_values_permitted is False,
    )
    evidence = (
        "Frozen S5 charter binds the 12 exhausted predecessor families.",
        "GitHub repository metadata must identify public active bitcoin/bitcoin master.",
        "The bounded unauthenticated git ls-remote attempt must succeed.",
        "GitHub repository metadata must report SPDX MIT.",
        "The frozen charter records Git author-date override risk.",
        "The frozen charter records Bitcoin Core rebase and signed-merge workflow.",
        "The frozen charter binds official public commit endpoint documentation.",
        "The frozen charter binds official pull merged_at endpoint documentation.",
        "The repository response must include nonnegative GitHub rate-limit headers.",
        "The Git response must contain exactly HEAD, master, and v30.0 hashes.",
        "The charter defines availability evidence without reading history payloads.",
        "The protocol reachability review is true and uses only allowed metadata.",
        "The frozen protocol contains one mechanism and zero parameters/candidates.",
        "The frozen protocol denies history, market values, and every trading mode.",
    )
    return tuple(
        S5SourceGateResult(
            gate_id=gate_id,
            status="PASS" if condition else "FAIL",
            evidence=message,
        )
        for gate_id, condition, message in zip(
            S5_SOURCE_GATE_IDS, conditions, evidence, strict=True
        )
    )


def build_result(
    *,
    protocol: S5BitcoinCoreSourceFeasibilityProtocol,
    attempts: tuple[S5MetadataAttempt, ...],
    artifacts: tuple[S5RawArtifactRecord, ...],
    repository: dict[str, Any],
    headers: dict[str, str],
    refs: tuple[S5GitRefRecord, ...],
    executed_at: datetime,
) -> S5BitcoinCoreSourceFeasibilityResult:
    gates = build_gate_results(
        protocol=protocol,
        attempts=attempts,
        repository=repository,
        headers=headers,
        refs=refs,
    )
    failed = sum(item.status == "FAIL" for item in gates)
    passed = len(gates) - failed
    success = failed == 0
    ref_map = {item.ref: item.object_hash for item in refs}
    payload = {
        "executed_at": executed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "attempts": attempts,
        "raw_artifacts": tuple(sorted(artifacts, key=lambda item: item.attempt_id)),
        "attempted_count": sum(item.attempted for item in attempts),
        "succeeded_count": sum(item.succeeded for item in attempts),
        "repository_full_name": repository.get("full_name"),
        "repository_private": repository.get("private"),
        "repository_archived": repository.get("archived"),
        "repository_disabled": repository.get("disabled"),
        "repository_visibility": repository.get("visibility"),
        "repository_default_branch": repository.get("default_branch"),
        "repository_clone_url": repository.get("clone_url"),
        "repository_license_spdx_id": repository.get("license_spdx_id"),
        "github_rate_limit": integer_header(headers, "x-ratelimit-limit"),
        "github_rate_remaining": integer_header(headers, "x-ratelimit-remaining"),
        "git_ref_records": refs,
        "head_matches_master": (
            bool(ref_map) and ref_map.get("HEAD") == ref_map.get("refs/heads/master")
        ),
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": failed,
        "repository_aggregate_numeric_context_received": attempts[0].succeeded,
        "source_feasibility_conclusion": (
            "TECHNICALLY_FEASIBLE_METADATA_PATH_ONLY"
            if success
            else "NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL"
        ),
        "decision": S5_SOURCE_PASS if success else S5_SOURCE_STOP,
        "next_authorization": S5_SOURCE_NEXT if success else S5_SOURCE_NONE,
        "authorizes_history_payload_protocol": success,
        "limitations": tuple(
            sorted(
                (
                    "This result establishes only technical metadata reachability and "
                    "canonical source identity.",
                    "The GitHub raw response contains incidental current repository "
                    "fields that are outcome-aware and nonqualifying.",
                    "No commit, pull-request, release, or contributor history was "
                    "requested or parsed.",
                    "Current HEAD and tag hashes do not prove point-in-time historical "
                    "availability.",
                    "GitHub rate-limit headers are transient and do not guarantee future "
                    "payload completion.",
                    "No predictive relationship or profitable strategy was tested or established.",
                    "A PASS authorizes only a separately frozen history-payload protocol, "
                    "not payload access itself.",
                    "No BTC market value, parameter, return, candidate, signal, paper "
                    "order, Testnet strategy order, production action, live action, real "
                    "capital, or profit was created.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreSourceFeasibilityResult.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5BitcoinCoreSourceFeasibilityResult.model_validate(complete)


def load_protocol(protocol_path: Path, audit_path: Path) -> S5BitcoinCoreSourceFeasibilityProtocol:
    protocol = S5BitcoinCoreSourceFeasibilityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5BitcoinCoreSourceFeasibilityProtocolAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_s5_source_protocol(protocol)
        or not audit_s5_source_protocol_audit(audit)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
    ):
        raise ValueError("S5 protocol or audit failed before execution")
    return protocol


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S5 source feasibility once.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--response-dir", type=Path, default=DEFAULT_RESPONSE_DIR)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S5 result already exists; rerun forbidden: {args.output}")
        protocol = load_protocol(args.protocol, args.protocol_audit)
        attempts = planned_attempts()
        artifacts: list[S5RawArtifactRecord] = []
        repository: dict[str, Any] = {}
        headers: dict[str, str] = {}
        refs: tuple[S5GitRefRecord, ...] = ()

        http_attempt, http_artifact, repository, headers = run_repository_attempt(
            protocol=protocol, response_dir=args.response_dir
        )
        attempts[0] = http_attempt
        artifacts.append(http_artifact)

        git_attempt, git_artifact, refs = run_git_attempt(
            protocol=protocol, response_dir=args.response_dir
        )
        attempts[1] = git_attempt
        artifacts.append(git_artifact)

        result = build_result(
            protocol=protocol,
            attempts=tuple(attempts),
            artifacts=tuple(artifacts),
            repository=repository,
            headers=headers,
            refs=refs,
            executed_at=datetime.now(UTC),
        )
        write_result_atomic(args.output, result)
        print(
            f"RECORDED {args.output} {result.result_evidence_hash} "
            f"decision={result.decision} attempted={result.attempted_count} "
            f"succeeded={result.succeeded_count} gates="
            f"{result.passed_gate_count}/{len(result.gate_results)} history=0 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
