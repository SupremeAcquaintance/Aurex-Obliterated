"""Plan/create/verify/restore private Aurex application bundles; no live authority."""

import argparse
import json
from pathlib import Path

from aurex.config.settings import Settings
from aurex.db.recovery_bundle import create_bundle, recovery_plan, restore_bundle, verify_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "create", "verify", "restore"])
    parser.add_argument("--root", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument(
        "--scope",
        choices=["FULL_EVIDENCE", "OPERATIONAL_WITHOUT_RAW_ARCHIVES"],
        default="FULL_EVIDENCE",
    )
    args = parser.parse_args()
    if args.mode in {"plan", "create"} and (args.root is None or args.database is None):
        parser.error("plan/create requires --root and --database")
    if args.mode == "restore" and args.destination is None:
        parser.error("restore requires a new --destination")
    try:
        if args.mode == "plan":
            result = recovery_plan(
                args.root, args.database, args.bundle.resolve().parent, args.scope
            )
        elif args.mode == "restore":
            result = restore_bundle(args.bundle, args.destination)
        else:
            manifest = (
                create_bundle(args.root, args.database, args.bundle, args.scope, Settings())
                if args.mode == "create"
                else verify_bundle(args.bundle)
            )
            result = {
                "status": "VERIFIED_BUNDLE",
                "scope": manifest.scope,
                "included_files": len(manifest.files),
                "omitted_archives": len(manifest.omitted_archives),
                "archive_bytes": manifest.archive_bytes,
                "archive_sha256": manifest.archive_sha256,
                "credentials_included": False,
                "application_start_verified": False,
                "dependency_wheels_included": False,
                "live_authority": False,
            }
        print(json.dumps(result, indent=2))
        return 0 if not result["status"].startswith("BLOCKED") else 1
    except Exception as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(exc).__name__, "live_authority": False}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
