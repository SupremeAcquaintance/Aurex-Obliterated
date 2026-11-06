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
from aurex.backtest_engine.s5_complete_release_tag_source_remediation import (  # noqa: E402
    S5CompleteReleaseTagSourceRemediationProtocolAuditV1,
    S5CompleteReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_complete_release_tag_source_remediation_execution import (  # noqa: E402
    S5_COMPLETE_RELEASE_PASS,
    S5_COMPLETE_RELEASE_RESULT_NEXT,
    S5CompleteReleaseExecutionContractAuditV1,
    S5CompleteReleaseExecutionContractV1,
    S5CompleteReleaseProcessTranscript,
    S5CompleteReleaseRemediationResultV1,
)
from aurex.backtest_engine.s5_complete_release_tag_source_remediation_result_audit import (  # noqa: E402
    S5_COMPLETE_RELEASE_RESULT_AUDIT_NEXT,
    S5_COMPLETE_RELEASE_RESULT_AUDIT_PASS,
    S5CompleteReleaseRemediationResultAuditV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
    S5ReleaseTagDiscoveryRecord,
    S5ReleaseTagProcessTranscript,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_execution_contract_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_result_v1.json"
)
DEFAULT_AUDIT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_result_audit_v1.json"
)
PRIOR_DISCOVERY = Path(
    "data/evidence/s5_release_tag_source_responses_v1/01_ls_remote_tags.json"
)
AUDIT_MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_complete_release_tag_source_remediation_result_audit.py"
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
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(PROJECT_ROOT / path))
        for path in paths
    )


def bindings_match(bindings: tuple[S5HistoryBinding, ...]) -> bool:
    return all(
        (PROJECT_ROOT / item.path).is_file()
        and file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in bindings
    )


def directory_manifest_hash(path: Path) -> str:
    records: list[dict] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError("S5 complete release audit found a symbolic link")
        if candidate.is_file():
            records.append(
                {
                    "relative_path": candidate.relative_to(path).as_posix(),
                    "file_sha256": file_sha256(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    if not records:
        raise ValueError("S5 complete release audit repository is empty")
    return universe_evidence_hash(records)


def complete_manifest(
    protocol: S5CompleteReleaseTagSourceRemediationProtocolV1,
) -> tuple[S5ReleaseTagDiscoveryRecord, ...]:
    transcript = S5ReleaseTagProcessTranscript.model_validate_json(
        (PROJECT_ROOT / PRIOR_DISCOVERY).read_text(encoding="utf-8")
    )
    if (
        file_sha256(PROJECT_ROOT / PRIOR_DISCOVERY)
        != protocol.frozen_discovery_transcript_file_sha256
        or transcript.transcript_evidence_hash
        != protocol.frozen_discovery_transcript_evidence_hash
        or transcript.return_code != 0
    ):
        raise ValueError("S5 complete release audit discovery lineage changed")
    payload = base64.b64decode(transcript.stdout_base64, validate=True)
    remote: dict[str, str] = {}
    for line in payload.splitlines():
        fields = line.split(b"\t")
        if len(fields) != 2:
            raise ValueError("S5 complete release audit discovery framing changed")
        object_sha = fields[0].decode("ascii")
        ref_name = fields[1].decode("utf-8")
        if (
            ref_name in remote
            or not ref_name.startswith("refs/tags/")
            or not re.fullmatch(r"[0-9a-f]{40}", object_sha)
        ):
            raise ValueError("S5 complete release audit discovery identity changed")
        remote[ref_name] = object_sha
    pattern = re.compile(protocol.stable_release_tag_regex)
    records: list[S5ReleaseTagDiscoveryRecord] = []
    for ref_name in sorted(item for item in remote if pattern.fullmatch(item)):
        object_sha = remote[ref_name]
        peeled_sha = remote.get(f"{ref_name}^{{}}")
        tag_type = "ANNOTATED" if peeled_sha is not None else "LIGHTWEIGHT"
        records.append(
            S5ReleaseTagDiscoveryRecord(
                ref_name=ref_name,
                object_sha=object_sha,
                peeled_commit_sha=peeled_sha or object_sha,
                tag_type=tag_type,
                fetch_refspec=f"+{ref_name}:{ref_name}",
            )
        )
    return tuple(records)


def parse_verified(payload: bytes) -> dict[str, tuple[str, str, str]]:
    records: dict[str, tuple[str, str, str]] = {}
    for raw_record in payload.split(b"\x1e"):
        record = raw_record.strip(b"\r\n")
        if record.endswith(b"\x00"):
            record = record[:-1]
        if not record:
            continue
        fields = record.split(b"\x00")
        if len(fields) != 4:
            raise ValueError("S5 complete release audit verification framing changed")
        ref_name, object_type, object_sha, peeled_sha = (
            item.decode("ascii") for item in fields
        )
        if (
            ref_name in records
            or not ref_name.startswith("refs/tags/")
            or object_type not in {"tag", "commit"}
            or not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or (object_type == "tag" and not re.fullmatch(r"[0-9a-f]{40}", peeled_sha))
            or (object_type == "commit" and peeled_sha)
        ):
            raise ValueError("S5 complete release audit verified identity changed")
        records[ref_name] = (object_type, object_sha, peeled_sha)
    return records


def drift_count(
    manifest: tuple[S5ReleaseTagDiscoveryRecord, ...],
    verified: dict[str, tuple[str, str, str]],
) -> int:
    expected_refs = {item.ref_name for item in manifest}
    drift = len(expected_refs.symmetric_difference(verified))
    for item in manifest:
        expected = (
            "tag" if item.tag_type == "ANNOTATED" else "commit",
            item.object_sha,
            item.peeled_commit_sha if item.tag_type == "ANNOTATED" else "",
        )
        if item.ref_name in verified and verified[item.ref_name] != expected:
            drift += 1
    return drift


def build_audit(
    *,
    result_path: Path,
    audited_at: datetime,
) -> S5CompleteReleaseRemediationResultAuditV1:
    protocol = S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_PROTOCOL).read_text(encoding="utf-8")
    )
    protocol_audit = S5CompleteReleaseTagSourceRemediationProtocolAuditV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_PROTOCOL_AUDIT).read_text(encoding="utf-8")
    )
    contract = S5CompleteReleaseExecutionContractV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_CONTRACT).read_text(encoding="utf-8")
    )
    contract_audit = S5CompleteReleaseExecutionContractAuditV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_CONTRACT_AUDIT).read_text(encoding="utf-8")
    )
    result = S5CompleteReleaseRemediationResultV1.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or protocol_audit.protocol_file_sha256 != file_sha256(PROJECT_ROOT / DEFAULT_PROTOCOL)
        or protocol_audit.builder_contract_hash != protocol.builder_contract_hash
        or protocol_audit.source_binding_manifest_evidence_hash
        != protocol.source_binding_manifest_evidence_hash
        or protocol_audit.prior_result_audit_evidence_hash
        != protocol.prior_result_audit_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.contract_file_sha256 != file_sha256(PROJECT_ROOT / DEFAULT_CONTRACT)
        or contract_audit.builder_contract_hash != contract.builder_contract_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
        or contract_audit.source_binding_manifest_evidence_hash
        != contract.source_binding_manifest_evidence_hash
        or contract_audit.implementation_binding_manifest_evidence_hash
        != contract.implementation_binding_manifest_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.execution_contract_audit_evidence_hash
        != contract_audit.audit_evidence_hash
        or result.runner_contract_hash != contract.runner_contract_hash
        or result.decision != S5_COMPLETE_RELEASE_PASS
        or result.next_authorization != S5_COMPLETE_RELEASE_RESULT_NEXT
        or not result.authorizes_amended_measurement_protocol
        or not bindings_match(protocol.source_bindings)
        or not bindings_match(protocol_audit.auditor_implementation_bindings)
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or not bindings_match(contract_audit.auditor_implementation_bindings)
    ):
        raise ValueError("S5 complete release audit lineage changed")
    if result.transcript_paths != (
        protocol.fetch_transcript_path,
        protocol.verification_transcript_path,
    ):
        raise ValueError("S5 complete release audit transcript paths changed")
    transcripts: list[S5CompleteReleaseProcessTranscript] = []
    for path_text, expected_hash in zip(
        result.transcript_paths,
        result.transcript_file_sha256s,
        strict=True,
    ):
        path = PROJECT_ROOT / path_text
        if file_sha256(path) != expected_hash:
            raise ValueError("S5 complete release audit transcript hash changed")
        transcripts.append(
            S5CompleteReleaseProcessTranscript.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        )
    if (
        tuple(item.sequence for item in transcripts) != (1, 2)
        or tuple(item.process_role for item in transcripts) != contract.expected_process_roles
        or any(
            not result.started_at <= item.started_at <= item.completed_at <= result.completed_at
            or (item.completed_at - item.started_at).total_seconds()
            > protocol.maximum_process_seconds
            for item in transcripts
        )
        or transcripts[0].completed_at > transcripts[1].started_at
    ):
        raise ValueError("S5 complete release audit process sequence or timing changed")
    manifest = complete_manifest(protocol)
    manifest_hash = universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in manifest)
    )
    verified = parse_verified(
        base64.b64decode(transcripts[1].stdout_base64, validate=True)
    )
    drift = drift_count(manifest, verified)
    destination = PROJECT_ROOT / protocol.destination_history_dataset_path
    expected_commands = (
        (
            *protocol.fetch_command_prefix[:2],
            str(destination),
            *protocol.fetch_command_prefix[3:],
            *(item.fetch_refspec for item in manifest),
        ),
        (
            *protocol.verification_command[:2],
            str(destination),
            *protocol.verification_command[3:],
        ),
    )
    if tuple(item.command for item in transcripts) != expected_commands:
        raise ValueError("S5 complete release audit command changed")
    if (
        len(manifest) != 132
        or sum(item.tag_type == "ANNOTATED" for item in manifest) != 104
        or sum(item.tag_type == "LIGHTWEIGHT" for item in manifest) != 28
        or manifest_hash != protocol.complete_stable_tag_manifest_evidence_hash
        or len(verified) != 132
        or drift != 0
        or any(item.return_code != 0 for item in transcripts)
    ):
        raise ValueError("S5 complete release audit identity accounting changed")
    original_hash = directory_manifest_hash(
        PROJECT_ROOT / protocol.original_history_dataset_path
    )
    incomplete_hash = directory_manifest_hash(
        PROJECT_ROOT / protocol.incomplete_release_dataset_path
    )
    complete_hash = directory_manifest_hash(destination)
    if (
        original_hash != result.original_repository_directory_sha256
        or incomplete_hash != result.incomplete_repository_directory_sha256
        or complete_hash != result.destination_final_directory_sha256
    ):
        raise ValueError("S5 complete release audit repository manifest changed")
    auditor_bindings = auditor_contract_bindings()
    return build_hashed(
        S5CompleteReleaseRemediationResultAuditV1,
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
            "original_repository_directory_sha256": original_hash,
            "incomplete_repository_directory_sha256": incomplete_hash,
            "complete_repository_directory_sha256": complete_hash,
            "limitations": tuple(
                sorted(
                    (
                        "All 132 fetched tag identities match the frozen discovery snapshot.",
                        "Annotated tagger timestamps have not yet been measured or filtered.",
                        "Git tag signatures have not been cryptographically verified.",
                        "Lightweight tags retain historical creation-time uncertainty.",
                        "No Git process or network request was executed during this audit.",
                        "No market value, return, strategy, signal, or order was created.",
                        "Prior repositories, transcripts, results, and audits remain immutable.",
                        "Production and live trading remain prohibited.",
                        "Qualified strategies and real net profit remain zero.",
                        "A separate amended measurement protocol is still required.",
                    )
                )
            ),
        },
    )


def write_audit(path: Path, audit: S5CompleteReleaseRemediationResultAuditV1) -> None:
    if path.exists():
        raise ValueError(f"S5 complete release result audit already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5CompleteReleaseRemediationResultAuditV1.model_validate_json(serialized) != audit:
        raise ValueError("S5 complete release result audit did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the complete S5 release-tag remediation result."
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
            stored = S5CompleteReleaseRemediationResultAuditV1.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected:
                raise ValueError("Stored S5 complete release result audit changed")
            print(f"PASS {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"{S5_COMPLETE_RELEASE_RESULT_AUDIT_PASS} {args.output} "
            f"{audit.audit_evidence_hash} tags=132 drift=0 git_processes=0 "
            f"network=0 market_values=0 next={S5_COMPLETE_RELEASE_RESULT_AUDIT_NEXT}",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
