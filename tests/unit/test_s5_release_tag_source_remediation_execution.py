from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_release_tag_source_remediation import (
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (
    S5_RELEASE_REMEDIATION_RUN,
    S5ReleaseTagProcessTranscript,
    S5ReleaseTagSourceRemediationExecutionContractV1,
)
from scripts.audit_s5_release_tag_source_remediation_execution import build_audit
from scripts.audit_s5_release_tag_source_remediation_result import (
    build_audit as build_result_audit,
)
from scripts.freeze_s5_release_tag_source_remediation_execution import (
    build_contract,
    write_contract,
)
from scripts.run_s5_release_tag_source_remediation import (
    DEFAULT_PROTOCOL,
    compare_fetched_tags,
    directory_manifest_hash,
    git_environment,
    parse_local_tags,
    parse_ls_remote_tags,
    parse_reachable_commits,
    require_process_success,
    run_git_process,
    select_stable_tags,
)


def frozen_time() -> datetime:
    return datetime(2026, 9, 8, 23, 0, tzinfo=UTC)


def git(*arguments: str, cwd=None) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        cwd=cwd,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
    ).stdout


def test_execution_contract_and_audit_reconstruct_without_network(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract = build_contract(frozen_at=frozen_time())
    write_contract(contract_path, contract)
    audit = build_audit(contract_path=contract_path, audited_at=frozen_time())

    assert contract.authorizes_single_remediation_run
    assert contract.expected_process_roles == (
        "REMOTE_TAG_DISCOVERY",
        "LOCAL_REACHABLE_COMMITS",
        "REMOTE_EXACT_TAG_FETCH",
        "LOCAL_TAG_VERIFICATION",
    )
    assert not contract.market_values_permitted
    assert not contract.production_permitted
    assert audit.contract_evidence_hash == contract.contract_evidence_hash
    assert audit.network_processes_executed == 0
    assert audit.next_authorization == S5_RELEASE_REMEDIATION_RUN


def test_execution_contract_rejects_authority_and_role_tampering() -> None:
    contract = build_contract(frozen_at=frozen_time())
    payload = contract.model_dump(mode="json")
    payload["market_values_permitted"] = True
    with pytest.raises(ValidationError):
        S5ReleaseTagSourceRemediationExecutionContractV1.model_validate(payload)

    payload = contract.model_dump(mode="json")
    payload["expected_process_roles"][0] = "LOCAL_REACHABLE_COMMITS"
    with pytest.raises(ValidationError):
        S5ReleaseTagSourceRemediationExecutionContractV1.model_validate(payload)


def test_transcript_verifies_decoded_byte_hash_and_process_role(tmp_path) -> None:
    repository = tmp_path / "repository"
    git("init", "-q", str(repository))
    transcript_path = tmp_path / "02_reachable.json"
    _, transcript = run_git_process(
        sequence=2,
        role="LOCAL_REACHABLE_COMMITS",
        command=("git", "-C", str(repository), "rev-parse", "--git-dir"),
        transcript_path=transcript_path,
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=git_environment(),
    )
    require_process_success(transcript)
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    payload["stdout_base64"] = base64.b64encode(b"tampered").decode("ascii")
    payload["stdout_byte_count"] = len(b"tampered")
    with pytest.raises(ValidationError):
        S5ReleaseTagProcessTranscript.model_validate(payload)

    payload = transcript.model_dump(mode="json")
    payload["network_process"] = True
    with pytest.raises(ValidationError):
        S5ReleaseTagProcessTranscript.model_validate(payload)


def test_git_environment_removes_proxy_token_and_credential_inputs(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("GIT_ASKPASS", "helper")
    trusted = DEFAULT_PROTOCOL.parent
    environment = git_environment(safe_directories=(trusted,))

    assert "HTTPS_PROXY" not in environment
    assert "GITHUB_TOKEN" not in environment
    assert environment["GIT_ASKPASS"] == ""
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert environment["GIT_CONFIG_VALUE_0"] == ""
    assert environment["GIT_CONFIG_KEY_2"] == "safe.directory"
    assert environment["GIT_CONFIG_VALUE_2"] == str(trusted.resolve())


def test_discovery_selection_and_verification_fail_closed() -> None:
    annotated_object = "a" * 40
    annotated_commit = "b" * 40
    lightweight_commit = "c" * 40
    future_commit = "d" * 40
    payload = (
        f"{annotated_object}\trefs/tags/v1.0\n"
        f"{annotated_commit}\trefs/tags/v1.0^{{}}\n"
        f"{lightweight_commit}\trefs/tags/v0.1.0\n"
        f"{'e' * 40}\trefs/tags/v2.0rc1\n"
        f"{future_commit}\trefs/tags/v3.0\n"
    ).encode()
    remote = parse_ls_remote_tags(payload)
    selected = select_stable_tags(
        remote,
        stable_release_tag_regex=(
            r"^refs/tags/v(?:0|[1-9][0-9]*)\."
            r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
        ),
        reachable_commits=frozenset({annotated_commit, lightweight_commit}),
        maximum_selected=500,
    )
    assert tuple(item.ref_name for item in selected) == (
        "refs/tags/v0.1.0",
        "refs/tags/v1.0",
    )
    assert tuple(item.tag_type for item in selected) == ("LIGHTWEIGHT", "ANNOTATED")

    verification = (
        f"refs/tags/v0.1.0\x00commit\x00{lightweight_commit}\x00\x00\x1e\n"
        f"refs/tags/v1.0\x00tag\x00{annotated_object}\x00{annotated_commit}\x00\x1e\n"
    ).encode()
    assert compare_fetched_tags(selected, parse_local_tags(verification)) == 0

    with pytest.raises(ValueError):
        parse_ls_remote_tags(payload + payload.splitlines(keepends=True)[0])
    with pytest.raises(ValueError):
        select_stable_tags(
            {"refs/tags/v1.0^{}": annotated_commit},
            stable_release_tag_regex=r"^refs/tags/v1\.0$",
            reachable_commits=frozenset({annotated_commit}),
            maximum_selected=500,
        )


def test_four_process_git_lifecycle_on_disposable_local_remote(tmp_path) -> None:
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    source = tmp_path / "source.git"
    destination = tmp_path / "destination.git"
    transcripts = tmp_path / "transcripts"
    git("init", "-q", str(work))
    git("-C", str(work), "config", "user.email", "aurex@example.invalid")
    git("-C", str(work), "config", "user.name", "Aurex Test")
    (work / "README.md").write_text("root\n", encoding="utf-8")
    git("-C", str(work), "add", "README.md")
    git("-C", str(work), "commit", "-q", "-m", "root")
    git("-C", str(work), "tag", "-a", "v1.0", "-m", "annotated stable")
    git("-C", str(work), "tag", "v0.1.0")
    git("-C", str(work), "tag", "-a", "v2.0rc1", "-m", "prerelease")
    git("clone", "-q", "--bare", str(work), str(remote))
    git("clone", "-q", "--bare", "--no-tags", str(remote), str(source))
    shutil.copytree(source, destination, symlinks=False)
    assert directory_manifest_hash(source) == directory_manifest_hash(destination)
    cutoff = git("-C", str(source), "rev-parse", "refs/heads/master").decode().strip()
    environment = git_environment()

    discovery_payload, discovery_transcript = run_git_process(
        sequence=1,
        role="REMOTE_TAG_DISCOVERY",
        command=("git", "ls-remote", "--tags", "--sort=refname", str(remote)),
        transcript_path=transcripts / "01.json",
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=environment,
    )
    require_process_success(discovery_transcript)
    reachable_payload, reachable_transcript = run_git_process(
        sequence=2,
        role="LOCAL_REACHABLE_COMMITS",
        command=("git", "-C", str(source), "rev-list", "--topo-order", cutoff),
        transcript_path=transcripts / "02.json",
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=environment,
    )
    require_process_success(reachable_transcript)
    protocol = S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
        DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    )
    selected = select_stable_tags(
        parse_ls_remote_tags(discovery_payload),
        stable_release_tag_regex=protocol.stable_release_tag_regex,
        reachable_commits=parse_reachable_commits(reachable_payload),
        maximum_selected=protocol.maximum_selected_stable_tag_refs,
    )
    assert tuple(item.ref_name for item in selected) == (
        "refs/tags/v0.1.0",
        "refs/tags/v1.0",
    )

    fetch_command = (
        "git",
        "-C",
        str(destination),
        "fetch",
        "--no-tags",
        "--no-write-fetch-head",
        "--filter=blob:none",
        str(remote),
        *(item.fetch_refspec for item in selected),
    )
    _, fetch_transcript = run_git_process(
        sequence=3,
        role="REMOTE_EXACT_TAG_FETCH",
        command=fetch_command,
        transcript_path=transcripts / "03.json",
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=environment,
    )
    require_process_success(fetch_transcript)
    verification_payload, verification_transcript = run_git_process(
        sequence=4,
        role="LOCAL_TAG_VERIFICATION",
        command=(
            "git",
            "-C",
            str(destination),
            "for-each-ref",
            "--format=%(refname)%00%(objecttype)%00%(objectname)%00%(*objectname)%00%1e",
            "refs/tags",
        ),
        transcript_path=transcripts / "04.json",
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
        environment=environment,
    )
    require_process_success(verification_transcript)
    local_records = parse_local_tags(verification_payload)
    assert compare_fetched_tags(selected, local_records) == 0
    assert len(tuple(transcripts.iterdir())) == 4


def test_stored_remediation_result_is_rejected_for_incomplete_coverage() -> None:
    audit = build_result_audit(
        result_path=DEFAULT_PROTOCOL.parent
        / "s5_release_tag_source_remediation_result_v1.json",
        audited_at=frozen_time(),
    )

    assert audit.frozen_protocol_pass_reproduced
    assert not audit.nominal_result_pass_upheld
    assert not audit.release_tag_source_complete_for_measurement
    assert audit.remote_exact_stable_base_ref_count == 132
    assert audit.admitted_stable_tag_count == 42
    assert audit.omitted_stable_tag_count == 90
    assert audit.omitted_annotated_tag_count == 90
    assert audit.omitted_lightweight_tag_count == 0
    assert audit.fetched_tag_identity_drift_count == 0
    assert audit.git_processes_executed_during_audit == 0
    assert audit.network_requests_executed_during_audit == 0
