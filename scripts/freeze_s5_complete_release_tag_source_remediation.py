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
    S5_COMPLETE_RELEASE_REMEDIATION_GATES,
    S5CompleteReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (  # noqa: E402
    S5ReleaseTagSourceRemediationProtocolAuditV1,
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
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

MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_complete_release_tag_source_remediation.py"
)
PRIOR_PROTOCOL = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_v1.json"
)
PRIOR_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_audit_v1.json"
)
PRIOR_EXECUTION = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_v1.json"
)
PRIOR_EXECUTION_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_audit_v1.json"
)
PRIOR_RESULT = Path(
    "data/evidence/s5_release_tag_source_remediation_result_v1.json"
)
PRIOR_RESULT_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_result_audit_v1.json"
)
DISCOVERY_TRANSCRIPT = Path(
    "data/evidence/s5_release_tag_source_responses_v1/01_ls_remote_tags.json"
)
REACHABILITY_TRANSCRIPT = Path(
    "data/evidence/s5_release_tag_source_responses_v1/02_reachable_commits.json"
)
FETCH_TRANSCRIPT = Path(
    "data/evidence/s5_release_tag_source_responses_v1/03_fetch_tags.json"
)
VERIFICATION_TRANSCRIPT = Path(
    "data/evidence/s5_release_tag_source_responses_v1/04_verify_tags.json"
)
INCOMPLETE_REPOSITORY = Path(
    "data/evidence/s5_bitcoin_core_release_tags_v1.git"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_protocol_v1.json"
)
SOURCE_PATHS = tuple(
    sorted(
        (
            PRIOR_PROTOCOL,
            PRIOR_PROTOCOL_AUDIT,
            PRIOR_EXECUTION,
            PRIOR_EXECUTION_AUDIT,
            PRIOR_RESULT,
            PRIOR_RESULT_AUDIT,
            DISCOVERY_TRANSCRIPT,
            REACHABILITY_TRANSCRIPT,
            FETCH_TRANSCRIPT,
            VERIFICATION_TRANSCRIPT,
        ),
        key=lambda path: path.as_posix(),
    )
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


def builder_contract_bindings() -> tuple[S5HistoryBinding, ...]:
    paths = tuple(
        sorted(
            (MODULE_PATH, Path(__file__).resolve().relative_to(PROJECT_ROOT)),
            key=lambda path: path.as_posix(),
        )
    )
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in builder_contract_bindings())
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    if len(SOURCE_PATHS) != 10 or not all(path.is_file() for path in SOURCE_PATHS):
        raise ValueError("S5 complete release source set is incomplete")
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in SOURCE_PATHS
    )


def directory_manifest_hash(path: Path) -> str:
    records: list[dict] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError("S5 complete release source contains a symbolic link")
        if candidate.is_file():
            records.append(
                {
                    "relative_path": candidate.relative_to(path).as_posix(),
                    "file_sha256": file_sha256(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    if not records:
        raise ValueError("S5 complete release source repository is empty")
    return universe_evidence_hash(records)


def transcript_stdout(path: Path) -> tuple[S5ReleaseTagProcessTranscript, bytes]:
    transcript = S5ReleaseTagProcessTranscript.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if transcript.return_code != 0:
        raise ValueError("S5 complete release source transcript failed")
    return transcript, base64.b64decode(transcript.stdout_base64, validate=True)


def parse_remote(payload: bytes) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in payload.splitlines():
        fields = line.split(b"\t")
        if len(fields) != 2:
            raise ValueError("S5 complete release discovery framing changed")
        object_sha = fields[0].decode("ascii")
        ref_name = fields[1].decode("utf-8")
        if (
            not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or not ref_name.startswith("refs/tags/")
            or ref_name in records
        ):
            raise ValueError("S5 complete release discovery identity changed")
        records[ref_name] = object_sha
    return records


def parse_reachable(payload: bytes) -> frozenset[str]:
    commits = tuple(payload.decode("ascii").splitlines())
    if (
        len(commits) != 50_395
        or any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in commits)
        or len(commits) != len(set(commits))
    ):
        raise ValueError("S5 complete release reachability source changed")
    return frozenset(commits)


def complete_tag_manifest(
    protocol: S5ReleaseTagSourceRemediationProtocolV1,
) -> tuple[S5ReleaseTagDiscoveryRecord, ...]:
    _, discovery_payload = transcript_stdout(DISCOVERY_TRANSCRIPT)
    _, reachable_payload = transcript_stdout(REACHABILITY_TRANSCRIPT)
    remote = parse_remote(discovery_payload)
    reachable = parse_reachable(reachable_payload)
    pattern = re.compile(protocol.stable_release_tag_regex)
    records: list[S5ReleaseTagDiscoveryRecord] = []
    for ref_name in sorted(item for item in remote if pattern.fullmatch(item)):
        object_sha = remote[ref_name]
        peeled_sha = remote.get(f"{ref_name}^{{}}")
        if peeled_sha is None:
            if object_sha not in reachable:
                raise ValueError("S5 complete release lightweight tag is cutoff-unreachable")
            tag_type = "LIGHTWEIGHT"
            peeled_sha = object_sha
        else:
            tag_type = "ANNOTATED"
        records.append(
            S5ReleaseTagDiscoveryRecord(
                ref_name=ref_name,
                object_sha=object_sha,
                peeled_commit_sha=peeled_sha,
                tag_type=tag_type,
                fetch_refspec=f"+{ref_name}:{ref_name}",
            )
        )
    manifest = tuple(records)
    if (
        len(remote) != 691
        or len(manifest) != 132
        or sum(item.tag_type == "ANNOTATED" for item in manifest) != 104
        or sum(item.tag_type == "LIGHTWEIGHT" for item in manifest) != 28
        or universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in manifest)
        )
        != "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    ):
        raise ValueError("S5 complete release tag manifest changed")
    return manifest


def load_lineage() -> tuple[
    S5ReleaseTagSourceRemediationProtocolV1,
    S5ReleaseTagSourceRemediationProtocolAuditV1,
    S5ReleaseTagSourceRemediationExecutionContractV1,
    S5ReleaseTagSourceRemediationExecutionContractAuditV1,
    S5ReleaseTagSourceRemediationResultV1,
    S5ReleaseTagSourceRemediationResultAuditV1,
]:
    protocol = S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
        PRIOR_PROTOCOL.read_text(encoding="utf-8")
    )
    protocol_audit = S5ReleaseTagSourceRemediationProtocolAuditV1.model_validate_json(
        PRIOR_PROTOCOL_AUDIT.read_text(encoding="utf-8")
    )
    execution = S5ReleaseTagSourceRemediationExecutionContractV1.model_validate_json(
        PRIOR_EXECUTION.read_text(encoding="utf-8")
    )
    execution_audit = (
        S5ReleaseTagSourceRemediationExecutionContractAuditV1.model_validate_json(
            PRIOR_EXECUTION_AUDIT.read_text(encoding="utf-8")
        )
    )
    result = S5ReleaseTagSourceRemediationResultV1.model_validate_json(
        PRIOR_RESULT.read_text(encoding="utf-8")
    )
    result_audit = S5ReleaseTagSourceRemediationResultAuditV1.model_validate_json(
        PRIOR_RESULT_AUDIT.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or execution.protocol_evidence_hash != protocol.protocol_evidence_hash
        or execution_audit.contract_evidence_hash != execution.contract_evidence_hash
        or result.execution_contract_evidence_hash != execution.contract_evidence_hash
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or result_audit.decision != S5_RELEASE_RESULT_AUDIT_REJECT
        or result_audit.next_authorization != S5_RELEASE_RESULT_AUDIT_NEXT
        or result_audit.nominal_result_pass_upheld
        or result_audit.release_tag_source_complete_for_measurement
        or directory_manifest_hash(INCOMPLETE_REPOSITORY)
        != result.destination_final_directory_sha256
    ):
        raise ValueError("S5 complete release predecessor lineage changed")
    return protocol, protocol_audit, execution, execution_audit, result, result_audit


def build_protocol(*, frozen_at: datetime) -> S5CompleteReleaseTagSourceRemediationProtocolV1:
    protocol, protocol_audit, execution, execution_audit, result, result_audit = (
        load_lineage()
    )
    manifest = complete_tag_manifest(protocol)
    discovery, _ = transcript_stdout(DISCOVERY_TRANSCRIPT)
    reachability, _ = transcript_stdout(REACHABILITY_TRANSCRIPT)
    bindings = source_bindings()
    return build_hashed(
        S5CompleteReleaseTagSourceRemediationProtocolV1,
        "protocol_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "source_bindings": bindings,
            "source_binding_manifest_evidence_hash": universe_evidence_hash(
                tuple(item.model_dump(mode="json") for item in bindings)
            ),
            "prior_protocol_evidence_hash": protocol.protocol_evidence_hash,
            "prior_protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "prior_execution_contract_evidence_hash": execution.contract_evidence_hash,
            "prior_execution_contract_audit_evidence_hash": execution_audit.audit_evidence_hash,
            "prior_result_evidence_hash": result.result_evidence_hash,
            "prior_result_audit_evidence_hash": result_audit.audit_evidence_hash,
            "frozen_discovery_transcript_file_sha256": file_sha256(DISCOVERY_TRANSCRIPT),
            "frozen_discovery_transcript_evidence_hash": (
                discovery.transcript_evidence_hash
            ),
            "frozen_reachability_transcript_file_sha256": file_sha256(
                REACHABILITY_TRANSCRIPT
            ),
            "frozen_reachability_transcript_evidence_hash": (
                reachability.transcript_evidence_hash
            ),
            "required_gate_ids": S5_COMPLETE_RELEASE_REMEDIATION_GATES,
            "limitations": tuple(
                sorted(
                    (
                        "A pass repairs release-tag source completeness only.",
                        "All prior repositories, transcripts, results, and audits stay immutable.",
                        "Annotated tagger time filtering belongs to the amended measurement run.",
                        "Current remote presence does not prove historical availability by itself.",
                        "Git tag presence does not prove signer identity or signature validity.",
                        "Lightweight tags preserve historical tag-creation-time uncertainty.",
                        (
                            "No new remote discovery is permitted; the frozen snapshot "
                            "is authoritative."
                        ),
                        "No market value, return, strategy, signal, or order may be created.",
                        "Only the exact sorted 132-ref manifest may be fetched.",
                        "Production and live trading remain prohibited.",
                        "Qualified strategies and real net profit remain zero.",
                        "The complete repository is additive and cannot replace prior evidence.",
                        f"The complete manifest remains fixed at {len(manifest)} stable refs.",
                    )
                )
            ),
        },
    )


def write_protocol(
    path: Path,
    protocol: S5CompleteReleaseTagSourceRemediationProtocolV1,
) -> None:
    if path.exists():
        raise ValueError(f"S5 complete release protocol already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate_json(
        serialized
    ) != protocol:
        raise ValueError("S5 complete release protocol did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the complete S5 release-tag source remediation protocol."
    )
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "stable_tags=132 annotated=104 lightweight=28 git_processes=0 "
            "copies=0 network=0 market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
