"""Acquire or independently reconstruct public candles without opening Aurex's DB."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from aurex.signal_gateway.native_market_data import (
    CLOCK_TOLERANCE_SECONDS,
    PublicCandleClient,
    PublicDataError,
    read_public_evidence,
    verify_public_evidence,
    write_public_evidence,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--first-open", type=datetime.fromisoformat)
    args = parser.parse_args(argv)
    result = {"execution_authority": False, "forward_qualifying": False, "database_opened": False}
    try:
        if args.verify:
            if args.first_open is not None or args.count != 1000:
                raise PublicDataError("verification_does_not_accept_acquisition_options")
            evidence = read_public_evidence(args.verify)
            result["mode"] = "offline_reconstruction"
        else:
            if args.output.exists():
                raise PublicDataError("output_already_exists")
            evidence = PublicCandleClient().acquire(count=args.count, first_open=args.first_open)
            result["artifact_sha256"] = write_public_evidence(evidence, args.output)
            # Success requires disk readback, not just the in-memory result.
            evidence = read_public_evidence(args.output)
            result["mode"] = "public_acquisition"
        bars = verify_public_evidence(evidence)
        result.update(
            status="PASS",
            transport=evidence.transport,
            bar_count=len(bars),
            first_open=bars[0].timestamp.isoformat(),
            last_open=bars[-1].timestamp.isoformat(),
            candles_sha256=evidence.candles_sha256,
            observed_at=evidence.pages[-1].received_at.isoformat(),
        )
    except (PublicDataError, ValidationError, OSError) as exc:
        code = str(exc) if isinstance(exc, PublicDataError) else type(exc).__name__
        result.update(status="BLOCKED", reason=code)
        if isinstance(exc, PublicDataError):
            result.update(http_status=exc.status, retry_after_seconds=exc.retry_after)
            if exc.clock is not None:
                result["clock_observation"] = exc.clock.model_dump(mode="json")
                result["clock_tolerance_seconds"] = CLOCK_TOLERANCE_SECONDS
        print(json.dumps(result, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
