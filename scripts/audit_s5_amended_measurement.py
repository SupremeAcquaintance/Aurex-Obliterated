from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_accepted_development_measurement_execution import (  # noqa: E402
    S5AcceptedDevelopmentMonthlyMeasurementRow,
    S5StableReleaseTagRecord,
)
from aurex.backtest_engine.universe import universe_evidence_hash as digest  # noqa: E402
from scripts import s5_amended_measurement as run  # noqa: E402


def reconstruct_tags(payload: bytes, manifest, reachable) -> tuple:
    expected = {item.ref_name: item for item in manifest}
    parsed = {}
    for segment in payload.split(b"\x1e"):
        segment = segment.strip(b"\r\n")
        if not segment:
            continue
        if not segment.endswith(b"\x00"):
            raise ValueError("Audit release terminator changed")
        fields = segment[:-1].split(b"\x00")
        if len(fields) != 7:
            raise ValueError("Audit release framing changed")
        ref, kind, object_sha, peeled, tagger, creator = [f.decode("ascii") for f in fields[:6]]
        if ref not in expected or ref in parsed:
            raise ValueError("Audit release universe changed")
        identity = expected[ref]
        if identity.object_sha != object_sha:
            raise ValueError("Audit release object drift")
        if identity.tag_type == "ANNOTATED":
            if kind != "tag" or peeled != identity.peeled_commit_sha:
                raise ValueError("Audit annotated identity drift")
            at = datetime.fromisoformat(tagger)
            source = "ANNOTATED_TAGGER_AT"
            signature = (
                "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"
                if fields[6]
                else "ANNOTATED_UNSIGNED"
            )
        else:
            if kind != "commit" or peeled or object_sha not in reachable:
                raise ValueError("Audit lightweight identity or ancestry drift")
            at = datetime.fromisoformat(creator)
            source, signature = "LIGHTWEIGHT_COMMITTER_AT", "LIGHTWEIGHT_UNVERIFIED"
        if at.tzinfo is None:
            raise ValueError("Audit release timestamp has no timezone")
        parsed[ref] = S5StableReleaseTagRecord(
            ref_name=ref,
            object_type=kind,
            object_sha=object_sha,
            peeled_commit_sha=identity.peeled_commit_sha,
            event_at=at.astimezone(UTC),
            event_time_source=source,
            signature_state=signature,
        )
    if set(parsed) != set(expected):
        raise ValueError("Audit release inventory is incomplete")
    return tuple(parsed[ref] for ref in sorted(parsed))


def independent_months(protocol, groups, diff: dict, tags: tuple) -> tuple:
    pulls, canonical, _targets, coverage, unresolved = groups
    actors = {item.pull_number: item for item in pulls}
    output = []
    month = protocol.measurement_period_start_month
    while month < protocol.measurement_period_end_exclusive:
        end = (
            month.replace(year=month.year + 1, month=1)
            if month.month == 12
            else (month.replace(month=month.month + 1))
        )

        def contains(at, start=month, stop=end):
            return start <= at.astimezone(UTC).date() < stop

        accepted = [item for item in coverage if contains(item.github_merged_at)]
        primary = [item for item in accepted if item.local_source_link_verified]
        integrations = [item for item in canonical if contains(item.event_at)]
        releases = [item for item in tags if contains(item.event_at)]
        human_ids, bot_ids, components = set(), set(), set()
        unknown = 0
        events = []
        for item in sorted(primary, key=lambda item: item.pull_number):
            actor = actors[item.pull_number]
            if actor.merged_at != item.github_merged_at or not item.local_source_commit_sha:
                raise ValueError("Audit source event join changed")
            if actor.actor_identity_status == "UNKNOWN_DELETED_OR_NULL":
                unknown += 1
            elif actor.actor_class == "BOT":
                bot_ids.add(actor.actor_id)
            elif actor.actor_class == "HUMAN_OR_UNRESOLVED_ACCOUNT":
                human_ids.add(actor.actor_id)
            else:
                raise ValueError("Audit actor classification changed")
            events.append(
                {
                    "pull_number": item.pull_number,
                    "github_merged_at": item.github_merged_at.isoformat(),
                    "local_source_commit_sha": item.local_source_commit_sha,
                    "actor_manifest_id": None
                    if actor.actor_id is None
                    else digest({"actor_id": actor.actor_id}),
                    "actor_class": actor.actor_class,
                    "actor_identity_status": actor.actor_identity_status,
                }
            )
        canonical_events = []
        for item in sorted(integrations, key=lambda item: item.merge_commit_sha):
            canonical_events.append(
                {
                    "merge_commit_sha": item.merge_commit_sha,
                    "canonical_pull_number": item.canonical_pull_number,
                    "event_at": item.event_at.isoformat(),
                    "event_time_source": item.event_time_source,
                }
            )
            for path in diff[item.merge_commit_sha]:
                parts = path.split("/")
                if len(parts) == 1:
                    components.add("ROOT")
                elif parts[0] != "src":
                    components.add(parts[0])
                else:
                    components.add("src/" + (parts[1] if len(parts) > 2 else "_root"))
        source_count = len({item.local_source_commit_sha for item in primary})
        github_count = sum(item.event_time_source == "GITHUB_MERGED_AT" for item in integrations)
        output.append(
            S5AcceptedDevelopmentMonthlyMeasurementRow(
                sequence=len(output) + 1,
                month_start=month,
                month_end_exclusive=end,
                measurement_available_at=datetime.combine(end, datetime.min.time(), UTC)
                + timedelta(days=7),
                primary_source_verified_accepted_pull_count=len(primary),
                primary_distinct_local_source_commit_count=source_count,
                primary_many_to_one_excess_count=len(primary) - source_count,
                all_accepted_pull_count=len(accepted),
                source_unverified_accepted_pull_count=len(accepted) - len(primary),
                canonical_integration_count=len(integrations),
                canonical_github_time_count=github_count,
                canonical_git_fallback_time_count=len(integrations) - github_count,
                known_human_or_unresolved_actor_count=len(human_ids),
                unknown_actor_event_count=unknown,
                human_contributor_lower_bound=len(human_ids),
                human_contributor_upper_bound=len(human_ids) + unknown,
                known_bot_actor_count=len(bot_ids),
                canonical_component_key_count=len(components),
                unresolved_git_merge_count=sum(
                    contains(item.git_committer_at) for item in unresolved
                ),
                stable_release_tag_count=len(releases),
                signed_annotated_stable_release_tag_count=sum(
                    item.signature_state == "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"
                    for item in releases
                ),
                primary_event_manifest_evidence_hash=digest(events),
                canonical_event_manifest_evidence_hash=digest(canonical_events),
                component_key_manifest_evidence_hash=digest(tuple(sorted(components))),
                release_tag_manifest_evidence_hash=digest(
                    tuple(
                        item.model_dump(mode="json")
                        for item in sorted(releases, key=lambda item: item.ref_name)
                    )
                ),
                source_normalization_result_evidence_hash=protocol.corrected_normalization_result_evidence_hash,
            )
        )
        month = end
    return tuple(output)


def build_audit() -> dict:
    protocol, contract = run.check_protocol(), run.check_contract()
    if run.read_sealed(run.CONTRACT_AUDIT) != run.execution_audit(contract):
        raise ValueError("Audit execution authority changed")
    result = run.read_sealed(run.RESULT)
    if (
        result["protocol_hash"] != protocol["evidence_hash"]
        or result["contract_hash"] != contract["evidence_hash"]
        or result["authority"] != run.AUTHORITY
        or result["decision"] != "PASS_S5_AMENDED_MEASUREMENT_PENDING_INDEPENDENT_AUDIT"
        or result["next_action"] != "AUDIT_S5_AMENDED_MEASUREMENT_RESULT"
        or result["historical_qualification_permitted"] is not False
        or result["process_count"] != 3
    ):
        raise ValueError("Audit result lineage or decision changed")
    attempt = run.read_sealed(run.ATTEMPT)
    if (
        attempt["contract_hash"] != contract["evidence_hash"]
        or attempt["started_at"] != result["started_at"]
    ):
        raise ValueError("Audit reserved attempt changed")
    run.check_bindings(result["transcript_bindings"])
    expected_paths = {
        f"{index:02d}.{suffix}" for index in range(1, 4) for suffix in ("stdout", "stderr", "json")
    }
    if {path.name for path in run.RESPONSES.iterdir()} != expected_paths:
        raise ValueError("Audit transcript inventory changed")
    payloads = []
    previous_end = datetime.fromisoformat(result["started_at"])
    result_end = datetime.fromisoformat(result["completed_at"])
    if (result_end - previous_end).total_seconds() > protocol["maximum_total_seconds"]:
        raise ValueError("Audit result time ceiling exceeded")
    for index in range(3):
        transcript = run.read_sealed(run.RESPONSES / f"{index + 1:02d}.json")
        output = run.RESPONSES / f"{index + 1:02d}.stdout"
        error = run.RESPONSES / f"{index + 1:02d}.stderr"
        started, ended = (
            datetime.fromisoformat(transcript[key]) for key in ("started_at", "completed_at")
        )
        if (
            transcript["sequence"] != index + 1
            or transcript["command"] != list(run.command_for(protocol, index))
            or transcript["network"] is not False
            or transcript["return_code"] != 0
            or not previous_end <= started <= ended <= result_end
            or (ended - started).total_seconds() > protocol["maximum_process_seconds"]
            or transcript["stdout_sha256"] != run.file_hash(output)
            or transcript["stderr_sha256"] != run.file_hash(error)
            or transcript["stdout_bytes"] != output.stat().st_size
            or transcript["stderr_bytes"] != error.stat().st_size
            or max(output.stat().st_size, error.stat().st_size) > protocol["maximum_stdout_bytes"]
        ):
            raise ValueError("Audit local transcript changed")
        previous_end = ended
        payloads.append(output.read_bytes())
    old, *_ = run.old_authorization()
    groups = run.load_inputs(old)
    reachable = run.original.parse_reachable_commits(payloads[1])
    diff = run.original.parse_first_parent_diff_stream(payloads[0])
    if len(reachable) != 50_395 or len(diff) != 17_543:
        raise ValueError("Audit Git history scope changed")
    tags = reconstruct_tags(payloads[2], run.source_manifest(), reachable)
    rows = independent_months(old, groups, diff, tags)
    if run.original.serialize_rows(rows) != run.ROWS.read_bytes():
        raise ValueError("Independent monthly reconstruction differs")
    if run.serialize_tags(tags) != run.TAGS.read_bytes():
        raise ValueError("Independent release reconstruction differs")
    previous = run.original.load_jsonl(
        PROJECT_ROOT / run.original.DEFAULT_OUTPUT, S5AcceptedDevelopmentMonthlyMeasurementRow
    )
    run.compare_non_release(rows, previous)
    included = sum(row.stable_release_tag_count for row in rows)
    counts = {
        "primary": sum(row.primary_source_verified_accepted_pull_count for row in rows),
        "all_accepted": sum(row.all_accepted_pull_count for row in rows),
        "canonical": sum(row.canonical_integration_count for row in rows),
        "unresolved": sum(row.unresolved_git_merge_count for row in rows),
    }
    for key, total in zip(counts, (16_271, 16_279, 16_242, 479), strict=True):
        if counts[key] + result["excluded_events"].get(key, 0) != total:
            raise ValueError("Audit event conservation changed")
    if (
        result["row_count"] != len(rows)
        or len(rows) != 212
        or result["inventory_count"] != len(tags)
        or len(tags) != 132
        or result["included_release_count"] != included
        or result["excluded_release_count"] != len(tags) - included
        or result["annotated_count"] != sum(item.object_type == "tag" for item in tags)
        or result["lightweight_count"] != sum(item.object_type == "commit" for item in tags)
        or result["non_release_fields_match_v1"] is not True
        or result["output_sha256"] != run.file_hash(run.ROWS)
        or result["tags_sha256"] != run.file_hash(run.TAGS)
    ):
        raise ValueError("Audit summary accounting changed")
    return run.sealed(
        {
            "schema": "aurex-s5-amended-measurement-result-audit-v2",
            "result_hash": result["evidence_hash"],
            "result_file_hash": run.file_hash(run.RESULT),
            "auditor_file_hash": run.file_hash(Path(__file__)),
            "output_hash": run.file_hash(run.ROWS),
            "tags_hash": run.file_hash(run.TAGS),
            "monthly_rows": len(rows),
            "release_inventory": len(tags),
            "included_releases": included,
            "excluded_releases": len(tags) - included,
            "event_counts": counts,
            "independent_monthly_reconstruction": True,
            "non_release_v1_equality": True,
            "local_processes_executed": 0,
            "authority": run.AUTHORITY,
            "historical_qualification_permitted": False,
            "decision": "PASS_S5_AMENDED_MEASUREMENT_INDEPENDENT_AUDIT",
            "next_action": "S5_MEASUREMENT_VIABILITY_AND_PROGRAM_PRIORITY_DECISION",
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently reconstruct S5 monthly fields.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        audit = build_audit()
        if args.check:
            if run.read_sealed(run.AUDIT) != audit:
                raise ValueError("Stored measurement audit changed")
        else:
            run.write_json(run.AUDIT, audit)
        print(json.dumps(audit, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
