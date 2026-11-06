from __future__ import annotations

import argparse
import base64
import re
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (  # noqa: E402
    S5ReleaseTagSourceRemediationProtocolAuditV1,
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
    S5_RELEASE_REMEDIATION_PASS,
    S5_RELEASE_REMEDIATION_RESULT_NEXT,
    S5ReleaseTagDiscoveryRecord,
    S5ReleaseTagProcessTranscript,
    S5ReleaseTagSourceRemediationExecutionContractAuditV1,
    S5ReleaseTagSourceRemediationExecutionContractV1,
    S5ReleaseTagSourceRemediationResultV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_result_audit import (  # noqa: E402
    S5_RELEASE_RESULT_AUDIT_NEXT,
    S5_RELEASE_RESULT_AUDIT_REJECT,
    S5ReleaseTagSourceRemediationResultAuditV1,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_release_tag_source_remediation_result_v1.json"
)
DEFAULT_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_result_audit_v1.json"
)
AUDIT_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_release_tag_source_remediation_result_audit.py"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_hashed[ModelT: BaseModel](
    model: type[ModelT],
    hash_field: str,
    values: dict,
) -> ModelT:
    payload = dict(values)
    payload[hash_field] = "0" * 64
    preliminary = model.model_construct(**payload)
    payload[hash_field] = universe_evidence_hash(
        preliminary.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def auditor_contract_bindings() -> tuple[S5HistoryBinding, ...]:
    paths = tuple(
        sorted(
            (AUDIT_MODULE_PATH, Path(__file__).resolve().relative_to(PROJECT_ROOT)),
            key=lambda path: path.as_posix(),
        )
    )
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def bindings_match(bindings: tuple[S5HistoryBinding, ...]) -> bool:
    return all(
        (PROJECT_ROOT / binding.path).is_file()
        and file_sha256(PROJECT_ROOT / binding.path) == binding.file_sha256
        for binding in bindings
    )


def directory_manifest_hash(path: Path) -> str:
    records: list[dict] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError(f"S5 release audit found a symbolic link: {candidate}")
        if candidate.is_file():
            records.append(
                {
                    "relative_path": candidate.relative_to(path).as_posix(),
                    "file_sha256": file_sha256(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    if not records:
        raise ValueError(f"S5 release audit repository is empty: {path}")
    return universe_evidence_hash(records)


def parse_remote_records(payload: bytes) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in payload.splitlines():
        fields = line.split(b"\t")
        if len(fields) != 2:
            raise ValueError("S5 release audit remote transcript framing changed")
        object_sha = fields[0].decode("ascii")
        ref_name = fields[1].decode("utf-8")
        if (
            not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or not ref_name.startswith("refs/tags/")
            or ref_name in records
        ):
            raise ValueError("S5 release audit remote identity changed")
        records[ref_name] = object_sha
    return records


def parse_reachable_records(payload: bytes) -> frozenset[str]:
    commits = tuple(payload.decode("ascii").splitlines())
    if (
        not commits
        or any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in commits)
        or len(commits) != len(set(commits))
    ):
        raise ValueError("S5 release audit reachable transcript changed")
    return frozenset(commits)


def classify_stable_coverage(
    remote: dict[str, str],
    *,
    stable_regex: str,
    reachable: frozenset[str],
) -> tuple[
    tuple[S5ReleaseTagDiscoveryRecord, ...],
    tuple[tuple[str, str], ...],
]:
    pattern = re.compile(stable_regex)
    stable_refs = tuple(sorted(ref_name for ref_name in remote if pattern.fullmatch(ref_name)))
    admitted: list[S5ReleaseTagDiscoveryRecord] = []
    omitted: list[tuple[str, str]] = []
    for ref_name in stable_refs:
        object_sha = remote[ref_name]
        peeled_sha = remote.get(f"{ref_name}^{{}}")
        if peeled_sha is not None:
            tag_type = "ANNOTATED"
            target_sha = peeled_sha
        else:
            tag_type = "LIGHTWEIGHT"
            target_sha = object_sha
        if target_sha not in reachable:
            omitted.append((ref_name, tag_type))
            continue
        admitted.append(
            S5ReleaseTagDiscoveryRecord(
                ref_name=ref_name,
                object_sha=object_sha,
                peeled_commit_sha=target_sha,
                tag_type=tag_type,
                fetch_refspec=f"+{ref_name}:{ref_name}",
            )
        )
    return tuple(admitted), tuple(omitted)


def parse_verified_records(payload: bytes) -> dict[str, tuple[str, str, str]]:
    records: dict[str, tuple[str, str, str]] = {}
    for raw_record in payload.split(b"\x1e"):
        record = raw_record.strip(b"\r\n")
        if record.endswith(b"\x00"):
            record = record[:-1]
        if not record:
            continue
        fields = record.split(b"\x00")
        if len(fields) != 4:
            raise ValueError("S5 release audit verification framing changed")
        ref_name, object_type, object_sha, peeled_sha = (
            item.decode("ascii") for item in fields
        )
        if (
            ref_name in records
            or object_type not in {"tag", "commit"}
            or not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or (peeled_sha and not re.fullmatch(r"[0-9a-f]{40}", peeled_sha))
        ):
            raise ValueError("S5 release audit verified identity changed")
        records[ref_name] = (object_type, object_sha, peeled_sha)
    return records


def identity_drift_count(
    admitted: tuple[S5ReleaseTagDiscoveryRecord, ...],
    verified: dict[str, tuple[str, str, str]],
) -> int:
    expected_refs = {item.ref_name for item in admitted}
    drift = len(expected_refs.symmetric_difference(verified))
    for item in admitted:
        expected = (
            "tag" if item.tag_type == "ANNOTATED" else "commit",
            item.object_sha,
            item.peeled_commit_sha if item.tag_type == "ANNOTATED" else "",
        )
        if item.ref_name in verified and verified[item.ref_name] != expected:
            drift += 1
    return drift


def expanded_command(
    template: tuple[str, ...],
    *,
    protocol: S5ReleaseTagSourceRemediationProtocolV1,
) -> tuple[str, ...]:
    replacements = {
        "{original_history_dataset_path}": str(
            PROJECT_ROOT / protocol.original_history_dataset_path
        ),
        "{destination_history_dataset_path}": str(
            PROJECT_ROOT / protocol.destination_history_dataset_path
        ),
        "{source_cutoff_commit}": protocol.source_cutoff_commit,
    }
    return tuple(replacements.get(token, token) for token in template)


def load_transcripts(
    result: S5ReleaseTagSourceRemediationResultV1,
) -> tuple[S5ReleaseTagProcessTranscript, ...]:
    transcripts: list[S5ReleaseTagProcessTranscript] = []
    for path_text, expected_hash in zip(
        result.transcript_paths,
        result.transcript_file_sha256s,
        strict=True,
    ):
        path = PROJECT_ROOT / path_text
        if file_sha256(path) != expected_hash:
            raise ValueError("S5 release audit transcript file hash changed")
        transcripts.append(
            S5ReleaseTagProcessTranscript.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        )
    if any(item.return_code != 0 for item in transcripts):
        raise ValueError("S5 release audit found a failed stored process")
    return tuple(transcripts)


def build_audit(
    *,
    result_path: Path,
    audited_at: datetime,
) -> S5ReleaseTagSourceRemediationResultAuditV1:
    protocol = S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_PROTOCOL).read_text(encoding="utf-8")
    )
    protocol_audit = S5ReleaseTagSourceRemediationProtocolAuditV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_PROTOCOL_AUDIT).read_text(encoding="utf-8")
    )
    contract = S5ReleaseTagSourceRemediationExecutionContractV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_CONTRACT).read_text(encoding="utf-8")
    )
    contract_audit = (
        S5ReleaseTagSourceRemediationExecutionContractAuditV1.model_validate_json(
            (PROJECT_ROOT / DEFAULT_CONTRACT_AUDIT).read_text(encoding="utf-8")
        )
    )
    result = S5ReleaseTagSourceRemediationResultV1.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.execution_contract_audit_evidence_hash
        != contract_audit.audit_evidence_hash
        or result.runner_contract_hash != contract.runner_contract_hash
        or result.decision != S5_RELEASE_REMEDIATION_PASS
        or result.next_authorization != S5_RELEASE_REMEDIATION_RESULT_NEXT
        or not result.authorizes_amended_measurement_protocol
        or not bindings_match(protocol.source_bindings)
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or not bindings_match(contract_audit.auditor_implementation_bindings)
    ):
        raise ValueError("S5 release audit result or predecessor lineage changed")

    transcripts = load_transcripts(result)
    expected_paths = (
        protocol.discovery_transcript_path,
        protocol.reachability_transcript_path,
        protocol.fetch_transcript_path,
        protocol.verification_transcript_path,
    )
    if result.transcript_paths != expected_paths:
        raise ValueError("S5 release audit transcript path sequence changed")
    outputs = tuple(base64.b64decode(item.stdout_base64, validate=True) for item in transcripts)
    remote = parse_remote_records(outputs[0])
    reachable = parse_reachable_records(outputs[1])
    admitted, omitted = classify_stable_coverage(
        remote,
        stable_regex=protocol.stable_release_tag_regex,
        reachable=reachable,
    )
    verified = parse_verified_records(outputs[3])
    admitted_manifest_hash = universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in admitted)
    )
    drift = identity_drift_count(admitted, verified)
    expected_commands = (
        protocol.discovery_command,
        expanded_command(protocol.reachable_commit_command, protocol=protocol),
        expanded_command(protocol.fetch_command_prefix, protocol=protocol)
        + tuple(item.fetch_refspec for item in admitted),
        expanded_command(protocol.verification_command, protocol=protocol),
    )
    if tuple(item.command for item in transcripts) != expected_commands:
        raise ValueError("S5 release audit stored Git command changed")
    annotated_admitted = sum(item.tag_type == "ANNOTATED" for item in admitted)
    lightweight_admitted = len(admitted) - annotated_admitted
    annotated_omitted = sum(tag_type == "ANNOTATED" for _, tag_type in omitted)
    lightweight_omitted = len(omitted) - annotated_omitted
    stable_count = len(admitted) + len(omitted)
    if (
        len(remote) != result.remote_tag_ref_record_count
        or len(reachable) != result.reachable_commit_count
        or len(admitted) != result.selected_stable_tag_count
        or annotated_admitted != result.selected_annotated_tag_count
        or lightweight_admitted != result.selected_lightweight_tag_count
        or admitted_manifest_hash != result.selected_tag_manifest_evidence_hash
        or len(verified) != result.verified_tag_count
        or drift != result.remote_ref_drift_count
        or stable_count != 132
        or len(omitted) != 90
        or annotated_omitted != 90
        or lightweight_omitted != 0
    ):
        raise ValueError("S5 release audit coverage accounting changed")
    original_hash = directory_manifest_hash(
        PROJECT_ROOT / protocol.original_history_dataset_path
    )
    remediated_hash = directory_manifest_hash(
        PROJECT_ROOT / protocol.destination_history_dataset_path
    )
    if (
        original_hash != result.original_history_dataset_directory_sha256
        or remediated_hash != result.destination_final_directory_sha256
    ):
        raise ValueError("S5 release audit repository manifest changed")
    auditor_bindings = auditor_contract_bindings()
    return build_hashed(
        S5ReleaseTagSourceRemediationResultAuditV1,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "result_file_sha256": file_sha256(result_path),
            "result_evidence_hash": result.result_evidence_hash,
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "execution_contract_evidence_hash": contract.contract_evidence_hash,
            "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
            "runner_contract_hash": contract.runner_contract_hash,
            "auditor_implementation_bindings": auditor_bindings,
            "auditor_contract_hash": universe_evidence_hash(
                tuple(item.model_dump(mode="json") for item in auditor_bindings)
            ),
            "transcript_paths": result.transcript_paths,
            "transcript_file_sha256s": result.transcript_file_sha256s,
            "transcript_evidence_hashes": tuple(
                item.transcript_evidence_hash for item in transcripts
            ),
            "admitted_tag_manifest_evidence_hash": admitted_manifest_hash,
            "original_repository_directory_sha256": original_hash,
            "remediated_repository_directory_sha256": remediated_hash,
            "limitations": tuple(
                sorted(
                    (
                        "All 42 fetched refs and object identities are internally valid.",
                        (
                            "Ancestor reachability is not a valid completeness rule "
                            "for release branches."
                        ),
                        "Ninety annotated stable-name refs were excluded by the frozen policy.",
                        "The nominal remediation PASS is rejected for measurement use.",
                        "The original and remediated repositories remain immutable evidence.",
                        "A new additive remediation must preserve all prior artifacts.",
                        "No Git process or network request was executed during this audit.",
                        "No market value, return, strategy, signal, or order was created.",
                        "Qualified strategies and real net profit remain zero.",
                        "Production and live trading remain prohibited.",
                    )
                )
            ),
        },
    )


def write_audit(
    path: Path,
    audit: S5ReleaseTagSourceRemediationResultAuditV1,
) -> None:
    if path.exists():
        raise ValueError(f"S5 release result audit already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5ReleaseTagSourceRemediationResultAuditV1.model_validate_json(serialized) != audit:
        raise ValueError("S5 release result audit did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the S5 release-tag source remediation result."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = S5ReleaseTagSourceRemediationResultAuditV1.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected:
                raise ValueError("Stored S5 release remediation result audit changed")
            print(f"PASS {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"{S5_RELEASE_RESULT_AUDIT_REJECT} {args.output} "
            f"{audit.audit_evidence_hash} remote_stable=132 admitted=42 "
            "omitted_annotated=90 git_processes=0 network=0 market_values=0 "
            f"next={S5_RELEASE_RESULT_AUDIT_NEXT}",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
