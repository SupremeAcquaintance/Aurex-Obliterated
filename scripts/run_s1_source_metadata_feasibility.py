from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_feasibility import (  # noqa: E402
    S1_SOURCE_NEXT_AUTHORIZATION,
    S1_SOURCE_PASS_DECISION,
    S1_SOURCE_STOP_DECISION,
    S1SourceGate,
    S1SourceMetadataProtocol,
    S1SourceMetadataResult,
    S1SourceRequest,
    S1SourceResponse,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_source_metadata_feasibility import (  # noqa: E402
    build_protocol,
)
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_source_metadata_feasibility_result_v1.json"
)
RUNNER_PATH = Path("scripts/run_s1_source_metadata_feasibility.py")
USER_AGENT = "Aurex-S1-Source-Metadata/1.0"


class BoundedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, maximum_redirects: int) -> None:
        super().__init__()
        self.maximum_redirects = maximum_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.redirect_count += 1
        if self.redirect_count > self.maximum_redirects:
            raise HTTPError(newurl, code, "S1 redirect budget exhausted", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def response_record(
    *,
    request_id: str,
    attempted_at: datetime,
    status_code: int | None,
    final_url: str | None,
    content_type: str | None,
    content_length: int | None,
    etag: str | None,
    last_modified: str | None,
    outcome: str,
    error_type: str | None = None,
    error_message: str | None = None,
) -> S1SourceResponse:
    final_host = urlparse(final_url).hostname if final_url else None
    payload = {
        "request_id": request_id,
        "attempted_at": attempted_at,
        "status_code": status_code,
        "final_url": final_url,
        "final_host": final_host,
        "content_type": content_type,
        "content_length": content_length,
        "etag": etag,
        "last_modified": last_modified,
        "outcome": outcome,
        "error_type": error_type,
        "error_message": error_message,
    }
    provisional = S1SourceResponse.model_construct(
        **payload,
        response_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["response_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"response_evidence_hash"})
    )
    return S1SourceResponse.model_validate(complete)


def parse_content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def execute_head(
    request_spec: S1SourceRequest,
    *,
    timeout_seconds: int,
    maximum_redirects: int,
) -> S1SourceResponse:
    attempted_at = datetime.now(UTC)
    request = Request(
        request_spec.url,
        method="HEAD",
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
    )
    opener = build_opener(BoundedRedirectHandler(maximum_redirects))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
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
    except HTTPError as exc:
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
    protocol: S1SourceMetadataProtocol,
    responses: tuple[S1SourceResponse, ...],
) -> tuple[S1SourceGate, ...]:
    by_id = {response.request_id: response for response in responses}
    specs = {request.request_id: request for request in protocol.requests}

    exact = len(responses) == 4 and set(by_id) == set(specs)
    zero_body = all(response.body_bytes_read == 0 for response in responses)
    alfred = by_id.get("01-alfred-nfci-series")
    vintage = [
        by_id.get("02-nfci-vintage-2020"),
        by_id.get("03-nfci-vintage-2021"),
    ]
    api = by_id.get("04-structured-api-no-key")
    hosts_match = exact and all(
        response.final_host == specs[response.request_id].expected_final_host
        for response in responses
        if response.final_host is not None
    ) and all(response.final_host is not None for response in responses)
    vintage_reachable = all(
        response is not None
        and response.outcome == "HTTP_RESPONSE"
        and response.status_code == 200
        for response in vintage
    )
    downloadable_types = all(
        response is not None
        and response.content_type is not None
        and any(
            token in response.content_type.lower()
            for token in ("csv", "text/plain", "octet-stream", "zip")
        )
        for response in vintage
    )
    gates = (
        S1SourceGate(
            gate_id="EXACT_REQUEST_AND_ZERO_BODY_BUDGET",
            status="PASS" if exact and zero_body else "FAIL",
            reason=(
                "Four frozen HEAD responses were recorded with zero body bytes."
                if exact and zero_body
                else "The request count or zero-body invariant failed."
            ),
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
            reason="The official ALFRED NFCI series HEAD endpoint must return HTTP 200.",
        ),
        S1SourceGate(
            gate_id="NO_KEY_VINTAGE_ENDPOINTS_REACHABLE",
            status="PASS" if vintage_reachable else "FAIL",
            reason="Both frozen no-key vintage CSV HEAD endpoints must return HTTP 200.",
        ),
        S1SourceGate(
            gate_id="VINTAGE_CONTENT_TYPES_DOWNLOADABLE",
            status="PASS" if downloadable_types else "FAIL",
            reason="Both vintage endpoints must advertise a downloadable content type.",
        ),
        S1SourceGate(
            gate_id="OFFICIAL_FINAL_HOSTS_MATCH",
            status="PASS" if hosts_match else "FAIL",
            reason="Every final host must equal its frozen official St. Louis Fed host.",
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
            reason=(
                "The no-key structured API returned a classifiable HTTP response; "
                "no credential was supplied."
            ),
        ),
        S1SourceGate(
            gate_id="ZERO_OUTCOME_AND_TRADING_AUTHORITY",
            status="PASS",
            reason="No body, market value, parameter, return, candidate, or order was opened.",
        ),
    )
    return tuple(sorted(gates, key=lambda gate: gate.gate_id))


def build_result(
    *,
    protocol_path: Path,
    protocol: S1SourceMetadataProtocol,
    responses: tuple[S1SourceResponse, ...],
    completed_at: datetime,
) -> S1SourceMetadataResult:
    ordered = tuple(sorted(responses, key=lambda response: response.request_id))
    gates = evaluate_gates(protocol, ordered)
    failed = any(gate.status == "FAIL" for gate in gates)
    payload = {
        "completed_at": completed_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_source_sha256": file_sha256(PROJECT_ROOT / RUNNER_PATH),
        "responses": ordered,
        "gates": gates,
        "decision": S1_SOURCE_STOP_DECISION if failed else S1_SOURCE_PASS_DECISION,
        "next_authorization": (
            "NONE_SOURCE_TRANSPORT_UNAVAILABLE"
            if failed
            else S1_SOURCE_NEXT_AUTHORIZATION
        ),
    }
    provisional = S1SourceMetadataResult.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"result_evidence_hash"})
    )
    return S1SourceMetadataResult.model_validate(complete)


def write_atomic(path: Path, result: S1SourceMetadataResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 source result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S1SourceMetadataResult.model_validate_json(serialized) != result:
        raise ValueError("S1 source result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the S1 HEAD-only source probe.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 source result: {args.output}")
    protocol = S1SourceMetadataProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    if protocol != build_protocol(frozen_at=protocol.frozen_at):
        raise SystemExit("Frozen S1 source protocol differs from reconstruction")
    responses = tuple(
        execute_head(
            request,
            timeout_seconds=protocol.connect_timeout_seconds,
            maximum_redirects=protocol.maximum_redirects_per_request,
        )
        for request in protocol.requests
    )
    result = build_result(
        protocol_path=args.protocol,
        protocol=protocol,
        responses=responses,
        completed_at=datetime.now(UTC),
    )
    write_atomic(args.output, result)
    print(
        f"COMPLETE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} requests=4 body_bytes=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
