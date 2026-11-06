from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_complete_release_tag_source_remediation import (
    S5_COMPLETE_RELEASE_REMEDIATION_NEXT,
    S5CompleteReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_complete_release_tag_source_remediation_execution import (
    S5_COMPLETE_RELEASE_RUN,
    S5CompleteReleaseExecutionContractV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (
    S5ReleaseTagDiscoveryRecord,
)
from scripts.audit_s5_complete_release_tag_source_remediation_execution import (
    build_audit as build_execution_audit,
)
from scripts.audit_s5_complete_release_tag_source_remediation_protocol import (
    build_audit,
)
from scripts.audit_s5_complete_release_tag_source_remediation_result import (
    DEFAULT_RESULT,
    parse_verified,
)
from scripts.audit_s5_complete_release_tag_source_remediation_result import (
    build_audit as build_result_audit,
)
from scripts.freeze_s5_complete_release_tag_source_remediation import (
    build_protocol,
    complete_tag_manifest,
    write_protocol,
)
from scripts.freeze_s5_complete_release_tag_source_remediation_execution import (
    build_contract,
    write_contract,
)
from scripts.run_s5_complete_release_tag_source_remediation import (
    git_environment,
    parse_verified_tags,
    require_process_success,
    run_git_process,
    tag_identity_drift_count,
)


def frozen_time() -> datetime:
    return datetime(2026, 9, 9, 0, 0, tzinfo=UTC)


def git(*arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        env=os.environ.copy(),
        check=True,
        capture_output=True,
    ).stdout


def test_complete_release_protocol_freezes_all_discovered_stable_refs() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    manifest = complete_tag_manifest(
        S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
            Path(
                "data/evidence/s5_release_tag_source_remediation_protocol_v1.json"
            ).read_text(encoding="utf-8")
        )
    )

    assert len(protocol.source_bindings) == 10
    assert protocol.complete_stable_tag_count == 132
    assert protocol.complete_annotated_tag_count == 104
    assert protocol.complete_lightweight_tag_count == 28
    assert len(manifest) == 132
    assert sum(item.tag_type == "ANNOTATED" for item in manifest) == 104
    assert sum(item.tag_type == "LIGHTWEIGHT" for item in manifest) == 28
    assert protocol.complete_stable_tag_manifest_evidence_hash == (
        "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    )
    assert not protocol.authorizes_complete_tag_fetch_now
    assert not protocol.authorizes_market_value_access
    assert not protocol.authorizes_live
    assert protocol.next_authorization == S5_COMPLETE_RELEASE_REMEDIATION_NEXT


def test_complete_release_protocol_audit_reconstructs_without_execution(tmp_path) -> None:
    protocol_path = tmp_path / "protocol.json"
    protocol = build_protocol(frozen_at=frozen_time())
    write_protocol(protocol_path, protocol)
    audit = build_audit(protocol_path=protocol_path, audited_at=frozen_time())

    assert audit.protocol_evidence_hash == protocol.protocol_evidence_hash
    assert audit.complete_stable_tag_count == 132
    assert audit.git_processes_executed == 0
    assert audit.repository_copies_executed == 0
    assert audit.network_requests_executed == 0
    assert audit.orders_submitted == 0
    assert audit.next_authorization == S5_COMPLETE_RELEASE_REMEDIATION_NEXT


def test_complete_release_protocol_rejects_authority_and_count_tampering() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    payload = protocol.model_dump(mode="json")
    payload["authorizes_market_value_access"] = True
    with pytest.raises(ValidationError):
        S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate(payload)

    payload = protocol.model_dump(mode="json")
    payload["complete_stable_tag_count"] = 42
    with pytest.raises(ValidationError):
        S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate(payload)


def test_complete_release_execution_contract_reconstructs_without_fetch(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract = build_contract(frozen_at=frozen_time())
    write_contract(contract_path, contract)
    audit = build_execution_audit(
        contract_path=contract_path,
        audited_at=frozen_time(),
    )

    assert contract.authorizes_single_remediation_run
    assert contract.expected_process_roles == (
        "REMOTE_EXACT_COMPLETE_TAG_FETCH",
        "LOCAL_COMPLETE_TAG_VERIFICATION",
    )
    assert not contract.market_values_permitted
    assert not contract.live_permitted
    assert audit.network_processes_executed == 0
    assert audit.next_authorization == S5_COMPLETE_RELEASE_RUN

    payload = contract.model_dump(mode="json")
    payload["live_permitted"] = True
    with pytest.raises(ValidationError):
        S5CompleteReleaseExecutionContractV1.model_validate(payload)


def test_two_process_complete_tag_fetch_lifecycle_on_local_remote(tmp_path) -> None:
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    incomplete = tmp_path / "incomplete.git"
    destination = tmp_path / "complete.git"
    transcripts = tmp_path / "transcripts"
    git("init", "-q", str(work))
    git("-C", str(work), "config", "user.email", "aurex@example.invalid")
    git("-C", str(work), "config", "user.name", "Aurex Test")
    (work / "README.md").write_text("root\n", encoding="utf-8")
    git("-C", str(work), "add", "README.md")
    git("-C", str(work), "commit", "-q", "-m", "root")
    git("-C", str(work), "tag", "v0.1.0")
    git("-C", str(work), "tag", "-a", "v1.0", "-m", "stable")
    git("clone", "-q", "--bare", str(work), str(remote))
    git("clone", "-q", "--bare", "--no-tags", str(remote), str(incomplete))
    git(
        "-C",
        str(incomplete),
        "fetch",
        "--no-tags",
        str(remote),
        "+refs/tags/v0.1.0:refs/tags/v0.1.0",
    )
    shutil.copytree(incomplete, destination, symlinks=False)
    lightweight = git("-C", str(remote), "rev-parse", "refs/tags/v0.1.0").decode().strip()
    annotated_object = git("-C", str(remote), "rev-parse", "refs/tags/v1.0").decode().strip()
    annotated_commit = (
        git("-C", str(remote), "rev-parse", "refs/tags/v1.0^{}")
        .decode()
        .strip()
    )
    manifest = (
        S5ReleaseTagDiscoveryRecord(
            ref_name="refs/tags/v0.1.0",
            object_sha=lightweight,
            peeled_commit_sha=lightweight,
            tag_type="LIGHTWEIGHT",
            fetch_refspec="+refs/tags/v0.1.0:refs/tags/v0.1.0",
        ),
        S5ReleaseTagDiscoveryRecord(
            ref_name="refs/tags/v1.0",
            object_sha=annotated_object,
            peeled_commit_sha=annotated_commit,
            tag_type="ANNOTATED",
            fetch_refspec="+refs/tags/v1.0:refs/tags/v1.0",
        ),
    )
    environment = git_environment(safe_directory=destination)
    _, fetch_transcript = run_git_process(
        sequence=1,
        role="REMOTE_EXACT_COMPLETE_TAG_FETCH",
        command=(
            "git",
            "-C",
            str(destination),
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            "--filter=blob:none",
            str(remote),
            *(item.fetch_refspec for item in manifest),
        ),
        transcript_path=transcripts / "01.json",
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=environment,
    )
    require_process_success(fetch_transcript)
    verification_payload, verification_transcript = run_git_process(
        sequence=2,
        role="LOCAL_COMPLETE_TAG_VERIFICATION",
        command=(
            "git",
            "-C",
            str(destination),
            "for-each-ref",
            "--format=%(refname)%00%(objecttype)%00%(objectname)%00%(*objectname)%00%1e",
            "refs/tags",
        ),
        transcript_path=transcripts / "02.json",
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=environment,
    )
    require_process_success(verification_transcript)
    verified = parse_verified_tags(verification_payload)
    assert len(verified) == 2
    assert tag_identity_drift_count(manifest, verified) == 0
    assert len(tuple(transcripts.iterdir())) == 2


def test_complete_result_audit_reconstructs_source_without_git(monkeypatch) -> None:
    def forbidden_process(*args, **kwargs):
        raise AssertionError("Result audit must not execute Git or network processes")

    monkeypatch.setattr(subprocess, "Popen", forbidden_process)
    audit = build_result_audit(result_path=DEFAULT_RESULT, audited_at=frozen_time())
    assert audit.verified_tag_count == 132
    assert audit.complete_annotated_tag_count == 104
    assert audit.complete_lightweight_tag_count == 28
    assert audit.tag_identity_drift_count == 0
    assert audit.nominal_result_pass_upheld
    assert not audit.event_time_filtering_executed
    assert audit.git_processes_executed_during_audit == 0
    assert audit.next_authorization == "FREEZE_S5_AMENDED_MEASUREMENT_PROTOCOL_ONLY"


@pytest.mark.parametrize(
    ("ref", "kind", "object_sha", "peeled"),
    [
        ("refs/heads/master", "commit", "a" * 40, ""),
        ("refs/tags/v1.0", "tree", "a" * 40, ""),
        ("refs/tags/v1.0", "commit", "bad-sha", ""),
        ("refs/tags/v1.0", "tag", "a" * 40, "bad-sha"),
        ("refs/tags/v1.0", "tag", "a" * 40, ""),
        ("refs/tags/v1.0", "commit", "a" * 40, "b" * 40),
    ],
)
def test_result_audit_rejects_invalid_verified_identity(ref, kind, object_sha, peeled):
    payload = ("\x00".join((ref, kind, object_sha, peeled)) + "\x00\x1e").encode()
    with pytest.raises(ValueError, match="verified identity"):
        parse_verified(payload)
