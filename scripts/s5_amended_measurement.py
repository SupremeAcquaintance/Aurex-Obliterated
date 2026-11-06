from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_accepted_development_measurement_execution import (  # noqa: E402
    S5StableReleaseTagRecord,
)
from aurex.backtest_engine.s5_complete_release_tag_source_remediation import (  # noqa: E402
    S5CompleteReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_complete_release_tag_source_remediation_result_audit import (  # noqa: E402
    S5CompleteReleaseRemediationResultAuditV1,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import run_s5_accepted_development_measurements as original  # noqa: E402
from scripts.audit_s5_complete_release_tag_source_remediation_result import (  # noqa: E402
    build_audit as audit_source,
)
from scripts.audit_s5_complete_release_tag_source_remediation_result import (  # noqa: E402
    complete_manifest,
)
from scripts.run_s5_complete_release_tag_source_remediation import (  # noqa: E402
    git_environment,
)

EVIDENCE = PROJECT_ROOT / "data/evidence"
PROTOCOL = EVIDENCE / "s5_amended_measurement_protocol_v2.json"
PROTOCOL_AUDIT = EVIDENCE / "s5_amended_measurement_protocol_audit_v2.json"
CONTRACT = EVIDENCE / "s5_amended_measurement_execution_v2.json"
CONTRACT_AUDIT = EVIDENCE / "s5_amended_measurement_execution_audit_v2.json"
ATTEMPT = EVIDENCE / "s5_amended_measurement_attempt_v2.json"
RESULT = EVIDENCE / "s5_amended_measurement_result_v2.json"
ROWS = EVIDENCE / "s5_accepted_development_monthly_measurements_v2.jsonl"
TAGS = EVIDENCE / "s5_amended_measurement_release_tags_v2.jsonl"
RESPONSES = EVIDENCE / "s5_amended_measurement_responses_v2"
SOURCE_PROTOCOL = EVIDENCE / "s5_complete_release_tag_source_remediation_protocol_v1.json"
SOURCE_RESULT = EVIDENCE / "s5_complete_release_tag_source_remediation_result_v1.json"
SOURCE_AUDIT = EVIDENCE / "s5_complete_release_tag_source_remediation_result_audit_v1.json"
AUDIT = EVIDENCE / "s5_amended_measurement_result_audit_v2.json"
IMPLEMENTATION = (
    "scripts/s5_amended_measurement.py",
    "scripts/audit_s5_amended_measurement.py",
    "scripts/run_s5_accepted_development_measurements.py",
    "scripts/run_s5_complete_release_tag_source_remediation.py",
    "scripts/audit_s5_complete_release_tag_source_remediation_result.py",
    "src/aurex/backtest_engine/s5_accepted_development_measurement_execution.py",
    "src/aurex/backtest_engine/s5_accepted_development_measurement_protocol.py",
    "src/aurex/backtest_engine/s5_complete_release_tag_source_remediation.py",
    "src/aurex/backtest_engine/s5_complete_release_tag_source_remediation_execution.py",
    "src/aurex/backtest_engine/s5_complete_release_tag_source_remediation_result_audit.py",
    "src/aurex/backtest_engine/s5_bitcoin_core_github_corrected_normalization_execution.py",
    "src/aurex/backtest_engine/s5_bitcoin_core_github_normalization_execution.py",
    "src/aurex/backtest_engine/s5_bitcoin_core_history_payload.py",
    "src/aurex/backtest_engine/s5_release_tag_source_remediation_execution.py",
    "src/aurex/backtest_engine/universe.py",
)
AUTHORITY = {
    "network": False,
    "market_values": False,
    "returns": False,
    "signals": False,
    "paper": False,
    "testnet_strategy_orders": False,
    "production": False,
    "live": False,
}
RELEASE_FIELDS = frozenset(
    {
        "stable_release_tag_count",
        "signed_annotated_stable_release_tag_count",
        "release_tag_manifest_evidence_hash",
    }
)


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def sealed(payload: dict) -> dict:
    value = json.loads(json.dumps(payload))
    value["evidence_hash"] = universe_evidence_hash(value)
    return value


def read_sealed(path: Path) -> dict:
    payload = read_json(path)
    content = {key: value for key, value in payload.items() if key != "evidence_hash"}
    if payload != sealed(content):
        raise ValueError(f"Evidence hash mismatch: {relative(path)}")
    return payload


def write_once(path: Path, payload: bytes) -> None:
    partial = path.with_name(path.name + ".part")
    if path.exists() or partial.exists():
        raise ValueError(f"Evidence already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    # On Windows rename refuses an existing destination; never replace evidence.
    partial.rename(path)


def write_json(path: Path, payload: dict) -> None:
    write_once(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())


def bindings(paths) -> list[dict]:
    return [{"path": relative(path), "sha256": file_hash(path)} for path in sorted(set(paths))]


def check_bindings(records: list[dict]) -> None:
    for record in records:
        path = PROJECT_ROOT / record["path"]
        if file_hash(path) != record["sha256"]:
            raise ValueError(f"Bound file changed: {record['path']}")


def old_authorization():
    return original.load_authorization(
        protocol_path=PROJECT_ROOT / original.DEFAULT_PROTOCOL,
        protocol_audit_path=PROJECT_ROOT / original.DEFAULT_PROTOCOL_AUDIT,
        contract_path=PROJECT_ROOT / original.DEFAULT_CONTRACT,
        contract_audit_path=PROJECT_ROOT / original.DEFAULT_CONTRACT_AUDIT,
    )


def build_protocol(frozen_at: str) -> dict:
    old, _, execution, _ = old_authorization()
    source = S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate_json(
        SOURCE_PROTOCOL.read_text(encoding="utf-8")
    )
    audit = S5CompleteReleaseRemediationResultAuditV1.model_validate_json(
        SOURCE_AUDIT.read_text(encoding="utf-8")
    )
    if audit_source(result_path=SOURCE_RESULT, audited_at=audit.audited_at) != audit:
        raise ValueError("Complete source audit no longer reconstructs")
    sources = [
        PROJECT_ROOT / original.DEFAULT_PROTOCOL,
        PROJECT_ROOT / original.DEFAULT_PROTOCOL_AUDIT,
        PROJECT_ROOT / original.DEFAULT_CONTRACT,
        PROJECT_ROOT / original.DEFAULT_CONTRACT_AUDIT,
        PROJECT_ROOT / original.DEFAULT_OUTPUT,
        PROJECT_ROOT / original.DEFAULT_RESULT,
        EVIDENCE / "s5_accepted_development_measurement_result_audit_v1.json",
        SOURCE_PROTOCOL,
        SOURCE_RESULT,
        SOURCE_AUDIT,
        *(PROJECT_ROOT / item.path for item in old.source_bindings),
    ]
    return sealed(
        {
            "schema": "aurex-s5-amended-measurement-protocol-v2",
            "frozen_at": frozen_at,
            "source_bindings": bindings(sources),
            "original_protocol_hash": old.protocol_evidence_hash,
            "complete_source_audit_hash": audit.audit_evidence_hash,
            "complete_manifest_hash": source.complete_stable_tag_manifest_evidence_hash,
            "original_repository": old.history_dataset_path,
            "original_repository_hash": old.history_dataset_directory_sha256,
            "complete_repository": source.destination_history_dataset_path,
            "complete_repository_hash": audit.complete_repository_directory_sha256,
            "month_start": "2009-01-01",
            "month_end_exclusive": "2026-09-01",
            "month_count": 212,
            "availability_lag_days": 7,
            "stable_tag_count": 132,
            "annotated_count": 104,
            "lightweight_count": 28,
            "release_policy": {
                "annotated": "TAGGER_TIME_NO_MASTER_ANCESTRY_REQUIREMENT",
                "lightweight": "COMMITTER_TIME_CUTOFF_REACHABLE_HISTORICAL_EXISTENCE_UNCERTAIN",
                "window": "START_INCLUSIVE_END_EXCLUSIVE_UTC",
                "signature": "PRESENCE_ONLY_NOT_CRYPTOGRAPHIC_VERIFICATION",
                "complete_inventory_preserved": True,
            },
            "non_release_policy": "RECONSTRUCT_ALL_FIELDS_AND_REQUIRE_EXACT_V1_EQUALITY",
            "historical_qualification_permitted": False,
            "raw_commands": [
                list(execution.first_parent_diff_command),
                list(execution.reachable_commit_command),
                list(execution.tag_inventory_command),
            ],
            "command_repositories": [
                old.history_dataset_path,
                old.history_dataset_path,
                source.destination_history_dataset_path,
            ],
            "source_cutoff_commit": old.source_cutoff_commit,
            "maximum_process_seconds": 600,
            "maximum_total_seconds": 1800,
            "maximum_stdout_bytes": 536_870_912,
            "maximum_output_bytes": 16_777_216,
            "process_count": 3,
            "retry_count": 0,
            "serialization": "SORTED_KEYS_COMPACT_ASCII_JSON_LINES_LF",
            "output_path": relative(ROWS),
            "tag_path": relative(TAGS),
            "result_path": relative(RESULT),
            "attempt_path": relative(ATTEMPT),
            "response_directory": relative(RESPONSES),
            "authority": AUTHORITY,
            "next_action": "FREEZE_AND_CHECK_S5_AMENDED_MEASUREMENT_EXECUTION",
        }
    )


def check_protocol() -> dict:
    protocol = read_sealed(PROTOCOL)
    if protocol != build_protocol(protocol["frozen_at"]):
        raise ValueError("Amended protocol no longer reconstructs")
    return protocol


def protocol_audit(protocol: dict) -> dict:
    return sealed(
        {
            "schema": "aurex-s5-amended-measurement-protocol-audit-v2",
            "protocol_hash": protocol["evidence_hash"],
            "protocol_file_hash": file_hash(PROTOCOL),
            "reconstructed": True,
            "processes": 0,
            "authority": AUTHORITY,
        }
    )


def build_contract(frozen_at: str) -> dict:
    protocol = check_protocol()
    if read_sealed(PROTOCOL_AUDIT) != protocol_audit(protocol):
        raise ValueError("Protocol audit mismatch")
    return sealed(
        {
            "schema": "aurex-s5-amended-measurement-execution-v2",
            "frozen_at": frozen_at,
            "protocol_hash": protocol["evidence_hash"],
            "protocol_audit_hash": read_sealed(PROTOCOL_AUDIT)["evidence_hash"],
            "implementation_bindings": bindings(PROJECT_ROOT / path for path in IMPLEMENTATION),
            "process_count": 3,
            "single_run": True,
            "persist_raw_outputs": True,
            "reserve_attempt_before_processes": True,
            "failure_consumes_attempt": True,
            "disable_lazy_fetch_and_all_network_protocols": True,
            "authority": AUTHORITY,
            "next_action": "RUN_S5_AMENDED_MEASUREMENT_ONCE",
        }
    )


def check_contract() -> dict:
    contract = read_sealed(CONTRACT)
    if contract != build_contract(contract["frozen_at"]):
        raise ValueError("Amended execution no longer reconstructs")
    return contract


def execution_audit(contract: dict) -> dict:
    return sealed(
        {
            "schema": "aurex-s5-amended-measurement-execution-audit-v2",
            "contract_hash": contract["evidence_hash"],
            "contract_file_hash": file_hash(CONTRACT),
            "reconstructed": True,
            "processes": 0,
            "authority": AUTHORITY,
        }
    )


def source_manifest():
    protocol = S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate_json(
        SOURCE_PROTOCOL.read_text(encoding="utf-8")
    )
    return complete_manifest(protocol)


def parse_release_inventory(payload: bytes, manifest, reachable) -> tuple:
    expected = {item.ref_name: item for item in manifest}
    seen = set()
    records = []
    for chunk in payload.split(b"\x1e"):
        chunk = chunk.strip(b"\r\n")
        if not chunk:
            continue
        if not chunk.endswith(b"\x00"):
            raise ValueError("Release record lacks terminator")
        fields = chunk[:-1].split(b"\x00")
        if len(fields) != 7:
            raise ValueError("Release inventory framing changed")
        ref, kind, object_sha, peeled, tagger_at, creator_at = (
            value.decode("ascii") for value in fields[:6]
        )
        identity = expected.get(ref)
        if ref in seen or identity is None:
            raise ValueError("Duplicate or unexpected release ref")
        seen.add(ref)
        annotated = identity.tag_type == "ANNOTATED"
        if (kind, object_sha, peeled) != (
            "tag" if annotated else "commit",
            identity.object_sha,
            identity.peeled_commit_sha if annotated else "",
        ):
            raise ValueError("Release identity drift")
        if not annotated and identity.peeled_commit_sha not in reachable:
            raise ValueError("Lightweight tag is outside cutoff history")
        event_at = original.parse_git_datetime(tagger_at if annotated else creator_at)
        signature = (
            (
                "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"
                if fields[6]
                else "ANNOTATED_UNSIGNED"
            )
            if annotated
            else "LIGHTWEIGHT_UNVERIFIED"
        )
        records.append(
            S5StableReleaseTagRecord(
                ref_name=ref,
                object_type=kind,
                object_sha=object_sha,
                peeled_commit_sha=identity.peeled_commit_sha,
                event_at=event_at,
                event_time_source="ANNOTATED_TAGGER_AT"
                if annotated
                else "LIGHTWEIGHT_COMMITTER_AT",
                signature_state=signature,
            )
        )
    if seen != set(expected):
        raise ValueError("Release inventory incomplete")
    return tuple(sorted(records, key=lambda row: row.ref_name))


def load_inputs(protocol):
    models = (
        original.S5GitHubNormalizedPull,
        original.S5CorrectedCanonicalMappingRow,
        original.S5CorrectedTargetResolutionRow,
        original.S5CorrectedAcceptedCoverageRow,
        original.S5CorrectedUnresolvedMergeRow,
    )
    if tuple(file_hash(PROJECT_ROOT / p) for p in protocol.input_paths) != (
        protocol.input_file_sha256s
    ):
        raise ValueError("Measurement source hash mismatch")
    groups = tuple(
        original.load_jsonl(PROJECT_ROOT / p, model)
        for p, model in zip(protocol.input_paths, models, strict=True)
    )
    if (
        tuple(len(group) for group in groups) != protocol.input_row_counts
        or tuple(original.row_manifest_hash(group) for group in groups)
        != protocol.input_row_manifest_evidence_hashes
    ):
        raise ValueError("Measurement source rows mismatch")
    return groups


def serialize_tags(tags) -> bytes:
    return b"".join(
        (
            json.dumps(tag.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        for tag in tags
    )


def compare_non_release(rows, previous) -> None:
    if len(rows) != len(previous):
        raise ValueError("Monthly row count changed")
    for row, before in zip(rows, previous, strict=True):
        if row.model_dump(exclude=RELEASE_FIELDS) != before.model_dump(exclude=RELEASE_FIELDS):
            raise ValueError(f"Non-release measurement changed: {row.month_start}")


def command_for(protocol: dict, index: int) -> tuple[str, ...]:
    replacements = {
        "{history_dataset_path}": str(PROJECT_ROOT / protocol["command_repositories"][index]),
        "{source_cutoff_commit}": protocol["source_cutoff_commit"],
    }
    return tuple(replacements.get(token, token) for token in protocol["raw_commands"][index])


def run_local(protocol: dict, index: int, deadline: float) -> bytes:
    command = command_for(protocol, index)
    environment = git_environment(safe_directory=Path(command[2]))
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CONFIG_PARAMETERS",
        "GIT_SHALLOW_FILE",
    ):
        environment.pop(key, None)
    environment.update(
        {"GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": "", "GIT_NO_REPLACE_OBJECTS": "1"}
    )
    started = datetime.now(UTC).isoformat()
    timeout = min(protocol["maximum_process_seconds"], deadline - time.monotonic())
    if timeout <= 0:
        raise ValueError("Measurement total time ceiling reached")
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", 124
    except OSError as exc:
        stdout, stderr, code = b"", str(exc).encode(), 125
    output = RESPONSES / f"{index + 1:02d}.stdout"
    error = RESPONSES / f"{index + 1:02d}.stderr"
    write_once(output, stdout)
    write_once(error, stderr)
    write_json(
        RESPONSES / f"{index + 1:02d}.json",
        sealed(
            {
                "sequence": index + 1,
                "command": list(command),
                "started_at": started,
                "completed_at": datetime.now(UTC).isoformat(),
                "return_code": code,
                "stdout_sha256": file_hash(output),
                "stderr_sha256": file_hash(error),
                "stdout_bytes": len(stdout),
                "stderr_bytes": len(stderr),
                "network": False,
            }
        ),
    )
    if code != 0 or max(len(stdout), len(stderr)) > protocol["maximum_stdout_bytes"]:
        raise ValueError(f"Local Git process {index + 1} failed or exceeded its byte ceiling")
    return stdout


def run_measurement() -> dict:
    protocol = check_protocol()
    contract = check_contract()
    if read_sealed(CONTRACT_AUDIT) != execution_audit(contract):
        raise ValueError("Execution audit mismatch")
    for path in (ATTEMPT, RESULT, ROWS, TAGS, RESPONSES):
        if path.exists() or path.with_name(path.name + ".part").exists():
            raise ValueError(f"Measurement run already consumed: {path.name}")
    started = datetime.now(UTC)
    deadline = time.monotonic() + protocol["maximum_total_seconds"]
    write_json(
        ATTEMPT,
        sealed(
            {
                "started_at": started.isoformat(),
                "contract_hash": contract["evidence_hash"],
                "single_attempt_reserved": True,
            }
        ),
    )
    outcome = {
        "schema": "aurex-s5-amended-measurement-result-v2",
        "started_at": started.isoformat(),
        "protocol_hash": protocol["evidence_hash"],
        "contract_hash": contract["evidence_hash"],
        "authority": AUTHORITY,
        "historical_qualification_permitted": False,
        "process_count": 0,
    }
    try:
        old, *_ = old_authorization()
        pulls, canonical, _targets, coverage, unresolved = load_inputs(old)
        payloads = []
        for index in range(3):
            outcome["process_count"] += 1
            payloads.append(run_local(protocol, index, deadline))
        diff = original.parse_first_parent_diff_stream(payloads[0])
        reachable = original.parse_reachable_commits(payloads[1])
        if len(reachable) != 50_395 or old.source_cutoff_commit not in reachable:
            raise ValueError("Reachable history changed")
        tags = parse_release_inventory(payloads[2], source_manifest(), reachable)
        rows, excluded = original.build_measurements(
            protocol=old,
            pulls=pulls,
            canonical_rows=canonical,
            coverage_rows=coverage,
            unresolved_rows=unresolved,
            diff_records=diff,
            release_tags=tags,
        )
        previous = original.load_jsonl(
            PROJECT_ROOT / original.DEFAULT_OUTPUT,
            original.S5AcceptedDevelopmentMonthlyMeasurementRow,
        )
        compare_non_release(rows, previous)
        in_window = [
            tag
            for tag in tags
            if old.measurement_period_start_month
            <= tag.event_at.date()
            < old.measurement_period_end_exclusive
        ]
        if len(rows) != 212 or sum(row.stable_release_tag_count for row in rows) != len(in_window):
            raise ValueError("Monthly release accounting failed")
        for key, field, total in (
            ("primary", "primary_source_verified_accepted_pull_count", 16_271),
            ("all_accepted", "all_accepted_pull_count", 16_279),
            ("canonical", "canonical_integration_count", 16_242),
            ("unresolved", "unresolved_git_merge_count", 479),
        ):
            if sum(getattr(row, field) for row in rows) + excluded.get(key, 0) != total:
                raise ValueError(f"Event conservation failed: {key}")
        check_bindings(protocol["source_bindings"])
        for prefix in ("original", "complete"):
            if (
                original.dataset_manifest_hash(PROJECT_ROOT / protocol[f"{prefix}_repository"])
                != (protocol[f"{prefix}_repository_hash"])
            ):
                raise ValueError("Repository changed during measurement")
        row_payload, tag_payload = original.serialize_rows(rows), serialize_tags(tags)
        if max(len(row_payload), len(tag_payload)) > protocol["maximum_output_bytes"]:
            raise ValueError("Measurement output ceiling exceeded")
        if time.monotonic() > deadline:
            raise ValueError("Measurement total time ceiling reached")
        write_once(ROWS, row_payload)
        write_once(TAGS, tag_payload)
        outcome.update(
            {
                "decision": "PASS_S5_AMENDED_MEASUREMENT_PENDING_INDEPENDENT_AUDIT",
                "next_action": "AUDIT_S5_AMENDED_MEASUREMENT_RESULT",
                "output_sha256": file_hash(ROWS),
                "tags_sha256": file_hash(TAGS),
                "row_count": len(rows),
                "inventory_count": len(tags),
                "included_release_count": len(in_window),
                "excluded_release_count": len(tags) - len(in_window),
                "annotated_count": sum(tag.object_type == "tag" for tag in tags),
                "lightweight_count": sum(tag.object_type == "commit" for tag in tags),
                "non_release_fields_match_v1": True,
                "excluded_events": excluded,
                "transcript_bindings": bindings(RESPONSES.iterdir()),
            }
        )
    except Exception as exc:  # noqa: BLE001 - preserve a consumed attempt and its failure
        outcome.update(
            {
                "decision": "STOP_S5_AMENDED_MEASUREMENT",
                "next_action": "REVIEW_PRESERVED_FAILURE",
                "failure_type": type(exc).__name__,
                "failure": str(exc)[:1500],
            }
        )
    outcome["completed_at"] = datetime.now(UTC).isoformat()
    result = sealed(outcome)
    write_json(RESULT, result)
    return result


def record_check(path: Path, expected: dict) -> dict:
    if path.exists():
        if read_sealed(path) != expected:
            raise ValueError(f"Audit changed: {path.name}")
    else:
        write_json(path, expected)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded S5 measurement correction, no market access."
    )
    parser.add_argument(
        "action",
        choices=("freeze-protocol", "check-protocol", "freeze-execution", "check-execution", "run"),
    )
    args = parser.parse_args()
    try:
        now = datetime.now(UTC).isoformat()
        if args.action == "freeze-protocol":
            value = build_protocol(now)
            write_json(PROTOCOL, value)
        elif args.action == "check-protocol":
            value = record_check(PROTOCOL_AUDIT, protocol_audit(check_protocol()))
        elif args.action == "freeze-execution":
            value = build_contract(now)
            write_json(CONTRACT, value)
        elif args.action == "check-execution":
            value = record_check(CONTRACT_AUDIT, execution_audit(check_contract()))
        else:
            value = run_measurement()
        print(json.dumps({key: value[key] for key in (
            "evidence_hash", "decision", "next_action", "row_count", "inventory_count",
            "included_release_count", "excluded_release_count", "failure",
        ) if key in value}, indent=2))
        return 1 if value.get("decision", "").startswith("STOP") else 0
    except (ValueError, OSError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
