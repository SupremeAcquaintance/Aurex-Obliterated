from __future__ import annotations

import hashlib

import pytest

from scripts.run_s5_bitcoin_core_history_census import (
    canonical_commit_stream,
    classify_batch_output,
    parse_commit_object,
)

PATTERNS = (
    (
        "BITCOIN_CORE_MAINTAINER_MERGE",
        r"^Merge bitcoin/bitcoin#([1-9][0-9]*):(?: |$)",
    ),
    (
        "GITHUB_DEFAULT_PULL_MERGE",
        r"^Merge pull request #([1-9][0-9]*) from .+$",
    ),
)


def commit_object(*, parents: tuple[str, ...], first_line: str) -> bytes:
    headers = [f"tree {'a' * 40}"]
    headers.extend(f"parent {parent}" for parent in parents)
    headers.extend(
        (
            "author Not Parsed <not-parsed@example.com> 1 +0000",
            "committer Not Parsed <not-parsed@example.com> 2 +0000",
        )
    )
    return ("\n".join(headers) + f"\n\n{first_line}\nignored body\n").encode()


def batch_payload(entries: tuple[tuple[str, bytes], ...]) -> bytes:
    return b"".join(
        f"{commit_id} commit {len(raw)}\n".encode() + raw + b"\n" for commit_id, raw in entries
    )


def test_classifies_first_parent_commit_objects_without_identity_fields() -> None:
    ids = tuple(f"{index:040x}" for index in range(1, 6))
    objects = (
        commit_object(parents=(), first_line="Initial import"),
        commit_object(
            parents=(ids[0],),
            first_line="Merge pull request #999 from ignored/single-parent",
        ),
        commit_object(
            parents=(ids[1], "b" * 40),
            first_line="Merge bitcoin/bitcoin#12: accepted maintainer form",
        ),
        commit_object(
            parents=(ids[2], "c" * 40, "d" * 40),
            first_line="Merge pull request #34 from bitcoin/topic",
        ),
        commit_object(
            parents=(ids[3], "e" * 40),
            first_line="Merge an older source without a pull request number",
        ),
    )
    inspection = classify_batch_output(
        payload=batch_payload(tuple(zip(ids, objects, strict=True))),
        commit_ids=ids,
        pattern_specs=PATTERNS,
        maximum_samples=25,
        maximum_sample_characters=300,
        first_parent_stream_sha256="f" * 64,
    )

    assert inspection.first_parent_commit_count == 5
    assert inspection.commit_object_count == 5
    assert inspection.root_commit_count == 1
    assert inspection.single_parent_commit_count == 1
    assert inspection.merge_commit_count == 3
    assert inspection.octopus_merge_commit_count == 1
    assert inspection.recognized_pull_merge_count == 2
    assert inspection.unrecognized_merge_count == 1
    assert inspection.single_parent_pattern_match_count == 1
    assert inspection.distinct_pull_request_ids == (12, 34)
    assert inspection.recognized_pattern_counts == {
        "BITCOIN_CORE_MAINTAINER_MERGE": 1,
        "GITHUB_DEFAULT_PULL_MERGE": 1,
    }
    assert tuple(item.sequence for item in inspection.accepted_pull_request_records) == (1, 2)
    assert inspection.unrecognized_merge_samples[0].first_line.startswith("Merge an older")
    assert "Not Parsed" not in inspection.unrecognized_merge_samples[0].first_line


def test_unrecognized_stream_hash_covers_records_beyond_sample_limit() -> None:
    ids = tuple(f"{index:040x}" for index in range(1, 4))
    objects = tuple(
        commit_object(
            parents=("a" * 40, "b" * 40),
            first_line=f"Unrecognized merge {index}",
        )
        for index in range(3)
    )
    inspection = classify_batch_output(
        payload=batch_payload(tuple(zip(ids, objects, strict=True))),
        commit_ids=ids,
        pattern_specs=PATTERNS,
        maximum_samples=1,
        maximum_sample_characters=10,
        first_parent_stream_sha256="f" * 64,
    )
    expected = hashlib.sha256()
    for commit_id, index in zip(ids, range(3), strict=True):
        expected.update(commit_id.encode())
        expected.update(b"\0")
        expected.update(f"Unrecognized merge {index}".encode())
        expected.update(b"\n")

    assert inspection.unrecognized_merge_count == 3
    assert len(inspection.unrecognized_merge_samples) == 1
    assert inspection.unrecognized_merge_samples[0].first_line == "Unrecogniz"
    assert inspection.unrecognized_merge_first_line_stream_sha256 == expected.hexdigest()


def test_parse_commit_object_rejects_invalid_parent_header() -> None:
    raw = commit_object(parents=("z" * 40,), first_line="Invalid parent")
    with pytest.raises(ValueError, match="invalid object ID"):
        parse_commit_object(raw)


def test_batch_parser_rejects_unexpected_trailing_output() -> None:
    commit_id = "1" * 40
    raw = commit_object(parents=(), first_line="Initial import")
    with pytest.raises(ValueError, match="trailing bytes"):
        classify_batch_output(
            payload=batch_payload(((commit_id, raw),)) + b"x",
            commit_ids=(commit_id,),
            pattern_specs=PATTERNS,
            maximum_samples=25,
            maximum_sample_characters=300,
            first_parent_stream_sha256="f" * 64,
        )


def test_canonical_commit_stream_requires_unique_cutoff_terminated_ids() -> None:
    first = "1" * 40
    cutoff = "2" * 40
    commit_ids, evidence_hash = canonical_commit_stream(
        f"{first}\n{cutoff}\n".encode(), cutoff=cutoff, maximum_count=2
    )
    assert commit_ids == (first, cutoff)
    assert evidence_hash == hashlib.sha256(f"{first}\n{cutoff}\n".encode()).hexdigest()

    with pytest.raises(ValueError, match="structural validation"):
        canonical_commit_stream(f"{first}\n{first}\n".encode(), cutoff=cutoff, maximum_count=2)
