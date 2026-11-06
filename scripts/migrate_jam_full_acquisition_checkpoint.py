from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_full_acquisition import (  # noqa: E402
    JAM_FULL_MONTHS,
    JamFullMonthEvidence,
)
from aurex.backtest_engine.universe import (  # noqa: E402
    universe_evidence_hash,
)
from scripts.run_jam_archive_full_acquisition import (  # noqa: E402
    file_sha256,
    load_protocol,
    runner_contract_hash,
    target_archive_path,
)

EXPECTED_OLD_RUNNER_HASH = (
    "c575d96c2ab0f2e86208e31aee1596c1cb12089232a21430369217d2f127d692"
)
DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/jam_archive_full_acquisition_checkpoint_v1.json"
)
DEFAULT_BACKUP = Path(
    "data/evidence/"
    "jam_archive_full_acquisition_checkpoint_v1.pre_zip_member_recording_runner.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_full_acquisition_checkpoint_migration_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")


def load_checkpoint_payload(path: Path) -> tuple[dict, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence_hash = payload.pop("checkpoint_evidence_hash", None)
    if evidence_hash != universe_evidence_hash(payload):
        raise ValueError("Jam checkpoint migration source hash failed")
    return payload, evidence_hash


def verify_source(
    *,
    path: Path,
    protocol_path: Path,
    evidence_root: Path,
) -> tuple[dict, str, list[JamFullMonthEvidence], int]:
    protocol = load_protocol(protocol_path)
    payload, evidence_hash = load_checkpoint_payload(path)
    months = [
        JamFullMonthEvidence.model_validate(item) for item in payload["months"]
    ]
    if (
        payload.get("schema_version")
        != "aurex-jam-full-acquisition-checkpoint-v1"
        or payload.get("protocol_evidence_hash")
        != protocol.protocol_evidence_hash
        or payload.get("runner_contract_hash") != EXPECTED_OLD_RUNNER_HASH
        or [item.month for item in months]
        != list(JAM_FULL_MONTHS[: len(months)])
        or len(months) != 35
    ):
        raise ValueError("Jam checkpoint migration source lineage changed")
    completed = {item.month for item in months}
    verified = 0
    for target in protocol.targets:
        if target.month not in completed:
            continue
        archive_path = target_archive_path(evidence_root, target)
        if (
            not archive_path.exists()
            or file_sha256(archive_path) != target.published_archive_sha256
        ):
            raise ValueError(f"Jam migration raw hash changed: {target.key}")
        with zipfile.ZipFile(archive_path) as archive:
            files = [
                member for member in archive.infolist() if not member.is_dir()
            ]
            if (
                len(files) != 1
                or files[0].filename != target.expected_csv_member
            ):
                raise ValueError(
                    f"Jam migration prior member matrix changed: {target.key}"
                )
        verified += 1
    if verified != 70:
        raise ValueError("Jam migration verified archive count changed")
    return payload, evidence_hash, months, verified


def migrated_checkpoint(
    *,
    protocol_evidence_hash: str,
    months: list[JamFullMonthEvidence],
    updated_at: datetime,
) -> dict:
    payload = {
        "schema_version": "aurex-jam-full-acquisition-checkpoint-v1",
        "updated_at": updated_at.isoformat(),
        "protocol_evidence_hash": protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "months": [item.model_dump(mode="json") for item in months],
    }
    payload["checkpoint_evidence_hash"] = universe_evidence_hash(payload)
    return payload


def migration_record(
    *,
    migrated_at: datetime,
    protocol_evidence_hash: str,
    old_checkpoint_evidence_hash: str,
    new_checkpoint_evidence_hash: str,
    verified_archive_count: int,
) -> dict:
    payload = {
        "schema_version": "aurex-jam-full-checkpoint-migration-v1",
        "migrated_at": migrated_at.isoformat(),
        "protocol_evidence_hash": protocol_evidence_hash,
        "old_runner_contract_hash": EXPECTED_OLD_RUNNER_HASH,
        "new_runner_contract_hash": runner_contract_hash(),
        "old_checkpoint_evidence_hash": old_checkpoint_evidence_hash,
        "new_checkpoint_evidence_hash": new_checkpoint_evidence_hash,
        "completed_month_count": 35,
        "verified_archive_count": verified_archive_count,
        "verification": (
            "PUBLISHED_SHA256_AND_EXACT_SINGLE_EXPECTED_MEMBER_FOR_ALL_70_"
            "COMPLETED_ARCHIVES"
        ),
        "reason": (
            "Permit the final runner to record a later official ZIP with a "
            "duplicate nested member without reparsing unchanged prior months."
        ),
        "market_values_inspected": False,
        "return_metrics_calculated": False,
        "creates_candidate": False,
        "creates_testnet_order_authority": False,
        "creates_live_eligibility": False,
    }
    payload["migration_evidence_hash"] = universe_evidence_hash(payload)
    return payload


def write_json_transactional(path: Path, payload: dict) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if path.exists() or temporary.exists():
        raise ValueError(f"Jam migration output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_write(args) -> dict:
    source_payload, old_hash, months, verified = verify_source(
        path=args.checkpoint,
        protocol_path=args.protocol,
        evidence_root=args.evidence_root,
    )
    migrated_at = datetime.now(UTC)
    new_checkpoint = migrated_checkpoint(
        protocol_evidence_hash=source_payload["protocol_evidence_hash"],
        months=months,
        updated_at=migrated_at,
    )
    record = migration_record(
        migrated_at=migrated_at,
        protocol_evidence_hash=source_payload["protocol_evidence_hash"],
        old_checkpoint_evidence_hash=old_hash,
        new_checkpoint_evidence_hash=new_checkpoint[
            "checkpoint_evidence_hash"
        ],
        verified_archive_count=verified,
    )
    write_json_transactional(
        args.backup,
        {
            **source_payload,
            "checkpoint_evidence_hash": old_hash,
        },
    )
    temporary = args.checkpoint.with_name(f"{args.checkpoint.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale checkpoint migration exists: {temporary}")
    temporary.write_text(
        json.dumps(new_checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.checkpoint)
    write_json_transactional(args.output, record)
    print(
        f"WROTE {args.output} {record['migration_evidence_hash']} "
        f"months=35 archives={verified}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> dict:
    source_payload, old_hash, months, verified = verify_source(
        path=args.backup,
        protocol_path=args.protocol,
        evidence_root=args.evidence_root,
    )
    checkpoint, _ = load_checkpoint_payload(args.checkpoint)
    current_months = [
        JamFullMonthEvidence.model_validate(item)
        for item in checkpoint["months"]
    ]
    record = json.loads(args.output.read_text(encoding="utf-8"))
    record_hash = record.pop("migration_evidence_hash", None)
    migration_checkpoint = migrated_checkpoint(
        protocol_evidence_hash=source_payload["protocol_evidence_hash"],
        months=months,
        updated_at=datetime.fromisoformat(record["migrated_at"]),
    )
    expected_record = migration_record(
        migrated_at=datetime.fromisoformat(record["migrated_at"]),
        protocol_evidence_hash=source_payload["protocol_evidence_hash"],
        old_checkpoint_evidence_hash=old_hash,
        new_checkpoint_evidence_hash=migration_checkpoint[
            "checkpoint_evidence_hash"
        ],
        verified_archive_count=verified,
    )
    expected_record.pop("migration_evidence_hash")
    if (
        checkpoint.get("schema_version")
        != "aurex-jam-full-acquisition-checkpoint-v1"
        or checkpoint.get("protocol_evidence_hash")
        != source_payload["protocol_evidence_hash"]
        or checkpoint.get("runner_contract_hash") != runner_contract_hash()
        or current_months[:35] != months
        or [item.month for item in current_months]
        != list(JAM_FULL_MONTHS[: len(current_months)])
        or len(current_months) < 35
        or record != expected_record
        or record_hash != universe_evidence_hash(record)
    ):
        raise ValueError("Jam checkpoint migration is not reproducible")
    print(
        "PASS "
        f"jam_checkpoint_migration={record_hash} "
        f"old={old_hash} "
        f"new={migration_checkpoint['checkpoint_evidence_hash']} "
        f"current_months={len(current_months)} archives={verified}",
        flush=True,
    )
    return record


def parse_args():
    parser = argparse.ArgumentParser(
        description="Migrate the verified 35-month Jam checkpoint once."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write:
            run_write(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
