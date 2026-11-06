from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (
    S5ReleaseTagDiscoveryRecord,
)
from scripts import s5_amended_measurement as runner
from scripts.audit_s5_amended_measurement import independent_months, reconstruct_tags


def identity(ref="refs/tags/v1.0", annotated=True):
    return S5ReleaseTagDiscoveryRecord(
        ref_name=ref,
        object_sha="a" * 40,
        peeled_commit_sha="b" * 40 if annotated else "a" * 40,
        tag_type="ANNOTATED" if annotated else "LIGHTWEIGHT",
        fetch_refspec=f"+{ref}:{ref}",
    )


def inventory(item, at="2026-08-31T23:59:59+00:00", signature=""):
    annotated = item.tag_type == "ANNOTATED"
    return (
        "\x00".join(
            (
                item.ref_name,
                "tag" if annotated else "commit",
                item.object_sha,
                item.peeled_commit_sha if annotated else "",
                at if annotated else "",
                at,
                signature,
            )
        )
        + "\x00\x1e\n"
    ).encode()


@pytest.mark.parametrize("parser", [runner.parse_release_inventory, reconstruct_tags])
def test_annotated_maintenance_branch_does_not_require_master_ancestry(parser):
    item = identity()
    tags = parser(inventory(item, signature="signature"), (item,), frozenset())
    assert tags[0].peeled_commit_sha == "b" * 40
    assert tags[0].signature_state == "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"


@pytest.mark.parametrize("parser", [runner.parse_release_inventory, reconstruct_tags])
def test_lightweight_requires_cutoff_ancestry(parser):
    item = identity(annotated=False)
    with pytest.raises(ValueError):
        parser(inventory(item), (item,), frozenset())
    tags = parser(inventory(item), (item,), frozenset({"a" * 40}))
    assert tags[0].event_time_source == "LIGHTWEIGHT_COMMITTER_AT"
    assert tags[0].signature_state == "LIGHTWEIGHT_UNVERIFIED"


@pytest.mark.parametrize("parser", [runner.parse_release_inventory, reconstruct_tags])
@pytest.mark.parametrize("defect", ["duplicate", "missing", "sha", "timezone", "framing"])
def test_release_inventory_rejects_invalid_evidence(parser, defect):
    item = identity()
    payload = inventory(item)
    payload = {
        "duplicate": payload + payload,
        "missing": b"",
        "sha": payload.replace(b"a" * 40, b"c" * 40),
        "timezone": inventory(item, at="2026-08-31T23:59:59"),
        "framing": payload.replace(b"\x00\x1e", b"\x1e"),
    }[defect]
    with pytest.raises(ValueError):
        parser(payload, (item,), frozenset())


def test_independent_monthly_boundary_lag_and_release_count():
    item = identity()
    later = identity(ref="refs/tags/v2.0")
    payload = inventory(item) + inventory(later, at="2026-09-01T00:00:00+00:00")
    tags = reconstruct_tags(payload, (item, later), frozenset())
    protocol = SimpleNamespace(
        measurement_period_start_month=date(2026, 8, 1),
        measurement_period_end_exclusive=date(2026, 9, 1),
        corrected_normalization_result_evidence_hash="f" * 64,
    )
    rows = independent_months(protocol, ((), (), (), (), ()), {}, tags)
    assert len(rows) == 1
    assert rows[0].stable_release_tag_count == 1
    assert rows[0].measurement_available_at == datetime(2026, 9, 8, tzinfo=UTC)
    assert rows[0].primary_source_verified_accepted_pull_count == 0


def test_independent_actor_and_many_to_one_uncertainty():
    at = datetime(2026, 8, 2, tzinfo=UTC)
    protocol = SimpleNamespace(
        measurement_period_start_month=date(2026, 8, 1),
        measurement_period_end_exclusive=date(2026, 9, 1),
        corrected_normalization_result_evidence_hash="f" * 64,
    )
    pulls = (
        SimpleNamespace(
            pull_number=1,
            merged_at=at,
            actor_id=10,
            actor_identity_status="KNOWN",
            actor_class="HUMAN_OR_UNRESOLVED_ACCOUNT",
        ),
        SimpleNamespace(
            pull_number=2,
            merged_at=at,
            actor_id=None,
            actor_identity_status="UNKNOWN_DELETED_OR_NULL",
            actor_class="UNKNOWN",
        ),
    )
    coverage = tuple(
        SimpleNamespace(
            pull_number=i,
            github_merged_at=at,
            local_source_link_verified=True,
            local_source_commit_sha="b" * 40,
        )
        for i in (1, 2)
    )
    canonical = (
        SimpleNamespace(
            merge_commit_sha="b" * 40,
            canonical_pull_number=1,
            event_at=at,
            event_time_source="GITHUB_MERGED_AT",
        ),
    )
    rows = independent_months(
        protocol,
        (pulls, canonical, (), coverage, ()),
        {"b" * 40: ("src/wallet/a.cpp", "src/foo.cpp", "README.md")},
        (),
    )
    assert rows[0].primary_many_to_one_excess_count == 1
    assert rows[0].human_contributor_lower_bound == 1
    assert rows[0].human_contributor_upper_bound == 2
    assert rows[0].canonical_component_key_count == 3


def test_write_once_preserves_evidence_and_partial(tmp_path):
    path = tmp_path / "result.json"
    runner.write_once(path, b"original")
    with pytest.raises(ValueError, match="already exists"):
        runner.write_once(path, b"replacement")
    assert path.read_bytes() == b"original"
    other = tmp_path / "other.json"
    other.with_name(other.name + ".part").write_bytes(b"interrupted")
    with pytest.raises(ValueError, match="already exists"):
        runner.write_once(other, b"replacement")


def test_sealed_record_rejects_tampering(tmp_path):
    path = tmp_path / "record.json"
    value = runner.sealed({"authority": runner.AUTHORITY})
    value["authority"]["live"] = True
    runner.write_json(path, value)
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.read_sealed(path)


def test_failed_run_preserves_attempt_and_forbids_second_run(tmp_path, monkeypatch):
    for name in ("ATTEMPT", "RESULT", "ROWS", "TAGS", "RESPONSES", "CONTRACT_AUDIT"):
        monkeypatch.setattr(runner, name, tmp_path / name.lower())
    protocol = {"evidence_hash": "a" * 64, "maximum_total_seconds": 1800}
    contract = {"evidence_hash": "b" * 64}
    monkeypatch.setattr(runner, "check_protocol", lambda: protocol)
    monkeypatch.setattr(runner, "check_contract", lambda: contract)
    monkeypatch.setattr(runner, "execution_audit", lambda value: {"verified": True})
    runner.write_json(runner.CONTRACT_AUDIT, runner.sealed({"verified": True}))
    monkeypatch.setattr(runner, "execution_audit", lambda value: runner.sealed({"verified": True}))

    def broken_source():
        raise ValueError("Synthetic source-integrity failure")

    monkeypatch.setattr(runner, "old_authorization", broken_source)
    result = runner.run_measurement()
    assert result["decision"] == "STOP_S5_AMENDED_MEASUREMENT"
    assert result["process_count"] == 0
    assert runner.ATTEMPT.is_file()
    assert runner.RESULT.is_file()
    assert not runner.ROWS.exists()
    with pytest.raises(ValueError, match="already consumed"):
        runner.run_measurement()
