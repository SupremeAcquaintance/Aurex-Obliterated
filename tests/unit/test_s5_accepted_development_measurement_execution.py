from __future__ import annotations

import os
import subprocess
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_accepted_development_measurement_execution import (
    S5_MEASUREMENT_RUN,
    S5AcceptedDevelopmentMeasurementExecutionContractV1,
    S5AcceptedDevelopmentMonthlyMeasurementRow,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.audit_s5_accepted_development_measurement_execution import build_audit
from scripts.freeze_s5_accepted_development_measurement_execution import (
    build_contract,
    write_contract,
)
from scripts.freeze_s5_accepted_development_measurement_protocol import build_protocol
from scripts.run_s5_accepted_development_measurements import (
    component_key,
    expand_command,
    git_environment,
    parse_first_parent_diff_stream,
    parse_reachable_commits,
    parse_stable_release_tags,
    run_git,
)


def frozen_time() -> datetime:
    return datetime(2026, 9, 8, 21, 0, tzinfo=UTC)


def empty_hash() -> str:
    return universe_evidence_hash(())


def test_component_key_policy_is_deterministic() -> None:
    assert component_key("README.md") == "ROOT"
    assert component_key("doc/release-notes.md") == "doc"
    assert component_key("src/net.cpp") == "src/_root"
    assert component_key("src/wallet/wallet.cpp") == "src/wallet"

    with pytest.raises(ValueError):
        component_key("src\\wallet\\wallet.cpp")
    with pytest.raises(ValueError):
        component_key("src/../wallet.cpp")


def test_first_parent_diff_and_reachable_parsers_fail_closed() -> None:
    first = "a" * 40
    second = "b" * 40
    payload = (
        b"\x1e"
        + first.encode()
        + b"\x00src/wallet/a.cpp\x00doc/a.md\x00"
        + b"\x1e"
        + second.encode()
        + b"\x00src/net.cpp\x00"
    )
    parsed = parse_first_parent_diff_stream(payload)

    assert parsed[first] == ("src/wallet/a.cpp", "doc/a.md")
    assert parsed[second] == ("src/net.cpp",)
    assert parse_reachable_commits(f"{first}\n{second}\n".encode()) == {
        first,
        second,
    }

    with pytest.raises(ValueError):
        parse_first_parent_diff_stream(payload + b"\x1e" + first.encode())
    with pytest.raises(ValueError):
        parse_reachable_commits(f"{first}\n{first}\n".encode())


def test_stable_release_parser_preserves_signature_uncertainty() -> None:
    annotated_object = "1" * 40
    annotated_commit = "2" * 40
    lightweight_commit = "3" * 40
    records = (
        b"refs/tags/v30.0\x00tag\x00"
        + annotated_object.encode()
        + b"\x00"
        + annotated_commit.encode()
        + b"\x002025-10-10T00:00:00+00:00"
        + b"\x002025-10-10T00:00:00+00:00"
        + b"\x00-----BEGIN PGP SIGNATURE-----\x00\x1e"
        + b"refs/tags/v0.1.0\x00commit\x00"
        + lightweight_commit.encode()
        + b"\x00\x00\x002009-01-09T00:00:00+00:00\x00\x00\x1e"
        + b"refs/tags/v31.0rc1\x00tag\x00"
        + ("4" * 40).encode()
        + b"\x00"
        + ("5" * 40).encode()
        + b"\x002026-01-01T00:00:00+00:00"
        + b"\x002026-01-01T00:00:00+00:00\x00\x00\x1e"
    )
    stable = parse_stable_release_tags(
        records,
        stable_release_tag_regex=(
            r"^refs/tags/v(?:0|[1-9][0-9]*)\."
            r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
        ),
        reachable_commits=frozenset({annotated_commit, lightweight_commit}),
    )

    assert len(stable) == 2
    assert stable[0].signature_state == "LIGHTWEIGHT_UNVERIFIED"
    assert stable[1].signature_state == (
        "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"
    )

    with pytest.raises(ValueError):
        parse_stable_release_tags(
            records,
            stable_release_tag_regex=r"^refs/tags/v30\.0$",
            reachable_commits=frozenset(),
        )


def test_monthly_row_enforces_accounting_and_seven_day_lag() -> None:
    row = S5AcceptedDevelopmentMonthlyMeasurementRow(
        sequence=1,
        month_start=date(2009, 1, 1),
        month_end_exclusive=date(2009, 2, 1),
        measurement_available_at=datetime(2009, 2, 8, tzinfo=UTC),
        primary_source_verified_accepted_pull_count=2,
        primary_distinct_local_source_commit_count=1,
        primary_many_to_one_excess_count=1,
        all_accepted_pull_count=3,
        source_unverified_accepted_pull_count=1,
        canonical_integration_count=1,
        canonical_github_time_count=1,
        canonical_git_fallback_time_count=0,
        known_human_or_unresolved_actor_count=1,
        unknown_actor_event_count=1,
        human_contributor_lower_bound=1,
        human_contributor_upper_bound=2,
        known_bot_actor_count=0,
        canonical_component_key_count=1,
        unresolved_git_merge_count=0,
        stable_release_tag_count=0,
        signed_annotated_stable_release_tag_count=0,
        primary_event_manifest_evidence_hash=empty_hash(),
        canonical_event_manifest_evidence_hash=empty_hash(),
        component_key_manifest_evidence_hash=empty_hash(),
        release_tag_manifest_evidence_hash=empty_hash(),
        source_normalization_result_evidence_hash="a" * 64,
    )

    assert row.primary_many_to_one_excess_count == 1
    payload = row.model_dump(mode="json")
    payload["measurement_available_at"] = "2009-02-07T00:00:00Z"
    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMonthlyMeasurementRow.model_validate(payload)


def test_execution_contract_and_audit_reconstruct_without_measurements(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract = build_contract(frozen_at=frozen_time())
    write_contract(contract_path, contract)
    audit = build_audit(contract_path=contract_path, audited_at=frozen_time())

    assert contract.authorizes_single_local_measurement_run
    assert contract.expected_git_process_count == 3
    assert contract.maximum_git_process_count == 4
    assert not contract.network_access_permitted
    assert not contract.market_values_permitted
    assert not contract.testnet_strategy_orders_permitted
    assert audit.contract_evidence_hash == contract.contract_evidence_hash
    assert audit.git_processes_executed == 0
    assert audit.source_rows_parsed == 0
    assert audit.next_authorization == S5_MEASUREMENT_RUN


def test_execution_contract_rejects_authority_tampering() -> None:
    contract = build_contract(frozen_at=frozen_time())
    payload = contract.model_dump(mode="json")
    payload["network_access_permitted"] = True

    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMeasurementExecutionContractV1.model_validate(payload)


def test_frozen_git_commands_emit_parseable_streams_on_synthetic_repo(tmp_path) -> None:
    repository = tmp_path / "history.git"
    repository.mkdir()

    def git(*arguments: str) -> bytes:
        return subprocess.run(
            ("git", "-C", str(repository), *arguments),
            check=True,
            capture_output=True,
            env=os.environ.copy(),
        ).stdout

    git("init", "-q")
    git("config", "user.email", "aurex@example.invalid")
    git("config", "user.name", "Aurex Test")
    (repository / "README.md").write_text("root\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "root")
    git("checkout", "-q", "-b", "feature")
    (repository / "src" / "wallet").mkdir(parents=True)
    (repository / "src" / "wallet" / "a.cpp").write_text("x\n", encoding="utf-8")
    git("add", "src/wallet/a.cpp")
    git("commit", "-q", "-m", "feature")
    git("checkout", "-q", "master")
    git("merge", "-q", "--no-ff", "feature", "-m", "merge feature")
    git("tag", "-a", "v1.0", "-m", "stable")
    git("tag", "v0.1.0")
    git("tag", "-a", "v2.0rc1", "-m", "candidate")
    cutoff = git("rev-parse", "HEAD").decode().strip()

    protocol = build_protocol(frozen_at=frozen_time())
    contract = build_contract(frozen_at=frozen_time())
    replacements = {
        "{history_dataset_path}": str(repository),
        "{source_cutoff_commit}": cutoff,
    }

    def command(template: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(replacements.get(token, token) for token in template)

    environment = git_environment(contract)
    diff_payload = run_git(
        command(contract.first_parent_diff_command),
        environment=environment,
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
    )
    reachable_payload = run_git(
        command(contract.reachable_commit_command),
        environment=environment,
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
    )
    tag_payload = run_git(
        command(contract.tag_inventory_command),
        environment=environment,
        timeout_seconds=30,
        maximum_stdout_bytes=1_000_000,
    )

    diff_records = parse_first_parent_diff_stream(diff_payload)
    reachable = parse_reachable_commits(reachable_payload)
    stable = parse_stable_release_tags(
        tag_payload,
        stable_release_tag_regex=protocol.stable_release_tag_regex,
        reachable_commits=reachable,
    )

    assert cutoff in diff_records
    assert "src/wallet/a.cpp" in diff_records[cutoff]
    assert cutoff in reachable
    assert tuple(item.ref_name for item in stable) == (
        "refs/tags/v0.1.0",
        "refs/tags/v1.0",
    )
    assert expand_command(contract.reachable_commit_command, protocol)[0] == "git"
