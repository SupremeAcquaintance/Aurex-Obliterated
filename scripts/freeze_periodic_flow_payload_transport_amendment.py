from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    PeriodicFlowPayloadPilotProtocol,
    audit_periodic_flow_payload_protocol,
)
from aurex.backtest_engine.periodic_flow_payload_transport_amendment import (  # noqa: E402
    PeriodicFlowPayloadTransportAmendment,
    audit_periodic_flow_transport_amendment,
    build_periodic_flow_transport_amendment,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_protocol_v1.json"
)
DEFAULT_MARKER_DIRECTORY = Path(
    "data/evidence/source_snapshots/"
    "q1_periodic_flow_payload_pilot_v1/SPOT"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_transport_amendment_v1.json"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_validate_markers(
    *,
    marker_directory: Path,
    protocol: PeriodicFlowPayloadPilotProtocol,
) -> dict[str, str]:
    request_paths = sorted(marker_directory.glob("*.zip.get.*.request.json"))
    response_paths = sorted(marker_directory.glob("*.zip.get.*.response.json"))
    if len(request_paths) != 3 or len(response_paths) != 3:
        raise ValueError("Q1 transport amendment requires exactly three marker pairs")
    if list(marker_directory.glob("*.part")) or list(marker_directory.glob("*.zip")):
        raise ValueError("Q1 transport amendment requires zero payload artifacts")
    target = protocol.targets[0]
    for index, (request_path, response_path) in enumerate(
        zip(request_paths, response_paths, strict=True),
        start=1,
    ):
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if (
            request.get("schema_version") != "aurex-q1-payload-http-request-v1"
            or request.get("protocol_evidence_hash")
            != protocol.protocol_evidence_hash
            or request.get("product") != "SPOT"
            or request.get("method") != "GET"
            or request.get("url") != target.archive_url
            or request.get("attempt") != index
            or request.get("range") is not None
            or response.get("schema_version")
            != "aurex-q1-payload-http-response-v1"
            or response.get("protocol_evidence_hash")
            != protocol.protocol_evidence_hash
            or response.get("product") != "SPOT"
            or response.get("method") != "GET"
            or response.get("url") != target.archive_url
            or response.get("attempt") != index
            or response.get("status") is not None
            or response.get("bytes_received") != 0
            or response.get("outcome") != "TRANSIENT"
        ):
            raise ValueError("Q1 marker is not a zero-byte pre-HTTP transport denial")
    return {
        path.as_posix(): file_sha256(path)
        for path in sorted((*request_paths, *response_paths))
    }


def authoritative_amendment(
    *,
    frozen_at: datetime,
    protocol_path: Path,
    marker_directory: Path,
) -> PeriodicFlowPayloadTransportAmendment:
    protocol = PeriodicFlowPayloadPilotProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    if not audit_periodic_flow_payload_protocol(protocol):
        raise ValueError("Q1 parent payload protocol hash failed")
    markers = load_and_validate_markers(
        marker_directory=marker_directory,
        protocol=protocol,
    )
    return build_periodic_flow_transport_amendment(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(protocol_path),
        parent_protocol_evidence_hash=protocol.protocol_evidence_hash,
        marker_file_sha256=markers,
        limitations=(
            "The amendment recognizes only the six frozen zero-byte Spot marker files.",
            "No HTTP response, redirect, payload byte, archive, or source observation occurred.",
            "The same three-attempt Spot HTTP budget is restored exactly once.",
            "The USD-M attempt budget and total six actual HTTP-attempt limit are unchanged.",
            "Archive URLs, published checksums, byte limits, parser, and gates are unchanged.",
            "No outcome, candidate, Pine, paper, strategy-order, production, or "
            "live authority is created.",
            "The amendment addresses local transport only and says nothing about "
            "source feasibility.",
        ),
    )


def write_amendment(
    path: Path,
    amendment: PeriodicFlowPayloadTransportAmendment,
) -> None:
    if path.exists():
        raise ValueError("Q1 transport amendment already exists; use --check")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if PeriodicFlowPayloadTransportAmendment.model_validate_json(
        serialized
    ) != amendment:
        raise ValueError("Q1 transport amendment JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 transport amendment transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowPayloadTransportAmendment:
    amendment = authoritative_amendment(
        frozen_at=datetime.now(UTC),
        protocol_path=args.protocol,
        marker_directory=args.marker_directory,
    )
    write_amendment(args.output, amendment)
    print(
        f"WROTE {args.output} {amendment.amendment_evidence_hash} "
        "pre_http_denials=3 payload_bytes=0",
        flush=True,
    )
    return amendment


def run_check(args) -> PeriodicFlowPayloadTransportAmendment:
    amendment = PeriodicFlowPayloadTransportAmendment.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_amendment(
        frozen_at=amendment.frozen_at,
        protocol_path=args.protocol,
        marker_directory=args.marker_directory,
    )
    if amendment != expected or not audit_periodic_flow_transport_amendment(amendment):
        raise ValueError("Q1 transport amendment is not reproducible")
    print(
        f"PASS q1_transport_amendment={amendment.amendment_evidence_hash} "
        "restored_spot_http_attempts=3",
        flush=True,
    )
    return amendment


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or check the Q1 zero-byte transport amendment."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--marker-directory",
        type=Path,
        default=DEFAULT_MARKER_DIRECTORY,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
