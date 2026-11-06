from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (  # noqa: E402
    S5BitcoinCoreSourceFeasibilityProtocol,
    S5BitcoinCoreSourceFeasibilityResult,
    S5BitcoinCoreSourceFeasibilityResultAudit,
    audit_s5_source_protocol,
    audit_s5_source_result,
    audit_s5_source_result_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_source_feasibility import (  # noqa: E402
    MODULE_PATH,
    build_result,
    parse_git_refs,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json")
DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_source_feasibility_result.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def verify_raw_artifacts(result: S5BitcoinCoreSourceFeasibilityResult) -> None:
    attempts = {item.attempt_id: item for item in result.attempts}
    for artifact in result.raw_artifacts:
        path = Path(artifact.path)
        if file_sha256(path) != artifact.file_sha256 or path.stat().st_size != artifact.byte_count:
            raise ValueError(f"S5 raw artifact changed: {path}")
        attempt = attempts[artifact.attempt_id]
        if (
            attempt.raw_artifact_path != artifact.path
            or attempt.raw_artifact_sha256 != artifact.file_sha256
        ):
            raise ValueError("S5 attempt-to-artifact binding changed")


def reconstruct_result(
    *, protocol_path: Path, result_path: Path
) -> S5BitcoinCoreSourceFeasibilityResult:
    protocol = S5BitcoinCoreSourceFeasibilityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreSourceFeasibilityResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if not audit_s5_source_protocol(protocol) or not audit_s5_source_result(result):
        raise ValueError("S5 protocol or result evidence hash failed")
    if result.protocol_evidence_hash != protocol.protocol_evidence_hash:
        raise ValueError("S5 result protocol binding changed")
    if result.runner_contract_hash != runner_contract_hash():
        raise ValueError("S5 result runner source changed")
    verify_raw_artifacts(result)

    artifacts = {item.attempt_id: Path(item.path) for item in result.raw_artifacts}
    repository: dict[str, Any] = {}
    headers: dict[str, str] = {}
    if result.attempts[0].attempted:
        envelope = json.loads(
            artifacts["01_GITHUB_REPOSITORY_METADATA"].read_text(encoding="utf-8")
        )
        headers = {str(key): str(value) for key, value in envelope.get("headers", {}).items()}
        body = base64.b64decode(envelope["body_base64"], validate=True)
        if result.attempts[0].succeeded:
            payload = json.loads(body.decode("utf-8"))
            license_payload = payload.get("license") or {}
            repository = {
                "full_name": payload.get("full_name"),
                "private": payload.get("private"),
                "archived": payload.get("archived"),
                "disabled": payload.get("disabled"),
                "visibility": payload.get("visibility"),
                "default_branch": payload.get("default_branch"),
                "clone_url": payload.get("clone_url"),
                "license_spdx_id": license_payload.get("spdx_id"),
            }
    refs = ()
    if result.attempts[1].succeeded:
        refs = parse_git_refs(artifacts["02_GIT_REF_DISCOVERY"].read_bytes())
    expected = build_result(
        protocol=protocol,
        attempts=result.attempts,
        artifacts=result.raw_artifacts,
        repository=repository,
        headers=headers,
        refs=refs,
        executed_at=result.executed_at,
    )
    if result != expected:
        raise ValueError("S5 result differs from independent reconstruction")
    return result


def build_audit(
    *, protocol_path: Path, result_path: Path, audited_at: datetime
) -> S5BitcoinCoreSourceFeasibilityResultAudit:
    result = reconstruct_result(protocol_path=protocol_path, result_path=result_path)
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "attempted_count": result.attempted_count,
        "succeeded_count": result.succeeded_count,
        "passed_gate_count": result.passed_gate_count,
        "failed_gate_count": result.failed_gate_count,
        "next_authorization": result.next_authorization,
    }
    provisional = S5BitcoinCoreSourceFeasibilityResultAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5BitcoinCoreSourceFeasibilityResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5BitcoinCoreSourceFeasibilityResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 result audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreSourceFeasibilityResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 source result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen S5 source result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreSourceFeasibilityResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_s5_source_result_audit(stored):
                raise ValueError("Stored S5 result audit differs from reconstruction")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            protocol_path=args.protocol,
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"attempted={audit.attempted_count} succeeded={audit.succeeded_count} "
            f"gates={audit.passed_gate_count}/14 history=0 market_values=0 "
            "returns=0 orders=0"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
