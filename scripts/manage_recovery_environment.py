"""Download pinned public wheels or reconstruct an isolated environment offline."""

import argparse
import json
from pathlib import Path

from aurex.db.recovery_environment import create_environment, prepare_wheelhouse, verify_wheelhouse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["download", "verify", "create"])
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.mode == "create" and args.destination is None:
        parser.error("create requires a new --destination")
    try:
        if args.mode == "create":
            result = create_environment(args.wheelhouse, args.destination)
        else:
            manifest = (
                prepare_wheelhouse(args.wheelhouse)
                if args.mode == "download"
                else verify_wheelhouse(args.wheelhouse)
            )
            result = {
                "status": "VERIFIED_WHEELHOUSE",
                "packages": len(manifest["wheels"]),
                "offline_install_verified": False,
                "live_authority": False,
            }
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(exc).__name__, "live_authority": False}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
