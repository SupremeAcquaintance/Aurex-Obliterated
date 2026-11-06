import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v3_p02_payload_pilot import (
    V3_P02_SAMPLE_KEYS,
    V3P02PayloadPilotProtocol,
    V3P02SamplePayloadEvidence,
)
from aurex.backtest_engine.research_v3_p02_stop_result import (
    V3P02FailedSampleRequestEvidence,
    V3P02PayloadPilotStopResult,
    audit_v3_p02_payload_pilot_stop_result,
    build_v3_p02_payload_pilot_stop_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

try:
    from scripts.run_v3_p02_payload_pilot import (
        _validate_request_marker,
        inspect_sample_archive,
        load_protocol,
        runner_contract_hash,
        sample_targets,
        target_paths,
    )
except ModuleNotFoundError:
    from run_v3_p02_payload_pilot import (
        _validate_request_marker,
        inspect_sample_archive,
        load_protocol,
        runner_contract_hash,
        sample_targets,
        target_paths,
    )

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = Path(
    "data/evidence/v3_p02_payload_pilot_protocol_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ATTEMPTED_RESULT = Path(
    "data/evidence/v3_p02_payload_pilot_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p02_payload_pilot_stop_result_v1.json"
)


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def finalizer_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "finalize_v3_p02_payload_pilot_stop.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_stop_result.py",
        ]
    )


def inspect_attempt_state(
    *,
    protocol: V3P02PayloadPilotProtocol,
    evidence_root: Path,
    attempted_result: Path,
) -> tuple[
    list[V3P02SamplePayloadEvidence],
    V3P02FailedSampleRequestEvidence,
]:
    if attempted_result.exists():
        raise ValueError(
            "An authoritative V3P02 payload result exists; stop finalization refused"
        )
    root = evidence_root / "v3_p02_payload_pilot_v1"
    if not root.is_dir():
        raise ValueError("V3P02 payload attempt directory is absent")
    if list(root.rglob("*.part")):
        raise ValueError("V3P02 attempt contains a stale transactional file")

    targets = sample_targets(protocol)
    if [target.key for target in targets] != V3_P02_SAMPLE_KEYS:
        raise ValueError("V3P02 frozen sample target order changed")
    marker_paths = []
    archive_paths = []
    verified = []
    failed = None
    for target in targets:
        archive_path, marker_path = target_paths(
            evidence_root=evidence_root,
            target=target,
        )
        if not marker_path.is_file():
            raise ValueError(f"V3P02 request marker is absent: {target.key}")
        _validate_request_marker(
            marker_path=marker_path,
            target=target,
            protocol=protocol,
        )
        marker_paths.append(marker_path)
        if target.key == ("DOGEUSDT", "2024-12"):
            if archive_path.exists():
                raise ValueError("Failed V3P02 DOGE archive unexpectedly exists")
            marker_payload = json.loads(
                marker_path.read_text(encoding="utf-8")
            )
            failed = V3P02FailedSampleRequestEvidence(
                archive_url=target.archive_url,
                request_marker_local_path=marker_path.relative_to(
                    evidence_root
                ).as_posix(),
                request_marker_sha256=file_sha256(marker_path),
                requested_at=datetime.fromisoformat(
                    marker_payload["requested_at"]
                ),
            )
            continue
        if not archive_path.is_file():
            raise ValueError(
                f"Verified V3P02 sample archive is absent: {target.key}"
            )
        archive_paths.append(archive_path)
        verified.append(
            inspect_sample_archive(
                target=target,
                archive_path=archive_path,
                evidence_root=evidence_root,
                protocol=protocol,
                payload_request_count=1,
            )
        )

    if (
        failed is None
        or len(marker_paths) != 3
        or len(archive_paths) != 2
        or len(list(root.rglob("*.request.json"))) != 3
        or len(list(root.rglob("*.zip"))) != 2
    ):
        raise ValueError("V3P02 attempt file matrix changed")
    return verified, failed


def authoritative_stop_result(
    *,
    generated_at: datetime,
    protocol: V3P02PayloadPilotProtocol,
    verified_samples: list[V3P02SamplePayloadEvidence],
    failed_sample: V3P02FailedSampleRequestEvidence,
) -> V3P02PayloadPilotStopResult:
    return build_v3_p02_payload_pilot_stop_result(
        generated_at=generated_at,
        payload_pilot_protocol_evidence_hash=(
            protocol.protocol_evidence_hash
        ),
        failed_runner_contract_hash=runner_contract_hash(),
        finalizer_contract_hash=finalizer_contract_hash(),
        verified_samples=verified_samples,
        failed_sample=failed_sample,
        limitations=[
            (
                "The frozen pilot exhausted its three sample GET requests and "
                "permitted no retry after the DOGEUSDT response ended early."
            ),
            (
                "The runner transactionally removed the partial DOGEUSDT file, so "
                "its partial byte count and the exact HEAD Content-Length were not "
                "preserved."
            ),
            (
                "The first run completed 744 HEAD observations, but those records "
                "and the exact attempt total were not persisted because no "
                "authoritative pilot result was created."
            ),
            (
                "The three resource gates were reported as passing by the failed "
                "runner, but their exact size observations are unavailable in this "
                "stop artifact."
            ),
            (
                "AAVEUSDT and BNBUSDT archives remain checksum verified and pass the "
                "frozen ID/timestamp density checks; two samples cannot satisfy the "
                "three-sample protocol."
            ),
            (
                "The stop is a transport/provenance outcome and does not establish "
                "that V3P02 lacks predictive edge or could never be acquired."
            ),
            (
                "No price, quantity, maker side, signal, trade, PnL, return, or "
                "strategy outcome was parsed or calculated."
            ),
            (
                "This result authorizes no retry, full acquisition, primary "
                "selection, candidate, validation, holdout, forward, Pine, paper, "
                "sandbox, live, or capital action."
            ),
        ],
    )


def write_result(path: Path, result: V3P02PayloadPilotStopResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V3P02PayloadPilotStopResult.model_validate_json(serialized) != result:
        raise ValueError("V3P02 stop result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_finalize(args) -> V3P02PayloadPilotStopResult:
    if args.output.exists():
        raise ValueError("Frozen V3P02 stop result exists; use --audit")
    protocol = load_protocol(args.protocol)
    verified, failed = inspect_attempt_state(
        protocol=protocol,
        evidence_root=args.evidence_root,
        attempted_result=args.attempted_result,
    )
    result = authoritative_stop_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        verified_samples=verified,
        failed_sample=failed,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"verified={result.verified_sample_count} "
        f"failed={result.failed_sample_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return run_audit(args)


def run_audit(args) -> V3P02PayloadPilotStopResult:
    protocol = load_protocol(args.protocol)
    result = V3P02PayloadPilotStopResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_payload_pilot_stop_result(result)
        or result.payload_pilot_protocol_evidence_hash
        != protocol.protocol_evidence_hash
        or result.failed_runner_contract_hash != runner_contract_hash()
        or result.finalizer_contract_hash != finalizer_contract_hash()
    ):
        raise ValueError("V3P02 stop result lineage audit failed")
    verified, failed = inspect_attempt_state(
        protocol=protocol,
        evidence_root=args.evidence_root,
        attempted_result=args.attempted_result,
    )
    rebuilt = authoritative_stop_result(
        generated_at=result.generated_at,
        protocol=protocol,
        verified_samples=verified,
        failed_sample=failed,
    )
    if rebuilt != result:
        raise ValueError("V3P02 stop result is not reproducible")
    print(
        "PASS "
        f"v3p02_stop={result.result_evidence_hash} "
        f"verified={result.verified_sample_count} "
        f"failed={result.failed_sample_count} "
        f"retry={result.authorizes_retry} "
        f"selection={result.selects_primary} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Finalize or audit the no-retry V3P02 payload pilot transport stop."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--finalize", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument(
        "--attempted-result",
        type=Path,
        default=DEFAULT_ATTEMPTED_RESULT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.finalize:
            run_finalize(args)
        else:
            run_audit(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
