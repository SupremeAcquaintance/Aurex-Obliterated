from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_feasibility import (  # noqa: E402
    S1SourceGate,
    S1SourceMetadataProtocol,
    S1SourceResponse,
)
from aurex.backtest_engine.s1_source_transport_v2 import (  # noqa: E402
    S1_V2_NEXT,
    S1_V2_PASS,
    S1_V2_STOP,
    S1SourceTransportAmendmentV2,
    S1SourceTransportResultV2,
    S1V2SourceRequest,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_source_transport_amendment_v2 import (  # noqa: E402
    V1_PROTOCOL_PATH,
    build_amendment,
)
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_source_metadata_feasibility import (  # noqa: E402
    BoundedRedirectHandler,
    parse_content_length,
    response_record,
)

DEFAULT_AMENDMENT = Path("data/evidence/s1_source_transport_amendment_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_source_transport_result_v2.json")
RUNNER_PATH = Path("scripts/run_s1_source_transport_v2.py")
USER_AGENT = "Aurex-S1-Source-Transport-V2/1.0"


def build_requests(
    amendment: S1SourceTransportAmendmentV2,
) -> tuple[S1V2SourceRequest, ...]:
    v1 = S1SourceMetadataProtocol.model_validate_json(
        V1_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    if tuple(request.url for request in v1.requests) != amendment.preserved_urls:
        raise ValueError("S1 v2 URL identity changed")
    return tuple(
        S1V2SourceRequest(
            request_id=request.request_id,
            url=request.url,
            expected_final_host=request.expected_final_host,
            role=request.role,
        )
        for request in v1.requests
    )


def execute_get_open(
    request_spec: S1V2SourceRequest,
    *,
    timeout_seconds: int,
    maximum_redirects: int,
) -> S1SourceResponse:
    attempted_at = datetime.now(UTC)
    request = Request(
        request_spec.url,
        method="GET",
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
    )
    opener = build_opener(BoundedRedirectHandler(maximum_redirects))
    try:
        response = opener.open(request, timeout=timeout_seconds)
        try:
            headers = response.headers
            return response_record(
                request_id=request_spec.request_id,
                attempted_at=attempted_at,
                status_code=response.status,
                final_url=response.geturl(),
                content_type=headers.get("Content-Type"),
                content_length=parse_content_length(headers.get("Content-Length")),
                etag=headers.get("ETag"),
                last_modified=headers.get("Last-Modified"),
                outcome="HTTP_RESPONSE",
            )
        finally:
            response.close()
    except HTTPError as exc:
        try:
            return response_record(
                request_id=request_spec.request_id,
                attempted_at=attempted_at,
                status_code=exc.code,
                final_url=exc.geturl(),
                content_type=exc.headers.get("Content-Type") if exc.headers else None,
                content_length=(
                    parse_content_length(exc.headers.get("Content-Length"))
                    if exc.headers
                    else None
                ),
                etag=exc.headers.get("ETag") if exc.headers else None,
                last_modified=exc.headers.get("Last-Modified") if exc.headers else None,
                outcome="HTTP_RESPONSE",
                error_type=type(exc).__name__,
                error_message=str(exc.reason),
            )
        finally:
            exc.close()
    except (TimeoutError, URLError, OSError) as exc:
        return response_record(
            request_id=request_spec.request_id,
            attempted_at=attempted_at,
            status_code=None,
            final_url=None,
            content_type=None,
            content_length=None,
            etag=None,
            last_modified=None,
            outcome="TRANSPORT_ERROR",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def evaluate_gates(
    requests: tuple[S1V2SourceRequest, ...],
    responses: tuple[S1SourceResponse, ...],
) -> tuple[S1SourceGate, ...]:
    by_id = {response.request_id: response for response in responses}
    specs = {request.request_id: request for request in requests}
    exact = len(responses) == 4 and set(by_id) == set(specs)
    alfred = by_id.get("01-alfred-nfci-series")
    vintage = (
        by_id.get("02-nfci-vintage-2020"),
        by_id.get("03-nfci-vintage-2021"),
    )
    api = by_id.get("04-structured-api-no-key")
    zero_read = all(item.body_bytes_read == 0 for item in responses)
    hosts_match = exact and all(
        response.final_host == specs[response.request_id].expected_final_host
        for response in responses
    )
    vintage_reachable = all(
        item is not None and item.outcome == "HTTP_RESPONSE" and item.status_code == 200
        for item in vintage
    )
    content_types = all(
        item is not None
        and item.content_type is not None
        and any(
            token in item.content_type.lower()
            for token in ("csv", "text/plain", "octet-stream", "zip")
        )
        for item in vintage
    )
    gates = (
        S1SourceGate(
            gate_id="EXACT_GET_OPEN_AND_ZERO_READ_CALLS",
            status="PASS" if exact and zero_read else "FAIL",
            reason="Four frozen GET opens must complete with zero application body bytes.",
        ),
        S1SourceGate(
            gate_id="ALFRED_SERIES_REACHABLE",
            status=(
                "PASS"
                if alfred is not None
                and alfred.outcome == "HTTP_RESPONSE"
                and alfred.status_code == 200
                else "FAIL"
            ),
            reason="The official ALFRED NFCI series GET must open at HTTP 200.",
        ),
        S1SourceGate(
            gate_id="NO_KEY_VINTAGE_ENDPOINTS_REACHABLE",
            status="PASS" if vintage_reachable else "FAIL",
            reason="Both frozen no-key vintage CSV GETs must open at HTTP 200.",
        ),
        S1SourceGate(
            gate_id="VINTAGE_CONTENT_TYPES_DOWNLOADABLE",
            status="PASS" if content_types else "FAIL",
            reason="Both vintage endpoints must advertise downloadable content.",
        ),
        S1SourceGate(
            gate_id="OFFICIAL_FINAL_HOSTS_MATCH",
            status="PASS" if hosts_match else "FAIL",
            reason="Every final host must match its frozen official host.",
        ),
        S1SourceGate(
            gate_id="STRUCTURED_API_AUTH_CLASSIFIED",
            status=(
                "PASS"
                if api is not None
                and api.outcome == "HTTP_RESPONSE"
                and api.status_code in {200, 400, 401, 403}
                else "FAIL"
            ),
            reason="The no-key structured API must return a classifiable response.",
        ),
        S1SourceGate(
            gate_id="ZERO_PAYLOAD_OUTCOME_AND_TRADING_AUTHORITY",
            status="PASS",
            reason="No response read, payload, market value, return, candidate, or order occurred.",
        ),
    )
    return tuple(sorted(gates, key=lambda gate: gate.gate_id))


def build_result(
    *,
    amendment_path: Path,
    amendment: S1SourceTransportAmendmentV2,
    requests: tuple[S1V2SourceRequest, ...],
    responses: tuple[S1SourceResponse, ...],
    completed_at: datetime,
) -> S1SourceTransportResultV2:
    gates = evaluate_gates(requests, responses)
    failed = any(gate.status == "FAIL" for gate in gates)
    payload = {
        "completed_at": completed_at,
        "amendment_file_sha256": file_sha256(amendment_path),
        "amendment_evidence_hash": amendment.amendment_evidence_hash,
        "runner_source_sha256": file_sha256(PROJECT_ROOT / RUNNER_PATH),
        "requests": requests,
        "responses": responses,
        "gates": gates,
        "decision": S1_V2_STOP if failed else S1_V2_PASS,
        "next_authorization": (
            "NONE_S1_V2_SOURCE_TRANSPORT_UNAVAILABLE" if failed else S1_V2_NEXT
        ),
    }
    provisional = S1SourceTransportResultV2.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"result_evidence_hash"})
    )
    return S1SourceTransportResultV2.model_validate(complete)


def write_atomic(path: Path, result: S1SourceTransportResultV2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 v2 result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S1SourceTransportResultV2.model_validate_json(serialized) != result:
        raise ValueError("S1 v2 result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen S1 source transport v2.")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 v2 result: {args.output}")
    amendment = S1SourceTransportAmendmentV2.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    if amendment != build_amendment(frozen_at=amendment.frozen_at):
        raise SystemExit("Frozen S1 v2 amendment differs from reconstruction")
    requests = build_requests(amendment)
    responses = tuple(
        execute_get_open(
            request,
            timeout_seconds=amendment.connect_timeout_seconds,
            maximum_redirects=amendment.maximum_redirects_per_request,
        )
        for request in requests
    )
    result = build_result(
        amendment_path=args.amendment,
        amendment=amendment,
        requests=requests,
        responses=responses,
        completed_at=datetime.now(UTC),
    )
    write_atomic(args.output, result)
    print(
        f"COMPLETE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} requests=4 read_calls=0 body_bytes=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
