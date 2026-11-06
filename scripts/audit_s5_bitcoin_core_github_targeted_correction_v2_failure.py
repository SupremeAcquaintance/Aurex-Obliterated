from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_STOP,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_failure import (  # noqa: E402
    S5TargetedCorrectionV2FailureAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction as base,
)

DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_v2_failure_audit_v1.json"
)
FAILURE_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v2/failure_pull_000010.json"
)
ATTEMPT_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v2/pull_000010.attempt.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_v2_failure.py"
)
AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_targeted_correction_v2_failure.py"
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": base.file_sha256(PROJECT_ROOT / path),
            }
            for path in sorted((MODULE_PATH, AUDITOR_PATH), key=lambda item: item.as_posix())
        )
    )


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5TargetedCorrectionV2FailureAudit:
    result = S5TargetedCompletenessCorrectionResultV2.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    envelope = json.loads(FAILURE_PATH.read_text(encoding="utf-8"))
    response = envelope["response"]
    body = base64.b64decode(response["body_base64"], validate=True)
    payload = json.loads(body)
    expected_files = {FAILURE_PATH.name, ATTEMPT_PATH.name}
    actual_files = {path.name for path in FAILURE_PATH.parent.iterdir() if path.is_file()}
    changed = (
        result.decision != S5_TARGETED_CORRECTION_STOP
        or result.failure_type != "ResponseFailure"
        or result.failure_message != "GitHub targeted merge commit SHA is invalid"
        or result.logical_request_attempt_count != 1
        or len(result.response_bindings) != 0
        or result.failure_artifact_path != FAILURE_PATH.as_posix()
        or result.failure_artifact_sha256 != base.file_sha256(FAILURE_PATH)
        or actual_files != expected_files
        or envelope.get("schema_version")
        != "aurex-s5-github-targeted-pull-failure-v2"
        or envelope.get("pull_number") != 10
        or envelope.get("remedial_retry_of_v1_uncertain_get") is not True
        or response.get("http_status") != 200
        or response.get("final_url")
        != "https://api.github.com/repos/bitcoin/bitcoin/pulls/10"
        or response.get("redirect_count") != 0
        or response.get("body_byte_count") != len(body)
        or response.get("body_sha256") != hashlib.sha256(body).hexdigest()
        or envelope.get("error") != {"type": None, "message": None}
        or payload.get("number") != 10
        or payload.get("state") != "closed"
        or payload.get("merged") is not True
        or payload.get("merge_commit_sha") != ""
        or not isinstance(payload.get("head"), dict)
        or not base.SHA1_RE.fullmatch(str(payload["head"].get("sha", "")))
        or not isinstance(payload.get("base"), dict)
        or payload["base"].get("ref") != "master"
        or result.btc_market_values_read != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
    )
    if changed:
        raise ValueError("S5 targeted v2 schema failure evidence changed")
    fields = {
        "audited_at": audited_at,
        "result_file_sha256": base.file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "failure_artifact_file_sha256": base.file_sha256(FAILURE_PATH),
        "response_body_sha256": hashlib.sha256(body).hexdigest(),
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S5TargetedCorrectionV2FailureAudit.model_construct(
        **fields, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5TargetedCorrectionV2FailureAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5TargetedCorrectionV2FailureAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v2 failure audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v2 failure audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV2FailureAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 targeted v2 failure audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S5 targeted v2 schema stop.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCorrectionV2FailureAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted v2 failure audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
