"""Read-only reconciliation of a terminal supervisor journal with retained receipts."""

import argparse
import json
import os
import sqlite3
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from aurex.db.models import NativeBarOutcome, PaperOrder, PaperTrade, Signal
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_market_data import EPOCH
from aurex.signal_gateway.native_processing import STREAM_KEY, verified_native_history
from aurex.signal_gateway.native_supervision import (
    MAX_JOURNAL_BYTES,
    NativeSupervisorConfig,
    audit_run_journal,
    error_code,
)


def audit_database(database: Path, directory: Path) -> dict:
    journal_path = directory / "events.jsonl"
    with journal_path.open("rb") as handle:
        journal_bytes = handle.read(MAX_JOURNAL_BYTES + 1)
    if len(journal_bytes) > MAX_JOURNAL_BYTES:
        raise NativeBarError("supervisor_journal_size_invalid")
    audit = audit_run_journal(directory)
    if audit.status != "TERMINAL":
        raise NativeBarError("supervisor_run_not_terminal")
    journal_hash = sha256(journal_bytes).hexdigest()
    records = [json.loads(line)["evidence"] for line in journal_bytes.splitlines()]
    config = NativeSupervisorConfig.model_validate(records[0]["payload"]["config"])
    path = database.resolve(strict=True)
    uri = path.as_uri() + "?mode=ro"
    reader = create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
    try:
        with Session(reader) as session:
            session.execute(text("PRAGMA query_only=ON"))
            session.execute(text("BEGIN"))
            verified = verified_native_history(session, EPOCH)
            referenced = 0
            new_ids = set()
            for record in records:
                if record["kind"] != "BAR_COMMITTED":
                    continue
                payload = record["payload"]
                row = session.get(NativeBarOutcome, payload["receipt_id"])
                if (
                    row is None
                    or row.stream_key != STREAM_KEY
                    or row.evidence_hash != payload["receipt_hash"]
                    or row.outcome != payload["outcome"]
                    or row.evidence["scope"] != config.scope.model_dump(mode="json")
                    or (config.mode == "OBSERVE" and row.outcome != "SOURCE_OBSERVED_NO_ENTRY")
                    or (config.mode == "JAM" and row.evidence.get("jam_decision") is None)
                    or (config.mode == "EXIT_ONLY" and row.evidence.get("online_exit") is None)
                ):
                    raise NativeBarError("supervisor_journal_database_mismatch")
                if not payload["duplicate"]:
                    if row.id in new_ids:
                        raise NativeBarError("supervisor_journal_duplicate_new_receipt")
                    new_ids.add(row.id)
                referenced += 1
            head = verified.head[1] if verified.head else None
            result = {
                "schema_version": "native_supervisor_database_audit_v1",
                "status": "PASS",
                "run_status": audit.terminal.status,
                "run_reason": audit.terminal.reason,
                "config_hash": audit.config_hash,
                "journal_sha256": journal_hash,
                "journal_reference_count": referenced,
                "run_new_receipt_count": len(new_ids),
                "database_receipt_count": session.scalar(
                    select(func.count()).select_from(NativeBarOutcome)
                ),
                "head_receipt_hash": verified.head[0].evidence_hash if verified.head else None,
                "head_closed_at": head.closed_at.isoformat() if head else None,
                "head_age_at_commit_seconds": (head.processed_at - head.closed_at).total_seconds()
                if head
                else None,
                "database_counts": {
                    name: session.scalar(select(func.count()).select_from(model))
                    for name, model in (
                        ("signals", Signal),
                        ("paper_orders", PaperOrder),
                        ("paper_trades", PaperTrade),
                    )
                },
                "database_reconciled": True,
                "read_only": True,
                "source_origin_verified": False,
                "forward_qualifying": False,
                "live_authority": False,
                "platform_acceptance": False,
            }
    finally:
        reader.dispose()
    with journal_path.open("rb") as handle:
        if sha256(handle.read(MAX_JOURNAL_BYTES + 1)).hexdigest() != journal_hash:
            raise NativeBarError("supervisor_journal_changed_during_audit")
    result["audit_hash"] = content_hash(result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise NativeBarError("supervisor_audit_output_exists")
        result = audit_database(args.database, args.run_directory)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if json.loads(args.output.read_text(encoding="utf-8")) != result:
            raise NativeBarError("supervisor_audit_readback_mismatch")
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "reason": error_code(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
