"""Create/verify private SQLite backups or restore to a NEW path. No in-place restore."""

import argparse
import json
from pathlib import Path

from aurex.db.backup import BackupError, create_backup, restore_copy, verify_backup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--database", type=Path, required=True)
    create.add_argument("--backup-directory", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--backup-directory", type=Path, required=True)
    restore = commands.add_parser("restore-copy")
    restore.add_argument("--backup-directory", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_backup(args.database, args.backup_directory)
        elif args.command == "verify":
            manifest = verify_backup(args.backup_directory)
        else:
            print(json.dumps(restore_copy(args.backup_directory, args.destination), indent=2))
            return 0
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "database_sha256": manifest.database_sha256,
                    "logical_hash": manifest.snapshot.logical_hash,
                    "revisions": list(manifest.snapshot.revisions),
                    "includes_external_files": False,
                    "live_authority": False,
                },
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        reason = str(exc) if isinstance(exc, BackupError) else type(exc).__name__
        print(json.dumps({"status": "BLOCKED", "reason": reason, "live_authority": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
